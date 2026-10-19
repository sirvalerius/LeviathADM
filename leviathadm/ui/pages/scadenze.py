"""Scadenze: le quattro sezioni di Scadenze.md, sola lettura."""
from __future__ import annotations
from nicegui import ui

from leviathadm.ui.shell import shell
from leviathadm.vault import cruscotto as C

COLONNE = [{'name': k, 'label': l, 'field': k, 'align': 'left'} for k, l in
           (('codice', 'Rilascio'), ('tipo', 'Tipo'), ('data_fmt', 'Data'), ('delta', 'Δ'), ('note', 'Note'))]
_CHIAVI = ('codice', 'tipo', 'data_fmt', 'delta', 'note')


def righe_tabella(entries: list[dict]) -> list[dict]:
    """Solo chiavi stringa: ui.table serializza in JSON (niente date). `id` univoco per riga
    (un rilascio può avere più scadenze)."""
    return [{'id': i, **{k: e[k] for k in _CHIAVI}} for i, e in enumerate(entries)]


def render_scadenze() -> None:
    with shell('Scadenze'):
        try:
            sezioni = C.scadenze()
        except Exception as e:  # noqa: BLE001 — un file malformato non deve dare 500
            ui.label(f'Errore nella lettura delle scadenze: {type(e).__name__}: {e}').classes('text-red-800')
            return
        for chiave, etichetta in C.ETICHETTE_SCADENZE.items():
            with ui.card().classes('w-full lv-card shadow-none'):
                ui.label(etichetta).classes('font-bold text-slate-700')
                righe = righe_tabella(sezioni[chiave])
                if not righe:
                    ui.label('Nessuna.').classes('text-sm text-slate-500 italic')
                    continue
                t = ui.table(columns=COLONNE, rows=righe, row_key='id').classes('w-full').props('dense flat')
                t.add_slot('body-cell-codice', '''<q-td :props="props">
                    <a :href="'/rilascio/' + props.value" class="text-blue-900">{{ props.value }}</a></q-td>''')
