"""Home: tabella densa dei rilasci del piano corrente."""
from __future__ import annotations
from nicegui import ui

from leviathadm.ui import state
from leviathadm.ui.shell import shell, vai
from leviathadm.ui.theme import STATO_COLORS, rango_stato

# larghezze fisse (percentuali della tabella, somma 100): la tabella è table-layout: fixed e le celle troncano
# con i puntini; il contenuto completo è nel tooltip (title) di ogni cella
_LARGHEZZE = {'n': 5, 'codice': 17, 'descrizione': 25, 'stato': 9, 'pm': 13, 'collaudo': 15, 'prossima': 16}
COLONNE = [
    {**c, 'style': f"width: {_LARGHEZZE[c['name']]}%", 'headerStyle': f"width: {_LARGHEZZE[c['name']]}%"} for c in [
        {'name': 'n', 'label': '#', 'field': 'n', 'align': 'right'},
        {'name': 'codice', 'label': 'Codice', 'field': 'codice', 'sortable': True, 'align': 'left'},
        {'name': 'descrizione', 'label': 'Rilascio', 'field': 'descrizione', 'sortable': True, 'align': 'left'},
        {'name': 'stato', 'label': 'Stato', 'field': 'stato', 'sortable': True, 'align': 'left',
         ':sort': '(a, b, ra, rb) => ra.stato_ord - rb.stato_ord'},   # ciclo di vita, non alfabetico
        {'name': 'pm', 'label': 'PM', 'field': 'pm', 'sortable': True, 'align': 'left'},
        {'name': 'collaudo', 'label': 'Collaudo prev./eff.', 'field': 'collaudo', 'sortable': True, 'align': 'left'},
        {'name': 'prossima', 'label': 'Prossima riunione', 'field': 'prossima', 'align': 'left'},
    ]]


def _fmt(d) -> str:
    return d.strftime('%d/%m/%Y') if d else '—'


def render_home(anno: str = '') -> None:
    idx = state.get_index()
    a = int(anno) if anno.isdigit() else idx.anno_default()
    with shell('Rilasci', anno=a):
        piano = idx.piano(a)
        rilasci = list(piano.rilasci.values()) if piano else []
        attivi = [r for r in rilasci if r.attivo]
        righe = [{
            'n': i, 'codice': r.codice, 'descrizione': r.descrizione_rilascio, 'stato': r.stato,
            'stato_ord': rango_stato(r.stato),
            'colore': STATO_COLORS.get(r.stato, 'grey-8'),
            'pm': r.frontmatter.get('pm', ''),
            'collaudo': f"{_fmt(r.data('data_collaudo_prevista'))} / {_fmt(r.data('data_collaudo_effettiva'))}",
            'prossima': r.prossima_riunione,
        } for i, r in enumerate(sorted(rilasci, key=lambda r: r.codice), start=1)]

        with ui.row().classes('w-full items-end gap-4'):
            ui.label(f'{len(attivi)} attivi · {len(rilasci) - len(attivi)} storici').classes('text-slate-600')
            ui.space()
            stati = sorted({r.stato for r in rilasci}, key=rango_stato)
            filtro_stato = ui.select(stati, value=[], label='Stato (vuoto = tutti)', multiple=True)                 .props('use-chips dense clearable').classes('w-72')
            filtro_testo = ui.input('Filtra').props('dense clearable').classes('w-64')

        if not righe:
            ui.label(f'Nessun rilascio in PO {a}. Verifica che il vault sia sincronizzato.') \
                .classes('text-slate-600 py-8')
            return

        tabella = ui.table(columns=COLONNE, rows=righe, row_key='codice', pagination={'rowsPerPage': 0}) \
            .classes('w-full lv-card lv-tabella-grande').props('flat')
        tabella.add_slot('body-cell', '''
            <q-td :props="props" :title="props.value" class="lv-ellissi">{{ props.value }}</q-td>''')
        tabella.add_slot('body-cell-stato', '''
            <q-td :props="props" :title="props.value">
              <q-badge outline :color="props.row.colore">{{ props.value }}</q-badge>
            </q-td>''')
        filtro_testo.bind_value_to(tabella, 'filter')

        def applica_stato(e):
            scelti = set(e.value or [])
            tabella.rows = righe if not scelti else [x for x in righe if x['stato'] in scelti]
        filtro_stato.on_value_change(applica_stato)
        tabella.on('rowClick', lambda e: vai(f"/rilascio/{e.args[1]['codice']}"))
