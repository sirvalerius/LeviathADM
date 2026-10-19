"""Pannello di esecuzione generico: pulsante → (campi) → (conferma / anteprima) → sottoprocesso → ui.log → esito."""
from __future__ import annotations
from collections.abc import Callable
from pathlib import Path

from nicegui import context, ui

from leviathadm.ui import state
from leviathadm.vault import azioni as A
from leviathadm.vault import esecutore


def testo_stato_deps(master: bool, deps: set[str]) -> str:
    seg = [f"ruolo: {'master' if master else 'slave'}"]
    for nome, chiave in (("Outlook", "outlook"), ("Word", "word"), ("pandoc", "pandoc")):
        seg.append(f"{nome} {'✓' if chiave in deps else '✗'}")
    return " · ".join(seg)


def verifica_disponibile(azione: A.Azione) -> str | None:
    """Motivo per cui l'azione non si può lanciare qui e ora (ruolo, dipendenze), o None."""
    return A.disponibile(azione, master=state.MASTER, deps=state.DEPS)


def _pannello():
    # a livello di pagina, non dentro il dialogo che contiene il pulsante: chiudere quel dialogo non deve
    # smontare il pannello con l'esito
    with context.client.content:
        with ui.dialog() as d, ui.card().classes('w-[760px] max-w-full'):
            titolo = ui.label().classes('font-bold')
            log = ui.log(max_lines=2000).classes('w-full h-96 font-mono text-xs')
            esito = ui.label().classes('text-sm')
            finali = ui.row()
            with ui.row():
                interrompi = ui.button('Interrompi', icon='stop', on_click=lambda: None).props('flat color=red-9')
                ui.button('Chiudi', on_click=d.close).props('flat')
    return d, titolo, log, esito, finali, interrompi


def _lancia(azione: A.Azione, cmd: list[str], rilascio, pannello, bottone, dopo: Callable[[int, ui.log], None] | None = None) -> None:
    d, titolo, log, esito, finali, interrompi = pannello
    motivo = verifica_disponibile(azione)
    if motivo:
        ui.notify(f'{azione.titolo}: {motivo}', type='warning')
        return
    try:
        run = esecutore.avvia(azione.id, cmd, rilascio=rilascio)
    except esecutore.EsecuzioneInCorso as e:
        ui.notify(f"Un'azione è già in corso: {e}", type='warning')
        return
    except RuntimeError as e:
        ui.notify(str(e), type='negative', close_button=True)
        return
    titolo.set_text(azione.titolo)
    log.clear()
    esito.set_text('')
    finali.clear()
    interrompi.on_click(lambda: run.interrompi())
    interrompi.enable()
    d.open()
    bottone.disable()

    avvisi: list[str] = []

    def _push(riga: str) -> None:
        log.push(riga)
        if riga.lstrip().startswith(('WARN', 'ATTENZIONE')):
            avvisi.append(riga.strip())

    def tick():
        while not run.righe.empty():
            _push(run.righe.get_nowait())
        if not run.attivo():
            while not run.righe.empty():          # ultime righe arrivate insieme alla fine
                _push(run.righe.get_nowait())
            for a in avvisi:                      # gli avvisi degli script (es. email mancanti) non vanno persi nel log
                ui.notify(a, type='warning', close_button=True, timeout=0)
            timer.deactivate()
            bottone.enable()
            interrompi.disable()
            if run.exit_code == 0:
                esito.set_text(f'Completata in {run.durata_s} s.')
                esito.classes(replace='text-sm text-green-800')
            else:
                esito.set_text(f'Terminata con errori (exit {run.exit_code}).')
                esito.classes(replace='text-sm text-red-800')
            if dopo:
                dopo(run.exit_code, log)
    timer = ui.timer(0.3, tick)


