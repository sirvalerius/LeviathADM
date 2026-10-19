"""Layout comune: header, drawer, ricerca globale, quick switcher (Ctrl+K), banner aggiornamento."""
from __future__ import annotations
from contextlib import contextmanager

from nicegui import ui

from leviathadm.ui import riavvio, state, sync_panel
from leviathadm.ui.theme import apply_theme, cambia_tema
from leviathadm.vault import esecutore

ROTTE_PIANO = {'Scadenze': '/scadenze', 'Bozze da inviare': '/bozze', 'Da collaudare': '/da-collaudare',
               'Da firmare': '/da-firmare', 'Stato invii': '/stato-invii'}
PAGINE_NOTA = ['Rilasci', 'Riunioni', 'Punti aperti']   # restano pagine generate/manuali, rese come nota

# Chrome/Edge usano Ctrl+K per la barra degli indirizzi; ui.keyboard non fa preventDefault.
CTRL_K_SCRIPT = ("<script>document.addEventListener('keydown', e => {"
                 " if (e.ctrlKey && e.key.toLowerCase() === 'k') e.preventDefault(); });</script>")


def vai(path: str) -> None:
    ui.navigate.to(path)


def _id_pagina(anno: int, nome: str) -> str:
    return f'PO {anno}~{nome}'


def voci_drawer(idx, anno: int) -> list[tuple[str, str]]:
    """Le viste native sempre; le pagine nota solo se esistono nel vault."""
    voci = list(ROTTE_PIANO.items())
    for nome in PAGINE_NOTA:
        if idx.nota(_id_pagina(anno, nome)) is not None:
            voci.append((nome, f'/nota/{_id_pagina(anno, nome)}'))
    voci += [('Azioni', '/azioni'), ('Log azioni', '/log'), ('Manuale', '/manuale')]
    return voci


def _rotta_di(tipo: str, nid: str) -> str:
    if tipo == 'rilascio':
        return f'/rilascio/{nid.split("~")[-1]}'
    return f'/nota/{nid}'


def _risultati(query: str, box: ui.column, chiudi) -> None:
    idx = state.get_index()
    risultati = idx.search(query, limit=12)
    box.clear()
    with box:
        for r in risultati:
            with ui.row().classes('items-center gap-2 cursor-pointer lv-row w-full px-2 py-1') \
                    .on('click', lambda _, r=r: (chiudi(), vai(_rotta_di(r.tipo, r.id)))):
                ui.badge(r.tipo).props('outline')
                ui.label(r.titolo).classes('text-sm')
                if r.snippet:
                    ui.label(r.snippet).classes('text-xs text-slate-500 truncate')
        if not risultati:
            ui.label('Nessun risultato').classes('text-sm text-slate-500 px-2')


@contextmanager
def shell(titolo: str, *, anno: int | None = None):
    idx = state.get_index()
    anno = anno or idx.anno_default()
    tema = apply_theme()
    ui.add_head_html(CTRL_K_SCRIPT)
    versione_vista = idx.versione

    with ui.dialog() as palette, ui.card().classes('w-[640px] max-w-full'):
        ui.label('Vai a…').classes('text-xs text-slate-500')
        box = ui.column().classes('w-full gap-0')
        campo = ui.input(placeholder='Cerca rilasci, note, persone (Ctrl+K)') \
            .props('autofocus dense outlined debounce=200').classes('w-full')
        campo.on_value_change(lambda e: _risultati(e.value, box, palette.close))

    def on_key(e):
        if e.action.keydown and e.modifiers.ctrl and str(e.key).lower() == 'k':
            campo.set_value('')
            palette.open()
    ui.keyboard(on_key=on_key, ignore=[])

    with ui.header().classes('bg-slate-800 text-white items-center gap-3 px-4 py-2'):
        ui.button(icon='menu', on_click=lambda: drawer.toggle()).props('flat round color=white')
        ui.label('LeviathADM').classes('text-lg font-bold')
        ui.select(idx.anni() or [anno], value=anno, label='Piano',
                  on_change=lambda e: vai(f'/?anno={e.value}')).props('dense dark').classes('w-28')
        ui.label(titolo).classes('text-sm text-slate-200 truncate')
        ui.space()
        sync_panel.pulsante_sync()
        ui.button('Cerca  Ctrl+K', icon='search', on_click=palette.open).props('flat color=white')
        ui.button(icon='dark_mode', on_click=lambda: cambia_tema(tema)).props('flat round color=white') \
            .tooltip('Tema chiaro/scuro')
        ui.button(icon='refresh', on_click=lambda: (idx.load_all(), ui.navigate.reload())) \
            .props('flat round color=white').tooltip('Ricarica indice')

    with ui.left_drawer(value=True).classes('lv-drawer') as drawer:
        ui.link('Rilasci', '/').classes('block px-3 py-1 no-underline text-slate-800 font-medium')
        ui.separator()
        ui.label(f'PO {anno}').classes('text-xs text-slate-500 px-3 pt-2')
        for nome, href in voci_drawer(idx, anno):
            ui.link(nome, href).classes('block px-3 py-1 no-underline text-slate-700')
        ui.separator()
        ui.link('Anagrafica', '/anagrafica').classes('block px-3 py-1 no-underline text-slate-700')
        ui.link('Nuovo punto di piano', '/nuovo').classes('block px-3 py-1 no-underline text-blue-900')
        ui.separator()
        riavvio.pulsante_riavvio(state.PORTA)

    banner = ui.row().classes('w-full bg-amber-100 text-amber-900 px-4 py-2 items-center gap-3 hidden')
    with banner:
        ui.icon('sync')
        ui.label('Il vault è cambiato sul disco (sync o Obsidian).')
        ui.button('Ricarica', on_click=ui.navigate.reload).props('dense flat')

    blocco = ui.row().classes('w-full bg-blue-100 text-blue-900 px-4 py-2 items-center gap-3 hidden')
    with blocco:
        ui.icon('hourglass_top')
        blocco_testo = ui.label()

    def controlla():
        if idx.versione != versione_vista:
            banner.classes(remove='hidden')
        azione = esecutore.in_corso()
        if azione:
            blocco_testo.set_text(f'Azione in corso: {azione}. Le modifiche sono sospese finché non termina.')
            blocco.classes(remove='hidden')
        else:
            blocco.classes(add='hidden')
    ui.timer(1.0, controlla)

    # larghezza piena (tetto a 1800px per gli schermi ultra-larghi): le tabelle hanno bisogno di spazio
    with ui.column().classes('w-full max-w-[1800px] mx-auto px-6 py-4 gap-4'):
        yield
