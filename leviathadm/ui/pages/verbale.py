"""Verbale di Collaudo: verifiche con esito a tre stati, esito complessivo; salva riscrivendo le 3 sezioni."""
from __future__ import annotations
from nicegui import ui

from leviathadm.ui import state
from leviathadm.ui.shell import shell, vai
from leviathadm.ui.widgets import campo_data
from leviathadm.vault import resoconti as R
from leviathadm.vault import writers

ESITI = ['', 'Superato', 'Non superato']


def render_verbale(nid: str) -> None:
    idx = state.get_index()
    n = idx.nota(nid)
    with shell('Verbale di Collaudo'):
        if n is None or 'Verbale di Collaudo' not in n.path.stem:
            ui.label('Verbale non trovato.').classes('text-lg text-slate-700')
            ui.link('Torna ai rilasci', '/').classes('text-blue-900')
            return
        v = R.parse_verbale(n.path, n.path.read_text(encoding='utf-8'), n.path.stat().st_mtime_ns)
        codice = v.frontmatter.get('codice_rilascio', '')
        with ui.row().classes('w-full items-center gap-3'):
            ui.label(n.titolo).classes('text-xl font-bold text-slate-800')
            ui.space()
            if codice:
                ui.link(codice, f'/rilascio/{codice}').classes('text-blue-900')
            ui.button('Nota grezza', icon='code', on_click=lambda: vai(f'/nota/{nid}')).props('flat')
        if v.problemi:
            ui.label('; '.join(v.problemi)).classes('text-xs text-amber-800')
        righe: list[dict] = []
        box = ui.column().classes('w-full gap-2')

        def render() -> None:
            box.clear()
            righe.clear()
            with box:
                for ver in v.verifiche:
                    with ui.card().classes('w-full lv-card shadow-none'):
                        with ui.row().classes('w-full items-center no-wrap gap-2'):
                            ui.label(f'{ver.n}.').classes('text-slate-500 w-8')
                            nome = ui.input(value=ver.nome).props('dense outlined').classes('grow')
                            opz = ESITI + ([ver.esito] if ver.esito and ver.esito not in ESITI else [])
                            esito = ui.select(opz, value=ver.esito, label='Esito').props('dense').classes('w-44')
                        with ui.row().classes('w-full gap-2'):
                            data = campo_data('Data', value=ver.data, formato='it', classes='w-40', conferma_weekend=True)
                            tst = ui.input('Testato da', value=ver.testato_da).props('dense outlined').classes('w-72')
                            note = ui.input('Note / anomalie', value=ver.note).props('dense outlined').classes('grow')
                        righe.append(dict(n=ver.n, nome=nome, esito=esito, data=data, testato_da=tst, note=note))
        render()

        def leggi() -> None:
            v.verifiche = [R.Verifica(n=w['n'], nome=(w['nome'].value or '').strip(), esito=w['esito'].value or '',
                                      data=(w['data'].value or '').strip(), testato_da=(w['testato_da'].value or '').strip(),
                                      note=(w['note'].value or '').strip())
                           for w in righe if (w['nome'].value or '').strip()]
            v.esito_complessivo = compl.value or ''
            v.data_verbale, v.presenti, v.riserve = ((dv.value or '').strip(), (pr.value or '').strip(),
                                                     (ris.value or '').strip())

        def aggiungi() -> None:
            leggi()
            v.verifiche.append(R.Verifica(n=len(v.verifiche) + 1, nome=''))
            render()

        ui.button('Aggiungi verifica', icon='add', on_click=aggiungi).props('flat dense')
        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label('Esito complessivo').classes('font-bold text-slate-700')
            compl = ui.select([''] + R.ESITI_VERBALE, value=v.esito_complessivo, label='Esito').classes('w-56')
            dv = campo_data('Data verbale', value=v.data_verbale, formato='it', classes='w-48', props='', conferma_weekend=True)
            pr = ui.input('Presenti', value=v.presenti).classes('w-full')
            ris = ui.input('Riserve / azioni correttive', value=v.riserve).classes('w-full')

        def salva() -> None:
            leggi()
            try:
                writers.salva_verbale(v)
            except writers.ConflittoModifica as e:
                ui.notify(str(e), type='negative',
                          timeout=0, close_button=True)
                return
            idx.reload([v.path])
            ui.notify('Verbale salvato (riepilogo e dettaglio riallineati).', type='positive')
            vai(f'/verbale/{nid}')

        with ui.row().classes('gap-3'):
            ui.button('Salva', icon='save', on_click=salva).props('unelevated')
            ui.button('Annulla', on_click=lambda: vai(f'/rilascio/{codice}' if codice else '/')).props('flat')
