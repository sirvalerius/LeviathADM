"""Bozze da inviare: approvazioni tacite scadute, bozze iniziali, convocazioni, definitivi — con azioni."""
from __future__ import annotations
from nicegui import ui

from leviathadm.ui import state
from leviathadm.ui.shell import shell
from leviathadm.vault import cruscotto as C
from leviathadm.vault import writers
from leviathadm.vault.paths import nota_id


def testo_conferma(b: dict) -> str:
    t = (f"Segnare {b['stem']} come inviato? Sposta .md/.docx/.msg in inviati/, imposta inviato: true, "
         "scadenza approvazione tacita = +5 giorni lavorativi, ✅ nella riga Riunioni della scheda.")
    if not b.get('has_msg'):
        t += " Attenzione: manca il .msg (la mail potrebbe non essere stata inviata da qui)."
    return t


def testo_conferma_convocazione(c: dict) -> str:
    return f"Segnare {c['stem']} come inviata? Sposta .eml/.ics in inviati/ e la toglie dalla lista."


def _esegui(fn, *args, ricarica: list, ok: str) -> None:
    """Esegue un'azione del cruscotto: errori in notifica, poi reload dell'indice e della pagina."""
    idx = state.get_index()
    try:
        esito = fn(*args)
    except writers.ConflittoModifica as e:
        ui.notify(str(e), type='negative', close_button=True)
        return
    except (FileExistsError, ValueError, PermissionError) as e:
        ui.notify(f'Operazione non eseguita: {e}', type='negative', close_button=True, timeout=0)
        return
    except OSError as e:   # errore a metà (spostamento iniziato): lo stato dei file va controllato
        ui.notify(f'Operazione interrotta, verifica i file del rilascio: {e}', type='negative', close_button=True, timeout=0)
        return
    idx.reload(ricarica + ([esito] if hasattr(esito, 'suffix') else []))
    ui.notify(ok, type='positive')
    ui.navigate.reload()


def _link_resoconto(idx, b: dict) -> str:
    return f"/resoconto/{nota_id(idx.root, b['path'])}" if b.get('path') else f"/rilascio/{b['codice']}"


def _vuoto(testo: str) -> None:
    ui.label(testo).classes('text-sm text-slate-500 italic')


def _riga_bozza(idx, b: dict) -> None:
    with ui.row().classes('w-full items-center gap-3 lv-riga'):
        ui.link(b['stem'], _link_resoconto(idx, b)).classes('text-blue-900 grow')
        ui.label(f"{b['codice']} · {b['tipo']} · {b['data']} · .docx {('⚠️ superato' if b.get('docx_superato') else '✅') if b['has_docx'] else '❌'} · "
                 f".msg {'✅' if b['has_msg'] else '❌'}").classes('text-sm text-slate-600 font-mono')
        with ui.dialog() as d, ui.card():
            ui.label(testo_conferma(b)).classes('text-sm')
            with ui.row():
                ui.button('Segna inviato', on_click=lambda: (d.close(), _esegui(
                    writers.archivia_bozza, b['path'], b['mtime_ns'],
                    ricarica=[b['path'], b['path'].parent / f"{b['path'].parent.name}.md"],
                    ok='Resoconto archiviato in inviati/.'))).props('unelevated color=orange-9')
                ui.button('Annulla', on_click=d.close).props('flat')
        ui.button('Segna inviato', icon='send', on_click=d.open).props('dense outline')


def render_bozze() -> None:
    idx = state.get_index()
    with shell('Bozze da inviare'):
        try:
            scadute = C.approvazioni_scadute()
            bozze, conv, definitivi = C.bozze()
        except Exception as e:  # noqa: BLE001 — un file malformato non deve dare 500
            ui.label(f'Errore nella lettura: {type(e).__name__}: {e}').classes('text-red-800')
            return

        if scadute:
            with ui.card().classes('w-full lv-card shadow-none border-amber-300'):
                ui.label('Approvazioni tacite scadute').classes('font-bold text-amber-900')
                ui.label('Registra data_approvazione; PDF e mail definitiva arrivano al prossimo sync del master.') \
                    .classes('text-xs text-slate-500')
                for a in scadute:
                    with ui.row().classes('w-full items-center gap-3 lv-riga'):
                        ui.link(a['stem'], f"/resoconto/{nota_id(idx.root, a['path'])}").classes('text-blue-900 grow')
                        ui.label(f"{a['tipo']} · {a['data']} · scaduta il {a['scadenza']}").classes('text-sm text-slate-600')
                        ui.button('Chiudi approvazione', icon='task_alt', on_click=lambda _, a=a: _esegui(
                            writers.chiudi_approvazione_tacita, a['path'], a['mtime_ns'], ricarica=[a['path']],
                            ok='Approvazione registrata: PDF e mail definitiva al prossimo sync del master.')) \
                            .props('dense outline')

        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label('Bozze iniziali').classes('font-bold text-slate-700')
            if not bozze:
                _vuoto('Nessuna bozza in attesa.')
            for b in bozze:
                if b['path'] is None:
                    ui.label(f"{b['stem']}: file non trovato (cartella rinominata?)").classes('text-sm text-amber-800')
                    continue
                _riga_bozza(idx, b)

        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label('Convocazioni da inviare').classes('font-bold text-slate-700')
            if not conv:
                _vuoto('Nessuna convocazione in attesa.')
            for c in conv:
                if c['path'] is None:
                    continue
                with ui.row().classes('w-full items-center gap-3 lv-riga'):
                    ui.label(c['stem']).classes('grow')
                    ui.label(f"{c['codice']} · Convocazione {c['tipo']} · {c['data']}").classes('text-sm text-slate-600')
                    with ui.dialog() as dc, ui.card():
                        ui.label(testo_conferma_convocazione(c)).classes('text-sm')
                        with ui.row():
                            ui.button('Segna inviata', on_click=lambda _, c=c, dc=dc: (dc.close(), _esegui(
                                writers.archivia_convocazione, c['path'], ricarica=[],
                                ok='Convocazione spostata in inviati/.'))).props('unelevated color=orange-9')
                            ui.button('Annulla', on_click=dc.close).props('flat')
                    ui.button('Segna inviata', icon='send', on_click=dc.open).props('dense outline')

        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label('Definitivi').classes('font-bold text-slate-700')
            if not definitivi:
                _vuoto('Nessun definitivo in attesa.')
            for x in definitivi:
                if x['path'] is None:
                    continue
                with ui.row().classes('w-full items-center gap-3 lv-riga'):
                    ui.link(x['stem'], _link_resoconto(idx, x)).classes('text-blue-900 grow')
                    ui.label(f"{x['codice']} · {x['tipo']} · {x['data']} · approvato {x['scadenza']} · "
                             f".msg {'✅' if x['has_msg'] else '❌'} · .pdf {'✅' if x['has_pdf'] else '❌'}") \
                        .classes('text-sm text-slate-600 font-mono')
                    ui.button('Segna definitivo inviato', icon='done_all', on_click=lambda _, x=x: _esegui(
                        writers.segna_definitivo_inviato, x['path'], x['mtime_ns'],
                        ricarica=[x['path']], ok='Definitivo segnato come inviato.')).props('dense outline')
