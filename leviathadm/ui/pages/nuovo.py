"""Wizard di creazione di una nuova scheda rilascio (delega a build_project_pages.write_release_page)."""
from __future__ import annotations
import re

from nicegui import ui

from leviathadm.ui import state
from leviathadm.ui.pages.rilascio_modifica import CAMPI_TEAM, valida_date_iso
from leviathadm.ui.shell import shell, vai
from leviathadm.ui.pages.anagrafica import persone
from leviathadm.ui.widgets import campo_data, campo_persona
from leviathadm.vault import writers

CODICE_RE = re.compile(r'ADM\d{3}-\d{2}-[0-9A-Z]{2}')


def render_nuovo() -> None:
    idx = state.get_index()
    anno = idx.anno_default()
    piano = idx.piano(anno)
    inputs = {}
    with shell('Nuovo punto di piano', anno=anno):
        def crea():
            cod = inputs['codice'].value.strip().upper()
            if not CODICE_RE.fullmatch(cod):
                ui.notify('Codice non valido: formato atteso ADMxxx-xx-xX (es. ADM953-01-0M).', type='warning')
                return
            if idx.rilascio(cod) is not None:
                ui.notify(f'{cod} esiste già: usa "Modifica scheda" dal dettaglio.', type='warning')
                return
            if not inputs['desc_rilascio'].value.strip():
                ui.notify('La descrizione del rilascio è obbligatoria.', type='warning')
                return
            date = {k: inputs[k].value.strip() for k in ('data_collaudo_prevista', 'data_rilascio_prevista')}
            err = valida_date_iso(date)
            if err:
                ui.notify(err, type='warning')
                return
            rel = {'cod_rilascio': cod, 'cod_sub': '-'.join(cod.split('-')[:2]),
                   'desc_progetto': inputs['desc_progetto'].value.strip(),
                   'desc_sub': inputs['desc_sub'].value.strip(),
                   'desc_rilascio': inputs['desc_rilascio'].value.strip(),
                   'vincoli_normativi': inputs['vincoli_normativi'].value,
                   **{k: inputs[k].value.strip() for k, _ in CAMPI_TEAM}, **date}
            try:
                path = writers.crea_rilascio(rel, piano.root)
            except FileExistsError:
                ui.notify(f'La cartella {cod} esiste già nel vault.', type='negative')
                return
            except writers.ConflittoModifica as e:      # es. azione in corso: nessuna scrittura
                ui.notify(str(e), type='negative', close_button=True)
                return
            idx.reload([path])
            ui.notify(f'Scheda {cod} creata.', type='positive')
            vai(f'/rilascio/{cod}')

        with ui.stepper().props('vertical flat').classes('w-full lv-card') as stepper:
            with ui.step('Codici e descrizioni', icon='tag'):
                inputs['codice'] = ui.input('Codice rilascio', placeholder='ADM953-01-0M').classes('w-64')
                inputs['desc_rilascio'] = ui.input('Descrizione rilascio').classes('w-full')
                inputs['desc_sub'] = ui.input('Descrizione sottoprogetto').classes('w-full')
                inputs['desc_progetto'] = ui.input('Descrizione progetto').classes('w-full')
                with ui.stepper_navigation():
                    ui.button('Avanti', on_click=stepper.next).props('unelevated')
            with ui.step('Team', icon='groups'):
                with ui.row().classes('w-full gap-4 flex-wrap'):
                    nomi = [n.titolo for n in persone(idx)]
                    for campo, label in CAMPI_TEAM:
                        if campo == 'struttura_business':
                            inputs[campo] = ui.input(label).classes('w-64')
                        else:   # persone: suggerimenti dall'Anagrafica, testo libero ammesso
                            inputs[campo] = campo_persona(label, 'Lunardi Astolfo' if campo == 'pm' else '', nomi, idx=idx)
                with ui.stepper_navigation():
                    ui.button('Avanti', on_click=stepper.next).props('unelevated')
                    ui.button('Indietro', on_click=stepper.previous).props('flat')
            with ui.step('Date e vincoli', icon='event'):
                with ui.row().classes('w-full gap-4 flex-wrap'):
                    inputs['data_collaudo_prevista'] = campo_data('Collaudo previsto (AAAA-MM-GG)', classes='w-56', props='')
                    inputs['data_rilascio_prevista'] = campo_data('Rilascio previsto (AAAA-MM-GG)', classes='w-56', props='')
                    inputs['vincoli_normativi'] = ui.select(['Sì', 'No'], value='No', label='Vincoli normativi') \
                        .classes('w-40')
                with ui.stepper_navigation():
                    ui.button('Crea scheda', icon='add', on_click=crea).props('unelevated')
                    ui.button('Indietro', on_click=stepper.previous).props('flat')
