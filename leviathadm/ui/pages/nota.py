"""Rendering in sola lettura di qualunque nota del vault, con wikilink risolti e backlink."""
from __future__ import annotations
from collections.abc import Callable

from nicegui import ui

from leviathadm.ui import state
from leviathadm.ui.shell import shell
from leviathadm.vault.models import Nota
from leviathadm.vault.parsers import _WIKI_RE


def _rotta(n: Nota) -> str:
    if n.tipo == 'rilascio':
        return f'/rilascio/{n.frontmatter.get("codice_rilascio", n.path.stem)}'
    return f'/nota/{n.id}'


def converti_wikilink(corpo: str, risolvi: Callable[[str], Nota | None]) -> str:
    def sost(m):
        bang, target, alias = m.group(1), m.group(2).strip(), (m.group(3) or '').strip()
        if bang:
            return f'*(allegato: {target})*'
        n = risolvi(target)
        if n is None:
            return f'**{alias or target}** (non trovato)'
        return f'[{alias or target}]({_rotta(n)})'
    return _WIKI_RE.sub(sost, corpo)


def render_nota(id: str) -> None:
    idx = state.get_index()
    n = idx.nota(id)
    with shell(n.titolo if n else 'Nota'):
        if n is None:
            ui.icon('search_off', size='lg').classes('text-slate-400')
            ui.label('Nota non trovata.').classes('text-lg text-slate-700')
            ui.link('Torna ai rilasci', '/').classes('text-blue-900')
            return
        with ui.row().classes('items-center gap-2'):
            ui.badge(n.tipo).props('outline')
            ui.label(n.path.relative_to(idx.root).as_posix()).classes('text-xs text-slate-500 font-mono')
            for t in n.tag:
                ui.badge(f'#{t}', color='slate-6').props('outline')
        if n.frontmatter:
            with ui.expansion('Proprietà', icon='tune').classes('w-full lv-card'):
                with ui.grid(columns=2).classes('gap-x-6 gap-y-1'):
                    for k, v in n.frontmatter.items():
                        ui.label(k).classes('text-xs text-slate-500')
                        ui.label(v or '—').classes('text-sm')
        ui.markdown(converti_wikilink(n.corpo, idx.risolvi),
                    extras=['tables', 'fenced-code-blocks', 'task_list']) \
            .classes('w-full lv-card p-4')
        backlink = idx.backlink_di(n.id)
        with ui.expansion(f'Citato da · {len(backlink)}', icon='link').classes('w-full lv-card'):
            for b in backlink:
                ui.link(b.titolo, _rotta(b)).classes('block text-sm text-blue-900')
