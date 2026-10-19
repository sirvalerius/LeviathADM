"""Anagrafica: elenco delle persone (Anagrafica/*.md) con filtro, scheda al clic, nuova persona."""
from __future__ import annotations
from nicegui import ui

from leviathadm.ui import state
from leviathadm.ui.shell import shell, vai
from leviathadm.ui.widgets import dialogo_nuova_persona
from leviathadm.vault.index import VaultIndex
from leviathadm.vault.models import Nota

COLONNE = [{'name': k, 'label': l, 'field': k, 'sortable': True, 'align': 'left'} for k, l in
           (('nome', 'Nome'), ('organizzazione', 'Org.'), ('direzione', 'Direzione'), ('ufficio', 'Ufficio'),
            ('email', 'Email'), ('ruolo_tipico', 'Ruolo tipico'))]


def persone(idx: VaultIndex) -> list[Nota]:
    return sorted((n for n in idx.note.values() if n.tipo == 'persona'), key=lambda n: n.titolo.lower())


def righe_anagrafica(note: list[Nota]) -> list[dict]:
    return [{'id': n.id, 'nome': n.titolo, **{k: n.frontmatter.get(k, '') for k in
            ('organizzazione', 'direzione', 'ufficio', 'email', 'ruolo_tipico')}} for n in note]


def render_anagrafica() -> None:
    idx = state.get_index()
    with shell('Anagrafica'):
        note = persone(idx)
        righe = righe_anagrafica(note)
        with ui.row().classes('w-full items-end gap-4'):
            ui.label(f'{len(righe)} persone').classes('text-slate-600')
            ui.space()
            filtro = ui.input('Filtra (nome, ufficio, email…)').props('dense clearable').classes('w-80')
            dlg = dialogo_nuova_persona(idx)
            ui.button('Nuova persona', icon='person_add', on_click=dlg.open).props('unelevated')
        ui.label('Le schede si creano anche in automatico dai CSV presenze (Carica fonti); qui si aggiungono a mano le persone '
                 'da usare nei ruoli delle schede rilascio.').classes('text-xs text-slate-500')
        t = ui.table(columns=COLONNE, rows=righe, row_key='id', pagination={'rowsPerPage': 0}) \
            .classes('w-full lv-card').props('dense flat')
        filtro.bind_value_to(t, 'filter')
        t.on('rowClick', lambda e: vai(f"/nota/{e.args[1]['id']}"))
