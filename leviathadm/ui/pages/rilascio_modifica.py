"""Modifica dei campi strutturati della scheda (solo i campi cambiati, con guardia anti-conflitto)."""
from __future__ import annotations
import re

from nicegui import ui

from leviathadm.ui import state
from leviathadm.ui.shell import shell, vai
from leviathadm.ui.pages.anagrafica import persone
from leviathadm.ui.widgets import campo_data, campo_persona, data_iso
from leviathadm.vault import writers

STATI = ['Da Avviare', 'Bozza', 'Startup', 'In corso', 'Analisi', 'In Verifica', 'Collaudo', 'Concluso']
CAMPI_TEAM = [('pm', 'PM'), ('ra', 'RA'), ('rp', 'RP'), ('struttura_business', 'Struttura business'),
              ('referente_business', 'Referente business'), ('referente_sogei', 'Referente SOGEI')]
CAMPI_DATE = [('data_fine_analisi', 'Fine analisi'), ('data_disponibilita_collaudo', 'Disponibilità collaudo'),
              ('data_collaudo_prevista', 'Collaudo previsto'), ('data_collaudo_effettiva', 'Collaudo effettivo'),
              ('data_rilascio_prevista', 'Rilascio previsto'), ('data_rilascio_effettiva', 'Rilascio effettivo')]


def opzioni_con_corrente(opzioni: list[str], corrente: str) -> list[str]:
    """ui.select rifiuta un valore fuori lista: il valore già in scheda (es. `Sì (GDPR, NIS2)`)
    va aggiunto alle opzioni, altrimenti la pagina va in errore."""
    return opzioni + ([corrente] if corrente and corrente not in opzioni else [])


def diff_campi(valori: dict, iniziali: dict) -> dict:
    """Solo i campi che l'utente ha davvero cambiato rispetto a quanto mostrato all'apertura
    (non rispetto al frontmatter: un select con default non deve scrivere chiavi mai toccate)."""
    return {k: v for k, v in valori.items() if v != iniziali.get(k)}


def valida_date_iso(valori: dict[str, str]) -> str | None:
    """Normalizza in posto le date (anche GG/MM/AAAA, come in alcune schede vecchie) in AAAA-MM-GG;
    errore solo per un valore non vuoto che non è una data (DA COMPLETARE ammesso)."""
    for campo, label in CAMPI_DATE:
        v = (valori.get(campo) or '').strip()
        if not v or v == 'DA COMPLETARE':
            continue
        iso = data_iso(v)
        if iso is None:
            return f'Data "{label}" non valida: usa AAAA-MM-GG.'
        valori[campo] = iso
    return None


def render_modifica(codice: str) -> None:
    idx = state.get_index()
    r = idx.rilascio(codice)
    with shell(f'Modifica {codice}'):
        if r is None:
            ui.label(f'Nessun rilascio con codice "{codice}".').classes('text-lg text-slate-700')
            ui.link('Torna ai rilasci', '/').classes('text-blue-900')
            return
        fm, inputs = r.frontmatter, {}

        def campo(nome: str, label: str, **kw):
            inputs[nome] = ui.input(label, value=fm.get(nome, ''), **kw).classes('w-64')
            return inputs[nome]

        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label('Anagrafica').classes('font-bold text-slate-700')
            with ui.row().classes('w-full gap-4 flex-wrap items-end'):
                campo('descrizione_rilascio', 'Descrizione rilascio').classes('w-full')
                campo('descrizione_sottoprogetto', 'Descrizione sottoprogetto').classes('w-96')
                campo('descrizione_progetto', 'Descrizione progetto').classes('w-96')
                stato_corrente = fm.get('stato', '') or 'Bozza'
                inputs['stato'] = ui.select(opzioni_con_corrente(STATI, stato_corrente), value=stato_corrente,
                                            label='Stato').classes('w-40')
                vincoli_correnti = fm.get('vincoli_normativi', '') or 'No'
                inputs['vincoli_normativi'] = ui.select(opzioni_con_corrente(['Sì', 'No'], vincoli_correnti),
                                                        value=vincoli_correnti, label='Vincoli normativi').classes('w-40')
                campo('nota_variazione_date', 'Nota variazione date').classes('w-96')
        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label('Team').classes('font-bold text-slate-700')
            with ui.row().classes('w-full gap-4 flex-wrap'):
                nomi = [n.titolo for n in persone(idx)]
                for nome, label in CAMPI_TEAM:
                    if nome == 'struttura_business':
                        campo(nome, label)
                    else:   # persone: suggerimenti dall'Anagrafica, testo libero ammesso
                        inputs[nome] = campo_persona(label, fm.get(nome, ''), nomi, idx=idx)
        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label('Date (AAAA-MM-GG)').classes('font-bold text-slate-700')
            with ui.row().classes('w-full gap-4 flex-wrap'):
                for nome, label in CAMPI_DATE:
                    inputs[nome] = campo_data(f'{label} (AAAA-MM-GG)', value=fm.get(nome, ''), classes='w-48', props='')

        iniziali = {k: (v.value.strip() if isinstance(v.value, str) else v.value) for k, v in inputs.items()}

        def salva():
            valori = {k: (v.value.strip() if isinstance(v.value, str) else v.value) for k, v in inputs.items()}
            err = valida_date_iso(valori)
            if err:
                ui.notify(err, type='warning')
                return
            modifiche = diff_campi(valori, iniziali)
            if not modifiche:
                ui.notify('Nessuna modifica da salvare.', type='info')
                return
            try:
                writers.update_frontmatter(r.path, modifiche, r.mtime_ns)
            except writers.ConflittoModifica as e:
                ui.notify(str(e),
                          type='negative', close_button=True)
                return
            idx.reload([r.path])
            ui.notify(f'Scheda aggiornata ({", ".join(modifiche)}).', type='positive')
            vai(f'/rilascio/{codice}')

        with ui.row().classes('gap-3'):
            ui.button('Salva modifiche', icon='save', on_click=salva).props('unelevated')
            ui.button('Annulla', on_click=lambda: vai(f'/rilascio/{codice}')).props('flat')
