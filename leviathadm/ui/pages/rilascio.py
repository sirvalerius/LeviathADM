"""Dettaglio rilascio in sola lettura."""
from __future__ import annotations
from nicegui import ui

from datetime import date
from pathlib import Path

from leviathadm.ui import state
from leviathadm.ui.esecuzione_ui import pulsante_azione
from leviathadm.ui.pages import nuovo_resoconto
from leviathadm.ui.pages.carica_fonti import dialogo_carica_fonti
from leviathadm.ui.pages.convocazione import dialogo_convocazione, giorni_lavorativi_dopo, proponi_data_collaudo
from leviathadm.ui.pages.lettere import dialogo_lettere
from leviathadm.ui.pages.resoconto import carica_doc, sezioni_lettura
from leviathadm.ui.pages.resoconto_modifica import editor_resoconto
from leviathadm.ui.shell import shell, vai
from leviathadm.ui.theme import STATO_COLORS
from leviathadm.vault import azioni as A
from leviathadm.vault import writers
from leviathadm.vault.loader import resoconti_non_collegati
from leviathadm.vault.models import Rilascio
from leviathadm.vault.parsers import ha_vincoli_normativi
from leviathadm.vault.paths import nota_id


def files_rilascio(r: Rilascio, pattern: str) -> list[Path]:
    """File del rilascio che rispondono al pattern: root e, per i PDF, anche _fonti/."""
    d = r.path.parent
    trovati = set(d.glob(pattern))
    if pattern.endswith('.pdf'):
        trovati |= set(d.glob('_fonti/**/' + pattern))
    return sorted(trovati, key=lambda p: p.name.lower())

PROTOCOLLI = [('protocollo_analisi', 'Analisi'), ('protocollo_approvazione_analisi', 'Approvazione analisi'),
              ('protocollo_disponibilita_collaudo', 'Disponibilità a collaudo'),
              ('protocollo_collaudo', 'Collaudo'), ('protocollo_estensione_esercizio', 'Estensione esercizio')]
DATE = [('data_fine_analisi', 'Fine analisi'), ('data_disponibilita_collaudo', 'Disponibilità collaudo'),
        ('data_collaudo_prevista', 'Collaudo previsto'), ('data_collaudo_effettiva', 'Collaudo effettivo'),
        ('data_rilascio_prevista', 'Rilascio previsto'), ('data_rilascio_effettiva', 'Rilascio effettivo')]
ICONE_FASE = {'Startup': 'flag', 'Collaudo': 'verified'}
NUOVO = 'nuovo'   # nome dello step "+" in coda al ciclo di vita
COLORE_STATO_RESOCONTO = {'bozza': 'grey-8', 'inviato': 'blue-9', 'definitivo': 'green-8'}


def avanzamento_stato(r: Rilascio, oggi: date | None = None) -> dict | None:
    """{da, a, manuale} se lo stato suggerito dai fatti della scheda supera quello scritto (avanza_stato.suggerisci),
    altrimenti None. `manuale` = stato_manuale: true (solo badge, niente pulsante). Rinominato: mai."""
    import avanza_stato
    fm = r.frontmatter
    if (fm.get('stato') or '').strip() == avanza_stato.RINOMINATO:
        return None
    riunioni = [{'fase': m.fase, 'inviato': m.inviato} for m in r.riunioni]
    s = avanza_stato.suggerisci(fm, riunioni, oggi or date.today())
    if not s or avanza_stato.rango(s) <= avanza_stato.rango(r.stato):
        return None
    return {'da': r.stato, 'a': s, 'manuale': (fm.get('stato_manuale') or '').strip().lower() == 'true'}


def _icona(fase: str) -> str:
    if 'Analisi' in fase:
        return 'query_stats'
    if 'SAL' in fase:
        return 'timeline'
    return ICONE_FASE.get(fase.split(' ')[0], 'radio_button_unchecked')


def _campo(label: str, valore: str) -> None:
    with ui.column().classes('gap-0 min-w-40'):
        ui.label(label).classes('text-xs text-slate-500')
        ui.label(valore or '—').classes('text-sm text-slate-800')


