"""Dialogo di convocazione (startup / collaudo) → leviathadm_cli in sottoprocesso."""
from __future__ import annotations
import re
from datetime import date, timedelta
from pathlib import Path

from nicegui import ui

from leviathadm.ui.esecuzione_ui import pulsante_azione
from leviathadm.ui.widgets import campo_data, campo_ora
from leviathadm.vault import azioni as A
from leviathadm.vault import piano_test
from leviathadm.vault.models import Rilascio

_ORA = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
GIORNI = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']


def valida_ora(ora: str) -> str | None:
    m = _ORA.match((ora or '').strip())
    if not m:
        return 'ora non valida (HH:MM)'
    minuti = int(m.group(1)) * 60 + int(m.group(2))
    if 12 * 60 + 30 <= minuti < 14 * 60:
        return 'niente riunioni tra le 12:30 e le 14:00 (pausa pranzo)'
    return None


def formatta_alternativa(d: date, ora: str) -> str:
    """Riga di una data alternativa nel formato atteso dalla mail di invito: 'martedì 21/10/2026, ore 11:30'."""
    return f"{GIORNI[d.weekday()]} {d:%d/%m/%Y}, ore {ora.strip()}"


def alternative_da_righe(righe: list[tuple[str, str]]) -> tuple[list[str], str | None]:
    """(alternative formattate, errore) dalle righe (data ISO, ora) del dialogo: le righe vuote si saltano,
    data senza ora (o viceversa) e orari in pausa pranzo sono errori."""
    out: list[str] = []
    for i, (data, ora) in enumerate(righe, start=1):
        data, ora = (data or '').strip(), (ora or '').strip()
        if not data and not ora:
            continue
        try:
            d = date.fromisoformat(data)
        except ValueError:
            return [], f'alternativa {i}: data non valida'
        motivo = valida_ora(ora)
        if motivo:
            return [], f'alternativa {i}: {motivo}'
        out.append(formatta_alternativa(d, ora))
    return out, None


def precompila_collaudo(rilascio_dir: Path) -> dict:
    piano = piano_test.trova_piano(rilascio_dir)
    doc, verifiche = piano_test.parse_piano_test(piano.read_text(encoding='utf-8')) if piano else ('', [])
    pdf = sorted(set(rilascio_dir.glob('*.pdf')) | set(rilascio_dir.glob('_fonti/**/*.pdf')), key=lambda p: p.name.lower())
    return {'documento': doc, 'verifiche': verifiche, 'pdf': [str(p) for p in pdf], 'piano_trovato': piano is not None}


def giorni_lavorativi_dopo(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def proponi_data_collaudo(r: Rilascio) -> str:
    """Regola di genera_convocazione (disponibilità + 20gg, −15/−10gg, giorno lavorativo); '' se non calcolabile."""
    from genera_convocazione import _parse_date, propose_collaudo_date   # puro Python, nessun COM
    disp = _parse_date(r.frontmatter.get('data_disponibilita_collaudo', ''))
    if disp is None:
        return ''
    return propose_collaudo_date(disp + timedelta(days=20), date.today()).isoformat()


def dialogo_convocazione(idx, r: Rilascio, tipo: str, data_proposta: str) -> ui.dialog:
    az = A.CATALOGO['convocazione_startup' if tipo == 'startup' else 'convocazione_collaudo']
    pre = precompila_collaudo(r.path.parent) if tipo == 'collaudo' else {}
    with ui.dialog() as d, ui.card().classes('w-[640px] max-w-full'):
        ui.label(az.titolo).classes('text-lg font-bold')
        with ui.row().classes('items-end gap-3'):
            data = campo_data('Data (AAAA-MM-GG)', value=data_proposta, classes='w-48', props='', conferma_weekend=True)
            ora = campo_ora('Ora', value='10:00', props='')
            durata = ui.number('Durata (min)', value=30 if tipo == 'startup' else 60, min=15, format='%.0f').classes('w-32')
        if tipo == 'collaudo' and not data_proposta:
            ui.label('Data non proponibile (data_disponibilita_collaudo assente o DA COMPLETARE): indicala a mano.') \
                .classes('text-xs text-amber-800')
        if tipo == 'startup':
            ui.label('Date alternative (facoltative)').classes('text-sm text-slate-600 mt-2')
            righe_alt: list[tuple[ui.input, ui.input]] = []
            for i in range(3):
                with ui.row().classes('items-end gap-3'):
                    righe_alt.append((campo_data(f'Alternativa {i + 1} (AAAA-MM-GG)', classes='w-48', props='', conferma_weekend=True),
                                      campo_ora('Ora', value='', props='')))
        else:
            if not pre['piano_trovato']:
                ui.label('Piano di Test.md non trovato: compila documento e verifiche a mano.').classes('text-xs text-amber-800')
            pdf = ui.select(pre['pdf'], label='PDF del piano di test (allegato)').classes('w-full')
            documento = ui.input('Documento di analisi', value=pre['documento']).classes('w-full')
            verifiche = ui.textarea('Casi di test (uno per riga)', value='\n'.join(pre['verifiche'])).classes('w-full')
        ui.label('Genera una bozza .eml da aprire in Outlook e inviare a mano; se esiste già viene sostituita, '
                 'il Verbale non viene mai sovrascritto.').classes('text-xs text-slate-500')

        def ctx() -> dict | None:
            try:
                dt = date.fromisoformat((data.value or '').strip())
            except ValueError:
                ui.notify('Data non valida.', type='warning')
                return None
            motivo = valida_ora(ora.value)
            if motivo:
                ui.notify(motivo, type='warning')
                return None
            base = {'codice': r.codice, 'data': dt.isoformat(), 'ora': ora.value.strip(), 'durata': str(max(15, int(durata.value or 0)))}
            if tipo == 'startup':
                alternative, errore = alternative_da_righe([(da.value, o.value) for da, o in righe_alt])
                if errore:
                    ui.notify(errore, type='warning')
                    return None
                ctx_ = {**base, 'alternative': alternative}
            else:
                if not pdf.value or not (documento.value or '').strip():
                    ui.notify('PDF e documento di analisi sono obbligatori.', type='warning')
                    return None
                v = [l.strip() for l in (verifiche.value or '').splitlines() if l.strip()]
                if not v:
                    ui.notify('Almeno un caso di test.', type='warning')
                    return None
                ctx_ = {**base, 'pdf': pdf.value, 'documento': documento.value.strip(), 'verifiche': v}
            d.close()        # il pannello di esecuzione vive a livello di pagina: resta visibile con l'esito
            return ctx_

        with ui.row().classes('gap-3'):
            pulsante_azione(az, rilascio=r.codice, ctx_fn=ctx, props='unelevated')
            ui.button('Annulla', on_click=d.close).props('flat')
    return d