def pulsante_azione(azione: A.Azione, ctx_base: dict | None = None, *, rilascio: str | None = None,
                    files_rilascio: Callable[[str], list[Path]] | None = None, props: str = 'dense outline',
                    ctx_fn: Callable[[], dict | None] | None = None,
                    dopo: Callable[[int, ui.log], None] | None = None):
    """Pulsante che esegue un'azione del catalogo: disabilitato con il motivo se non disponibile; dialogo
    dei campi se l'azione ne ha; conferma o anteprima (due passi); pannello con l'output.
    ctx_fn: calcola il contesto al clic (dialoghi dedicati); None da ctx_fn = non eseguire."""
    motivo = verifica_disponibile(azione)
    pannello = _pannello()
    idx = state.get_index()

    def ricarica(_exit: int, _log) -> None:
        if azione.ricarica and rilascio:
            r = idx.rilascio(rilascio)
            if r:
                for g in azione.ricarica:
                    idx.reload(list(r.path.parent.glob(g)))
        if dopo:
            dopo(_exit, _log)

    def esegui(ctx: dict) -> None:
        ctx_tot = {**(ctx_base or {}), **ctx}
        if azione.due_passi:
            def dopo_anteprima(exit_code: int, _log) -> None:
                if exit_code != 0:
                    return                      # anteprima fallita: niente "Applica davvero"
                finali = pannello[4]
                with finali:
                    ui.button('Applica davvero', icon='check', on_click=lambda: (
                        finali.clear(), _lancia(azione, A.comando_applica(azione, ctx_tot), rilascio, pannello, bottone, ricarica))) \
                        .props('unelevated color=orange-9')
            _lancia(azione, A.comando(azione, ctx_tot), rilascio, pannello, bottone, dopo_anteprima)
            return
        cmd = A.comando(azione, ctx_tot)
        if azione.conferma:
            with ui.dialog() as c, ui.card():
                ui.label(azione.conferma).classes('text-sm')
                with ui.row():
                    ui.button('Procedi', on_click=lambda: (c.close(), _lancia(azione, cmd, rilascio, pannello, bottone, ricarica))) \
                        .props('unelevated color=orange-9')
                    ui.button('Annulla', on_click=c.close).props('flat')
            c.open()
        else:
            _lancia(azione, cmd, rilascio, pannello, bottone, ricarica)

    def al_clic() -> None:
        if ctx_fn is not None:
            ctx = ctx_fn()
            if ctx is not None:
                esegui(ctx)
            return
        if not azione.campi:
            esegui({})
            return
        with ui.dialog() as f, ui.card().classes('w-[520px] max-w-full'):
            ui.label(azione.titolo).classes('font-bold')
            widget: dict[str, object] = {}
            for c in azione.campi:
                if c.tipo == 'scelta':
                    piano = idx.piano(idx.anno_default())
                    opz = list(c.opzioni) or (sorted(piano.rilasci) if (c.nome == 'codice' and piano) else [])
                    widget[c.nome] = ui.select(opz, label=c.etichetta, value=c.default or None).classes('w-full')
                elif c.tipo == 'file_rilascio':
                    opz = {str(p): p.name for p in (files_rilascio(c.pattern_file) if files_rilascio else [])}
                    widget[c.nome] = ui.select(opz, label=c.etichetta, multiple=not c.obbligatorio).classes('w-full')
                elif c.tipo == 'testo_lungo':
                    widget[c.nome] = ui.textarea(c.etichetta, value=c.default).classes('w-full')
                else:
                    widget[c.nome] = ui.input(c.etichetta, value=c.default).classes('w-full')

            def conferma_campi() -> None:
                ctx = {}
                for c in azione.campi:
                    v = widget[c.nome].value
                    if c.obbligatorio and not v:
                        ui.notify(f'{c.etichetta}: obbligatorio', type='warning')
                        return
                    ctx[c.nome] = v if v is not None else ([] if c.tipo == 'file_rilascio' and not c.obbligatorio else '')
                f.close()
                esegui(ctx)
            with ui.row():
                ui.button('Esegui', on_click=conferma_campi).props('unelevated')
                ui.button('Annulla', on_click=f.close).props('flat')
        f.open()

    bottone = ui.button(azione.titolo, on_click=al_clic).props(props)
    if motivo:
        bottone.disable()
        bottone.tooltip(motivo)
    elif esecutore.in_corso():
        bottone.disable()
        bottone.tooltip("un'azione è in corso")
    return bottone