def render_rilascio(codice: str) -> None:
    idx = state.get_index()
    r = idx.rilascio(codice)
    with shell(codice):
        if r is None:
            ui.icon('search_off', size='lg').classes('text-slate-400')
            ui.label(f'Nessun rilascio con codice "{codice}".').classes('text-lg text-slate-700')
            ui.link('Torna ai rilasci', '/').classes('text-blue-900')
            return
        fm = r.frontmatter
        with ui.row().classes('w-full items-center gap-3'):
            ui.label(r.descrizione_rilascio).classes('text-xl font-bold text-slate-800')
            ui.badge(r.stato, color=STATO_COLORS.get(r.stato, 'grey-8')).props('outline')
            av = avanzamento_stato(r)
            if av:
                ui.badge(f"→ {av['a']}", color='indigo-8').props('outline') \
                    .tooltip('Stato suggerito dai fatti registrati nella scheda'
                             + (' — avanzamento automatico bloccato da stato_manuale' if av['manuale'] else ''))
                if not av['manuale']:
                    def _avanza(a=av['a'], mtime=r.mtime_ns):
                        try:
                            writers.update_frontmatter(r.path, {'stato': a}, mtime)
                        except writers.ConflittoModifica as e:
                            ui.notify(str(e), type='negative', close_button=True)
                            return
                        idx.reload([r.path])
                        ui.notify(f'Stato avanzato: {r.stato or "(vuoto)"} → {a}', type='positive')
                        vai(f'/rilascio/{codice}')
                    ui.button('Avanza stato', icon='arrow_forward', on_click=_avanza).props('dense outline')
            if ha_vincoli_normativi(fm.get('vincoli_normativi', '')):
                ui.badge('Vincoli normativi', color='amber-9').props('outline')
            ui.space()
            dlg = nuovo_resoconto.dialogo(idx, r)
            ui.button('Nuovo resoconto', icon='note_add', on_click=dlg.open).props('unelevated')
            ui.button('Modifica scheda', icon='edit',
                      on_click=lambda: vai(f'/rilascio/{codice}/modifica')).props('outline')
        ui.label(f"{fm.get('codice_progetto', '')} · {fm.get('descrizione_progetto', '')}  →  "
                 f"{fm.get('codice_sottoprogetto', '')} · {fm.get('descrizione_sottoprogetto', '')}") \
            .classes('text-xs text-slate-500')
        if r.problemi:
            ui.label('Scheda incompleta: ' + '; '.join(r.problemi)).classes('text-xs text-amber-800')

        with ui.card().classes('w-full lv-card shadow-none'):
            with ui.row().classes('w-full gap-x-10 gap-y-3 flex-wrap'):
                _campo('PM', fm.get('pm', ''))
                _campo('RA', fm.get('ra', ''))
                _campo('RP', fm.get('rp', ''))
                _campo(f"Referente business ({fm.get('struttura_business', '')})", fm.get('referente_business', ''))
                _campo('Referente SOGEI', fm.get('referente_sogei', ''))
            ui.separator().classes('my-2')
            with ui.row().classes('w-full gap-x-10 gap-y-3 flex-wrap'):
                for campo, label in DATE:
                    _campo(label, fm.get(campo, ''))
            if fm.get('nota_variazione_date'):
                ui.label(f"Variazione date: {fm['nota_variazione_date']}").classes('text-xs text-amber-800 mt-2')
            if r.prossima_riunione:
                ui.separator().classes('my-2')
                with ui.row().classes('items-center gap-2'):
                    ui.icon('event').classes('text-slate-500')
                    ui.label(f'Prossima riunione: {r.prossima_riunione}').classes('text-sm text-slate-700')
            if r.team_raw:
                with ui.expansion('Team', icon='groups').classes('w-full'):
                    ui.markdown(r.team_raw, extras=['tables'])

        ui.label('Ciclo di vita').classes('text-lg font-bold text-slate-700')
        fasi = [m.fase for m in r.riunioni]
        resoconti_per_stem = {x.stem: x for x in r.resoconti}
        with ui.stepper(value=str(len(fasi) - 1) if fasi else NUOVO).classes('w-full lv-card')                 .props('header-nav animated flat') as stepper:
            for i, fase in enumerate(fasi):
                riunione = r.riunioni[i]
                with ui.step(str(i), title=fase, icon=_icona(fase)):
                    stato_invio = "inviato" if riunione.inviato else "da inviare"
                    ui.label(f'Riunione del {riunione.data} — resoconto {stato_invio}')                         .classes('text-sm text-slate-600')
                    res = resoconti_per_stem.get(riunione.resoconto_link)
                    if res:
                        with ui.row().classes('items-center gap-2'):
                            ui.badge(res.stato, color=COLORE_STATO_RESOCONTO[res.stato]).props('outline')
                            ui.link(res.stem, f'/resoconto/{nota_id(idx.root, res.path)}')                                 .classes('text-sm text-blue-900')
                            presenti = [e for e, ok in (('.docx', res.ha_docx), ('.msg', res.ha_msg),
                                                        ('.pdf', res.ha_pdf)) if ok]
                            ui.label(' · '.join(presenti)).classes('text-xs text-slate-500 font-mono')
                    elif riunione.resoconto_link:
                        ui.label(f'Resoconto non trovato: {riunione.resoconto_link}')                             .classes('text-sm text-amber-800')
                    if fase.startswith('Collaudo'):
                        if r.verbali:
                            ui.link('Verbale di Collaudo', f'/verbale/{nota_id(idx.root, r.verbali[-1])}')                                 .classes('text-sm text-blue-900')
                        else:
                            ui.label('Verbale assente (nasce dalla convocazione di collaudo)')                                 .classes('text-xs text-slate-500')
            with ui.step(NUOVO, title='+', icon='add'):
                ui.label('Aggiunge una riunione al ciclo di vita: compila il modulo qui sotto.')                     .classes('text-sm text-slate-600')
        pannello = ui.column().classes('w-full gap-3')

        def mostra(nome: str) -> None:
            """Sotto lo stepper: il modulo del "+" oppure il resoconto della fase scelta
            (editor se è una bozza, sola lettura se è già stato inviato)."""
            pannello.clear()
            with pannello:
                if nome == NUOVO:
                    with ui.card().classes('w-full lv-card shadow-none'):
                        ui.label('Nuova riunione').classes('font-bold text-slate-700')
                        ui.label('Lo scheletro nasce già compilato da scheda, Anagrafica e CSV presenze: '
                                 'restano da scrivere ARGOMENTI TRATTATI e AZIONI CONCORDATE.')                             .classes('text-xs text-slate-500')
                        nuovo_resoconto.form_nuovo(idx, r, dopo=lambda out, avvisi: ui.timer(
                            2.5 if avvisi else 0.3, ui.navigate.reload, once=True))
                    return
                riunione = r.riunioni[int(nome)]
                res = resoconti_per_stem.get(riunione.resoconto_link)
                if res is None:
                    ui.label(f'Resoconto non trovato: {riunione.resoconto_link}' if riunione.resoconto_link
                             else 'Nessun resoconto collegato a questa riunione.').classes('text-sm text-slate-500')
                    return
                nid = nota_id(idx.root, res.path)
                doc, _, err = carica_doc(idx, nid)
                if err:
                    ui.label(err).classes('text-sm text-amber-800')
                    return
                bloccato = res.path.parent.name == 'inviati' or not doc.ha_sezioni
                with ui.row().classes('items-center gap-2'):
                    ui.icon('lock' if bloccato else 'lock_open').classes('text-slate-500' if bloccato else 'text-green-800')
                    if res.path.parent.name == 'inviati':
                        ui.label('Inviato: sola lettura. Per correggerlo usa "Riporta in bozza" nella pagina del resoconto.')
                    elif bloccato:
                        ui.label('Ciclone sezioni standard: modificabile solo come nota grezza.')
                    else:
                        ui.label('Bozza: campi modificabili.')
                    ui.link('Apri pagina', f'/resoconto/{nid}').classes('text-sm text-blue-900')
                if bloccato:
                    sezioni_lettura(doc)
                else:
                    editor_resoconto(idx, nid, dopo_salva=lambda: mostra(nome), annulla=lambda: mostra(nome))
        stepper.on_value_change(lambda e: mostra(e.value))
        mostra(stepper.value)

        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label('Azioni').classes('font-bold text-slate-700')
            oggi = date.today()
            conv_s = dialogo_convocazione(idx, r, 'startup', giorni_lavorativi_dopo(oggi, 7).isoformat())
            conv_c = dialogo_convocazione(idx, r, 'collaudo', proponi_data_collaudo(r))
            with ui.row().classes('items-center gap-2 flex-wrap'):
                fonti_dlg = dialogo_carica_fonti(idx, r)
                ui.button('Carica fonti', icon='upload', on_click=fonti_dlg.open).props('dense outline')
                ui.button('Convocazione startup', icon='event', on_click=conv_s.open).props('dense outline')
                ui.button('Convocazione collaudo', icon='event', on_click=conv_c.open).props('dense outline')
                lett = dialogo_lettere(idx, r)
                ui.button('Lettere di fine collaudo', icon='description', on_click=lett.open).props('dense outline')
                pulsante_azione(A.CATALOGO['mail_resoconto'], {'codice': r.codice}, rilascio=r.codice,
                                files_rilascio=lambda g, r=r: files_rilascio(r, g))
                pulsante_azione(A.CATALOGO['prepara_firma'], {'codice': r.codice}, rilascio=r.codice)
                from leviathadm.ui import apri
                ui.button('Apri cartella', icon='folder_open', on_click=lambda p=r.path: apri.apri_cartella(p)).props('dense flat')
            ui.label('Le convocazioni sono bozze .eml da aprire e inviare; la mail resoconto è una bozza .msg (Outlook). '
                     'Nessuna mail viene inviata dall\'app.').classes('text-xs text-slate-500')

        altri = resoconti_non_collegati(r)
        if altri:
            with ui.expansion(f'Altri resoconti · {len(altri)} (non collegati alla tabella Riunioni)',
                              icon='description', value=True).classes('w-full lv-card'):
                for res in altri:
                    with ui.row().classes('items-center gap-2'):
                        ui.badge(res.stato, color=COLORE_STATO_RESOCONTO[res.stato]).props('outline')
                        ui.link(res.stem, f'/resoconto/{nota_id(idx.root, res.path)}').classes('text-sm text-blue-900')
                        ui.label(res.data_riunione.strftime('%d/%m/%Y') if res.data_riunione else '') \
                            .classes('text-xs text-slate-500')

        compilati = sum(1 for k, _ in PROTOCOLLI if fm.get(k, '').strip())
        with ui.expansion(f'Protocolli ADM · {compilati}/{len(PROTOCOLLI)}', icon='gavel').classes('w-full lv-card'):
            for campo, label in PROTOCOLLI:
                with ui.row().classes('w-full items-baseline gap-4 lv-riga'):
                    ui.label(label).classes('text-sm text-slate-500 w-48 shrink-0')
                    ui.label(fm.get(campo, '').strip() or '—').classes('text-sm')

        aperte = [a for a in r.azioni if not a.chiusa]
        with ui.expansion(f'Azioni · {len(aperte)} aperte, {len(r.azioni) - len(aperte)} chiuse',
                          icon='checklist', value=bool(aperte)).classes('w-full lv-card'):
            for a in r.azioni:
                with ui.row().classes('items-start gap-2 no-wrap lv-riga'):
                    ui.icon('check_circle' if a.chiusa else 'radio_button_unchecked') \
                        .classes('mt-0.5 ' + ('text-green-700' if a.chiusa else 'text-orange-700'))
                    suffisso = f'  (scadenza {a.scadenza:%d/%m/%Y})' if a.scadenza and not a.chiusa else ''
                    ui.label(a.testo_pulito + suffisso) \
                        .classes('text-sm ' + ('text-slate-500 line-through' if a.chiusa else 'text-slate-800'))

        with ui.expansion(f'Decisioni chiave · {len(r.decisioni)}', icon='history_edu').classes('w-full lv-card'):
            for d in r.decisioni:
                ui.label((f'{d.data:%d/%m/%Y} — ' if d.data else '') + d.testo).classes('text-sm text-slate-800')

        backlink = idx.backlink_di(r.id)
        with ui.expansion(f'Citato da · {len(backlink)}', icon='link').classes('w-full lv-card'):
            for n in backlink:
                ui.link(n.titolo, f'/nota/{n.id}').classes('block text-sm text-blue-900')
