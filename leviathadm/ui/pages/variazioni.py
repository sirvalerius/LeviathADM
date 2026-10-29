"""Dialogo "Registra variazione": riga in ## Variazioni della scheda (date o effort su una fase) e, per le date,
data prevista della fase aggiornata nel frontmatter (writers.registra_variazione; allineato alla web 81_ui_variazioni.js)."""
from __future__ import annotations
from datetime import date

from nicegui import ui

from leviathadm.ui.pages.bozze import _esegui
from leviathadm.ui.widgets import campo_data, data_iso
from leviathadm.vault import writers
from leviathadm.vault.models import Rilascio

ETICHETTE = {'Date': ('Da (data prevista attuale; vuoto = quella della scheda)', 'A (nuova data prevista)'),
             'Effort': ('Da (effort attuale, gg/uomo)', 'A (nuovo effort, gg/uomo)')}


def dialogo_variazione(r: Rilascio) -> ui.dialog:
    fm = r.frontmatter
    ultimo = f'[[{r.resoconti[-1].stem}]]' if r.resoconti else ''
    with ui.dialog() as d, ui.card().classes('w-[640px] max-w-full'):
        ui.label(f'Registra variazione — {r.codice}').classes('text-lg font-bold')
        ui.label('Una riga nel registro Variazioni della scheda. Per le date, la data prevista della fase viene '
                 'aggiornata al nuovo valore (quello vecchio resta nella colonna "Da").').classes('text-xs text-slate-500')
        with ui.row().classes('w-full gap-3 flex-wrap'):
            data = campo_data('Data della variazione', date.today().isoformat(), classes='w-48')
            fase = ui.select(list(writers.FASI_VARIAZIONE), label='Fase', value='Collaudo').classes('w-40').props('dense outlined')
            tipo = ui.select(list(writers.TIPI_VARIAZIONE), label='Tipo', value='Date').classes('w-32').props('dense outlined')
        with ui.row().classes('w-full gap-3 flex-wrap'):
            da = ui.input(ETICHETTE['Date'][0], value=fm.get('data_collaudo_prevista', '')).classes('flex-1').props('dense outlined')
            a = ui.input(ETICHETTE['Date'][1]).classes('flex-1').props('dense outlined')
        motivo = ui.input('Motivo', placeholder="es. slittamento dell'analisi SOGEI").classes('w-full').props('dense outlined')
        fonte = ui.input('Fonte (resoconto, protocollo, mail)', value=ultimo).classes('w-full').props('dense outlined')

        def aggiorna(_=None) -> None:
            e_date = tipo.value == 'Date'
            da.value = fm.get(writers.FASI_VARIAZIONE[fase.value], '') if e_date else ''
            da.props(f'label="{ETICHETTE[tipo.value][0]}"')
            a.props(f'label="{ETICHETTE[tipo.value][1]}"')
        fase.on_value_change(aggiorna)
        tipo.on_value_change(aggiorna)

        def registra() -> None:
            iso = data_iso(data.value or '')
            if not iso:
                ui.notify('Data della variazione non valida: usa AAAA-MM-GG o GG/MM/AAAA.', type='warning')
                return
            v_da, v_a = (da.value or '').strip(), (a.value or '').strip()
            if tipo.value == 'Date':
                v_da = data_iso(v_da) or v_da
                v_a = data_iso(v_a) or v_a
            _esegui(writers.registra_variazione, r.path, iso, fase.value, tipo.value, v_da, v_a,
                    (motivo.value or '').strip(), (fonte.value or '').strip(), r.mtime_ns,
                    ricarica=[r.path], ok=f'Variazione registrata nella scheda {r.codice}.')
            d.close()
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Chiudi', on_click=d.close).props('flat')
            ui.button('Registra', icon='edit_calendar', on_click=registra).props('unelevated')
    return d
