"""Da firmare: lettere di fine collaudo; due flag per lettera (in firma, protocollata)."""
from __future__ import annotations
from nicegui import ui

from leviathadm.ui.pages.bozze import _esegui
from leviathadm.ui.shell import shell
from leviathadm.vault import cruscotto as C
from leviathadm.vault import writers


def _riga(it: dict, bottone: str, stato: str, ok: str, extra: str = '') -> None:
    with ui.row().classes('w-full items-center gap-3 lv-riga'):
        ui.link(it['codice'], f"/rilascio/{it['codice']}").classes('text-blue-900 w-40')
        ui.label(it['label']).classes('grow')
        if extra:
            ui.label(extra).classes('text-xs text-slate-500')
        if stato == 'protocollata':
            ui.link('Modifica scheda', f"/rilascio/{it['codice']}/modifica").classes('text-xs text-blue-900')
        ui.button(bottone, icon='draw' if stato == 'in_firma' else 'verified', on_click=lambda _, it=it: _esegui(
            writers.segna_lettera, it['scheda'], it['field_base'], stato, it['mtime_ns'],
            ricarica=[it['scheda']], ok=ok)).props('dense outline')


def render_da_firmare() -> None:
    with shell('Da firmare'):
        try:
            da_mandare, in_firma = C.da_firmare()
        except Exception as e:  # noqa: BLE001 — un file malformato non deve dare 500
            ui.label(f'Errore nella lettura: {type(e).__name__}: {e}').classes('text-red-800')
            return
        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label('Da mandare in firma').classes('font-bold text-slate-700')
            ui.label('La cartella "da mandare in firma/<Lettera>/" con i PDF per Arcipelago la prepara il sync.') \
                .classes('text-xs text-slate-500')
            if not da_mandare:
                ui.label('Nessuna lettera in attesa.').classes('text-sm text-slate-500 italic')
            for it in da_mandare:
                _riga(it, 'Mandata in firma', 'in_firma', 'Lettera segnata in firma.',
                      'cartella firma pronta' if it['cartella_pronta'] else 'cartella firma: da preparare al sync')
        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label('In firma — attesa firma e protocollazione').classes('font-bold text-slate-700')
            ui.label('Dopo "Protocollata": inserisci numero e data di protocollo e la riga in ## Allegati protocolli '
                     'nella scheda (link "Modifica scheda").').classes('text-xs text-slate-500')
            if not in_firma:
                ui.label('Nessuna lettera in attesa.').classes('text-sm text-slate-500 italic')
            for it in in_firma:
                _riga(it, 'Protocollata', 'protocollata',
                      'Lettera protocollata: compila protocollo e tabella Allegati nella scheda.')
