"""Resoconto: lettura, Rigenera .docx, Riporta in bozza, link all'editor e al Verbale."""
from __future__ import annotations
from nicegui import run, ui

from leviathadm.ui import apri, state
from leviathadm.ui.shell import shell, vai
from leviathadm.vault import resoconti as R
from leviathadm.vault import writers
from leviathadm.vault.index import VaultIndex
from leviathadm.vault.loader import _RESOCONTO_RE
from leviathadm.vault.paths import nota_id

COLORE_STATO = {'bozza': 'grey-8', 'inviato': 'blue-9', 'definitivo': 'green-8'}


def carica_doc(idx: VaultIndex, nid: str):
    """(doc, rilascio, errore): errore non vuoto se la nota non esiste o non è un resoconto."""
    n = idx.nota(nid)
    if n is None:
        return None, None, f'Nessuna nota con id "{nid}".'
    m = _RESOCONTO_RE.match(n.path.stem)
    if m is None:
        return None, None, f'Non è un resoconto: {n.path.name}'
    r = idx.rilascio(m.group(1))
    try:
        doc = R.parse_resoconto_doc(n.path, n.path.read_text(encoding='utf-8'), n.path.stat().st_mtime_ns)
    except OSError as e:
        return None, None, f'File non leggibile: {e}'
    return doc, r, ''


def stato_doc(doc: R.ResocontoDoc) -> str:
    fm = doc.frontmatter
    if fm.get('definitivo_inviato', '').lower() == 'true':
        return 'definitivo'
    if fm.get('inviato', '').lower() == 'true' or doc.path.parent.name == 'inviati':
        return 'inviato'
    return 'bozza'


def render_resoconto(nid: str) -> None:
    idx = state.get_index()
    doc, r, err = carica_doc(idx, nid)
    with shell('Resoconto'):
        if err:
            ui.label(err).classes('text-lg text-slate-700')
            ui.link('Torna ai rilasci', '/').classes('text-blue-900')
            return
        stato, in_inviati = stato_doc(doc), doc.path.parent.name == 'inviati'
        codice = r.codice if r else doc.frontmatter.get('codice_rilascio', '')

        with ui.dialog() as conferma, ui.card():
            ui.label('Riportare il resoconto in bozza?').classes('font-bold')
            ui.label('Sposta .md/.docx/.pdf fuori da inviati/, elimina il .msg già inviato, imposta inviato: false, '
                     'svuota la scadenza e segna ❌ nella scheda. Dopo le correzioni: "Rigenera .docx", poi il sync '
                     'genera il nuovo .msg (per il collaudo telematico riallega a mano il documento di analisi).') \
                .classes('text-sm text-slate-600')
            with ui.row():
                ui.button('Riporta in bozza', on_click=lambda: rettifica()).props('unelevated color=orange-9')
                ui.button('Annulla', on_click=conferma.close).props('flat')

        def rettifica():
            if r is None:
                ui.notify('Scheda del rilascio non trovata: impossibile aggiornare la tabella Riunioni.',
                          type='negative', close_button=True)
                return
            try:
                nuovo = writers.riporta_in_bozza(doc.path, r.path)
            except (OSError, ValueError) as e:
                ui.notify(f'Rettifica non riuscita: {e}', type='negative', close_button=True)
                return
            idx.reload([doc.path, nuovo, r.path])
            vai(f'/resoconto/{nota_id(idx.root, nuovo)}/modifica')

        async def rigenera():
            ui.notify('Generazione .docx in corso…', type='info')
            try:
                out, _ = await run.io_bound(writers.rigenera_docx, doc.path, doc.mtime_ns)
            except writers.ConflittoModifica as e:
                ui.notify(str(e), type='negative',
                          close_button=True)
                return
            except Exception as e:  # noqa: BLE001 — l'errore va mostrato, non nascosto
                ui.notify(f'Generazione fallita: {e}', type='negative', close_button=True)
                return
            idx.reload([doc.path])
            ui.notify(f'Generato {out.name} (data compilazione = oggi). Il sync rigenererà il .msg.', type='positive')
            ui.navigate.reload()

        with ui.row().classes('w-full items-center gap-3'):
            ui.label(doc.titolo).classes('text-xl font-bold text-slate-800')
            ui.badge(stato, color=COLORE_STATO[stato]).props('outline')
            ui.space()
            if in_inviati:
                ui.button('Riporta in bozza', icon='undo', on_click=conferma.open).props('outline color=orange-9')
            elif doc.ha_sezioni:
                ui.button('Modifica', icon='edit', on_click=lambda: vai(f'/resoconto/{nid}/modifica')).props('outline')
                # Rigenera solo su bozze con sezioni: su un archiviato altererebbe l'archivio (regola di rettifica),
                # su un export docx2md produrrebbe un Word vuoto sopra quello ufficiale
                ui.button('Rigenera .docx', icon='description', on_click=rigenera).props('outline')
            mail = apri.file_mail(doc.path)
            if mail:
                ui.button('Apri in Outlook', icon='mail', on_click=lambda m=mail: apri.apri_in_outlook(m)).props('outline')
            ui.button('Apri cartella', icon='folder_open', on_click=lambda p=doc.path: apri.apri_cartella(p)).props('flat')
            ui.button('Nota grezza', icon='code', on_click=lambda: vai(f'/nota/{nid}')).props('flat')
        presenti = [e for e in ('.docx', '.msg', '.pdf') if doc.path.with_suffix(e).exists()]
        with ui.row().classes('items-center gap-3 text-xs text-slate-500'):
            if r:
                ui.link(f'{codice} · {r.descrizione_rilascio}', f'/rilascio/{codice}').classes('text-blue-900')
            ui.label(f"{doc.frontmatter.get('tipo_riunione', '')} · {doc.frontmatter.get('data_riunione', '')}")
            ui.label(' · '.join(presenti) or 'nessun allegato').classes('font-mono')
            if doc.is_collaudo and r and r.verbali:
                ui.link('Verbale di Collaudo', f'/verbale/{nota_id(idx.root, r.verbali[-1])}').classes('text-blue-900')
        if doc.problemi:
            ui.label('; '.join(doc.problemi)).classes('text-xs text-amber-800')
        if not doc.ha_sezioni:
            ui.markdown(doc.pre + doc.footer, extras=['tables'])
            return
        sezioni_lettura(doc)


def sezioni_lettura(doc: R.ResocontoDoc) -> None:
    """Le sezioni del resoconto in sola lettura (pagina del resoconto e pannello del ciclo di vita)."""
    for s in doc.sezioni:
        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label(s.heading).classes('font-bold text-slate-700')
            ui.markdown(s.inner or '*(vuota)*', extras=['tables'])
