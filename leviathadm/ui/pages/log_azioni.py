"""Log delle esecuzioni (azioni.jsonl): ultime 100, più recenti prima."""
from __future__ import annotations
from datetime import datetime

from nicegui import ui

from leviathadm.ui import state
from leviathadm.ui.shell import shell
from leviathadm.vault import azioni as A
from leviathadm.vault import esecutore

COLONNE = [{'name': k, 'label': l, 'field': k, 'align': 'left'} for k, l in
           (('quando', 'Quando'), ('azione', 'Azione'), ('rilascio', 'Rilascio'), ('esito', 'Esito'), ('durata', 'Durata'))]


def righe_log(voci: list[dict]) -> list[dict]:
    out = []
    for i, v in enumerate(voci):
        try:
            quando = datetime.fromisoformat(v.get('ts', '')).strftime('%d/%m/%Y %H:%M')
        except ValueError:
            quando = v.get('ts', '')
        az = A.CATALOGO.get(v.get('azione', ''))
        e = v.get('exit')
        out.append({'id': i, 'quando': quando, 'azione': az.titolo if az else v.get('azione', ''),
                    'rilascio': v.get('rilascio') or '', 'esito': 'ok' if e == 0 else f'errore (exit {e})',
                    'durata': f"{v['durata_s']} s" if v.get('durata_s') is not None else '',
                    'coda': '\n'.join(v.get('coda') or [])})
    return out


def render_log() -> None:
    idx = state.get_index()
    with shell('Log azioni'):
        righe = righe_log(esecutore.log_leggi(idx.root))
        if not righe:
            ui.label('Nessuna esecuzione registrata.').classes('text-slate-600')
            return
        t = ui.table(columns=COLONNE, rows=righe, row_key='id', pagination=25).classes('w-full lv-card').props('dense flat')
        t.add_slot('body', r'''<q-tr :props="props"><q-td v-for="col in props.cols" :key="col.name" :props="props">{{ col.value }}</q-td></q-tr>
            <q-tr v-if="props.row.coda" :props="props"><q-td colspan="100%"><pre class="text-xs whitespace-pre-wrap">{{ props.row.coda }}</pre></q-td></q-tr>''')
