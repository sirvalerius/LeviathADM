"""Carica fonti: trascritti (.docx/.md/.vtt), CSV presenze, PDF → _fonti/AAAAMMGG <Fase>/; conversione, Anagrafica, riga Riunioni."""
from __future__ import annotations
from nicegui import events, ui

from leviathadm.ui import state
from leviathadm.ui.widgets import campo_data, data_iso
from leviathadm.vault import fonti as F
from leviathadm.vault import writers
from leviathadm.vault.index import VaultIndex
from leviathadm.vault.models import Rilascio
from leviathadm.vault.resoconti import fase_tabella


def processa(idx: VaultIndex, r: Rilascio, data_iso_: str, fase_tab: str, files: list[tuple[str, bytes]], *,
             sovrascrivi: set[str], deps: set[str]) -> list[str]:
    """Salva ogni file, converte i trascritti, importa le presenze, completa la riga Riunioni. Un messaggio per esito."""
    msg: list[str] = []
    trascritto: str | None = None
    toccati = []
    for nome, dati in files:
        try:
            e = F.salva_fonte(r.path.parent, data_iso_, fase_tab, nome, dati, sovrascrivi=nome in sovrascrivi)
        except writers.ConflittoModifica as ex:       # azione in corso: niente scritture
            msg.append(str(ex))
            break
        if e.stato in ("rifiutato", "conflitto"):
            msg.append(f"{nome}: {e.stato} — {e.messaggio}")
            continue
        msg.append(f"{nome}: {e.stato}")
        suf = e.path.suffix.lower()
        if suf in (".docx", ".vtt", ".md"):
            try:
                md = F.converti_trascritto(e.path, deps=deps)
            except Exception as ex:  # noqa: BLE001 — pandoc/pypandoc: file salvato, conversione a mano
                md = None
                msg.append(f"{nome}: salvato ma non convertito ({ex}): convertilo a mano")
            else:
                if md is None:
                    msg.append(f"{nome}: salvato ma non convertito (pandoc assente): convertilo a mano")
            if md is not None:
                trascritto = trascritto or md.name
                toccati.append(md)
        elif suf == ".csv":
            try:
                p = F.importa_presenze(e.path)
                msg.append(f"{nome}: {len(p['adm'])} ADM, {len(p['sogei'])} SOGEI, {len(p['altri'])} altri; "
                           f"stub Anagrafica creati: {len(p['created'])}")
            except Exception as ex:  # noqa: BLE001 — CSV illeggibile: salvato, Anagrafica intatta
                msg.append(f"{nome}: salvato, ma non leggibile come presenze ({ex})")
    if trascritto:
        try:
            # mtime letto ADESSO: `r` è l'oggetto di quando la pagina è stata resa, un Salva precedente l'ha già cambiato
            if writers.completa_riga_riunione(r.path, data_iso_, fase_tab, trascritto, r.path.stat().st_mtime_ns):
                msg.append(f"Riga Riunioni {data_iso_} {fase_tab}: trascritto `{trascritto}`")
            toccati.append(r.path)
        except writers.ConflittoModifica as ex:
            msg.append(f"Riga Riunioni non aggiornata ({ex}): aggiungi il trascritto a mano")
    idx.reload(toccati)
    return msg


def dialogo_carica_fonti(idx: VaultIndex, r: Rilascio) -> ui.dialog:
    raccolti: dict[str, bytes] = {}
    with ui.dialog() as d, ui.card().classes('w-[640px] max-w-full'):
        ui.label('Carica fonti').classes('text-lg font-bold')
        with ui.row().classes('items-end gap-3'):
            data = campo_data('Data riunione (AAAA-MM-GG o GG/MM/AAAA)', classes='w-64', props='', conferma_weekend=True)
            fase = ui.select(['Startup', 'Analisi', 'SAL', 'Collaudo'], value='SAL', label='Fase').classes('w-40')
            n_sal = ui.number('Numero SAL', value=1, min=1, format='%.0f').classes('w-32')
            n_sal.bind_visibility_from(fase, 'value', value='SAL')
        elenco = ui.label('Nessun file').classes('text-xs text-slate-500')

        async def ricevi(e: events.UploadEventArguments) -> None:
            raccolti[e.file.name] = await e.file.read()        # NiceGUI 3: FileUpload asincrono
            elenco.set_text(', '.join(raccolti))
        ui.upload(on_upload=ricevi, multiple=True, auto_upload=True, max_file_size=F.MAX_BYTES,
                  label='Trascina qui trascritti (.docx/.md/.vtt), CSV presenze, PDF').classes('w-full')
        ui.label('Destinazione: _fonti/AAAAMMGG <Fase>/ del rilascio. I .docx/.vtt vengono convertiti in .md, il CSV aggiorna '
                 "l'Anagrafica, il trascritto entra nella riga Riunioni se la colonna è vuota.").classes('text-xs text-slate-500')
        esiti = ui.column().classes('w-full')

        def salva(sovrascrivi: set[str] = frozenset()) -> None:
            iso = data_iso(data.value or '')
            if not iso:
                ui.notify('Data non valida.', type='warning')
                return
            if not raccolti:
                ui.notify('Nessun file caricato.', type='warning')
                return
            fase_tab = fase_tabella(f"SAL {int(n_sal.value or 1)}" if fase.value == 'SAL' else fase.value)
            msg = processa(idx, r, iso, fase_tab, list(raccolti.items()), sovrascrivi=set(sovrascrivi), deps=state.DEPS)
            esiti.clear()
            conflitti = [m.split(':')[0] for m in msg if ': conflitto' in m]
            with esiti:
                for m in msg:
                    brutto = 'conflitto' in m or 'rifiutat' in m or 'non ' in m
                    ui.label(m).classes('text-sm ' + ('text-amber-800' if brutto else 'text-slate-700'))
                if conflitti:
                    ui.button(f'Sovrascrivi {len(conflitti)} file', on_click=lambda: salva(set(conflitti))) \
                        .props('dense outline color=orange-9')
        with ui.row().classes('gap-3'):
            ui.button('Salva', icon='save', on_click=lambda: salva()).props('unelevated')
            ui.button('Chiudi', on_click=d.close).props('flat')
    return d
