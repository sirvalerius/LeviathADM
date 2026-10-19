"""Stato invii: matrice rilascio × fase, celle P/D con link ai resoconti."""
from __future__ import annotations
import html
from pathlib import Path

from nicegui import ui

from leviathadm.ui import state
from leviathadm.ui.shell import shell
from leviathadm.vault import cruscotto as C
from leviathadm.vault.paths import nota_id
import build_stato_invii


def celle(matrix: dict, colonne: list[str], root: Path) -> list[dict]:
    righe = []
    for codice in sorted(matrix):
        storico = any(v.get('rinominato') for vs in matrix[codice].values() for v in vs)
        r = {'codice': codice, 'storico': storico}
        for fase in colonne:
            r[fase] = [{'testo': build_stato_invii._cell_text([v]), 'href': f'/resoconto/{nota_id(root, v["path"])}'}
                       for v in matrix[codice].get(fase, [])]
        righe.append(r)
    return righe


def render_stato_invii() -> None:
    idx = state.get_index()
    with shell('Stato invii'):
        try:
            matrix, colonne = C.stato_invii()
        except Exception as e:  # noqa: BLE001
            ui.label(f'Errore nella lettura: {type(e).__name__}: {e}').classes('text-red-800')
            return
        ui.label('P = provvisorio inviato · D = definitivo inviato (➖ saltato, — non ancora dovuto)') \
            .classes('text-xs text-slate-500')
        # tabella HTML intera: ui.element('thead') + ui.html non rende i <th> (NiceGUI avvolge in <div>)
        ui.html(html_tabella(celle(matrix, colonne, idx.root), colonne))


def html_tabella(righe: list[dict], colonne: list[str]) -> str:
    th = ''.join(f'<th class="text-left px-2 py-1">{html.escape(h)}</th>' for h in ['Rilascio'] + colonne)
    out = [f'<table class="w-full text-sm lv-card"><thead><tr>{th}</tr></thead><tbody>']
    for r in righe:
        cod = html.escape(r['codice'])
        celle_html = [f'<td class="px-2 py-1 whitespace-nowrap"><a class="text-blue-900" href="/rilascio/{cod}">{cod}</a>'
                      + (' <span class="text-xs text-slate-500">(storico)</span>' if r['storico'] else '') + '</td>']
        for fase in colonne:
            voci = ' / '.join(f'<a class="text-slate-800 no-underline" href="{html.escape(v["href"])}">{html.escape(v["testo"])}</a>'
                              for v in r[fase]) or '<span class="text-slate-400">—</span>'
            celle_html.append(f'<td class="px-2 py-1 whitespace-nowrap">{voci}</td>')
        out.append('<tr class="border-t border-slate-200">' + ''.join(celle_html) + '</tr>')
    out.append('</tbody></table>')
    return ''.join(out)
