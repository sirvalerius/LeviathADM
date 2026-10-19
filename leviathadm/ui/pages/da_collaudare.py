"""Da collaudare: punti con disponibilità ricevuta e collaudo non ancora svolto; registra la data effettiva."""
from __future__ import annotations
from nicegui import ui

from leviathadm.ui.pages.bozze import _esegui
from leviathadm.ui.shell import shell
from leviathadm.ui.widgets import campo_data, data_iso
from leviathadm.vault import cruscotto as C
from leviathadm.vault import writers


def render_da_collaudare() -> None:
    with shell('Da collaudare'):
        try:
            items = C.da_collaudare()
        except Exception as e:  # noqa: BLE001 — un file malformato non deve dare 500
            ui.label(f'Errore nella lettura: {type(e).__name__}: {e}').classes('text-red-800')
            return
        ui.label('Registra la data appena il collaudo si è davvero svolto: il punto esce dalla lista e dalle scadenze '
                 'tassative; le lettere di chiusura compaiono in Da firmare.').classes('text-xs text-slate-500')
        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label('Punti da collaudare').classes('font-bold text-slate-700')
            if not items:
                ui.label('Nessuno.').classes('text-sm text-slate-500 italic')
            for it in items:
                with ui.row().classes('w-full items-center gap-3 lv-riga'):
                    ui.link(it['codice'], f"/rilascio/{it['codice']}").classes('text-blue-900 w-40')
                    ui.label(f"previsto {it['previsto']}").classes('text-sm text-slate-600 w-40')
                    campo = campo_data('Data collaudo effettiva (AAAA-MM-GG o GG/MM/AAAA)', classes='w-72', conferma_weekend=True)

                    def registra(it=it, campo=campo):
                        iso = data_iso(campo.value or '')
                        if not iso:
                            ui.notify('Data non valida: usa AAAA-MM-GG o GG/MM/AAAA.', type='warning')
                            return
                        _esegui(writers.registra_collaudo, it['scheda'], iso, it['mtime_ns'],
                                ricarica=[it['scheda']], ok=f"Collaudo del {iso} registrato.")
                    ui.button('Registra', icon='event_available', on_click=registra).props('dense outline')
