"""Dialogo "Lettere di fine collaudo" → leviathadm_cli genera-lettere in sottoprocesso (allineato alla web 79_ui_lettere.js)."""
from __future__ import annotations

from nicegui import ui

from leviathadm.ui.esecuzione_ui import pulsante_azione
from leviathadm.vault import azioni as A
from leviathadm.vault.models import Rilascio

ESITI = ('POSITIVO', 'con riserva', 'NEGATIVO')
AVVISO_NEGATIVO = "senza esito positivo non si chiede l'estensione"


def precompila(codice: str) -> dict:
    """genera_lettere.dati_lettere, senza far cadere la pagina se la scheda è incompleta."""
    from genera_lettere import dati_lettere   # puro Python (python-docx), nessun COM
    try:
        return dati_lettere(codice)
    except Exception as e:   # noqa: BLE001
        return {'progetto': '', 'descrizione_progetto': '', 'sottoprogetto': '', 'rilascio': codice, 'adm': [], 'sogei': [],
                'fonte_nomi': '', 'esito': 'POSITIVO', 'direzione': '', 'ufficio': '', 'area_staff': 'Area di Staff', 'rb': '',
                'avvisi': [f'dati non leggibili: {e}']}


def righe(testo: str) -> list[str]:
    return [r.strip() for r in (testo or '').splitlines() if r.strip()]


def dialogo_lettere(idx, r: Rilascio) -> ui.dialog:
    az = A.CATALOGO['lettere_collaudo']
    d0 = precompila(r.codice)
    fonte = {'resoconto': 'dal resoconto di collaudo', 'csv': 'dal CSV presenze del collaudo', 'team': 'dal team della scheda', '': 'nessuna fonte: compila a mano'}[d0['fonte_nomi']]
    with ui.dialog() as d, ui.card().classes('w-[720px] max-w-full'):
        ui.label(az.titolo).classes('text-lg font-bold')
        ui.label(f"Rilascio: {d0['rilascio']} · progetto {d0['progetto']} {d0['descrizione_progetto']} · sottoprogetto {d0['sottoprogetto']}").classes('text-xs text-slate-600')
        with ui.row().classes('gap-4'):
            trasm = ui.checkbox('Trasmissione copia verbale di collaudo', value=True)
            est = ui.checkbox('Richiesta estensione in esercizio', value=d0['esito'] != 'NEGATIVO')
        with ui.row().classes('gap-3 w-full'):
            adm = ui.textarea(f'Rappresentanti ADM (uno per riga, Cognome Nome; cognome composto non riconosciuto: Cognome | Nome · {fonte})',
                              value='\n'.join(d0['adm'])).classes('flex-1')
            sogei = ui.textarea('Rappresentanti SOGEI (uno per riga)', value='\n'.join(d0['sogei'])).classes('flex-1')
        esito = ui.select(list(ESITI), label='Esito del collaudo', value=d0['esito'] if d0['esito'] in ESITI else 'POSITIVO').classes('w-48')
        with ui.row().classes('gap-3 w-full'):
            direzione = ui.input('Direzione di business (p.c.)', value=d0['direzione']).classes('flex-1')
            ufficio = ui.input('Ufficio del Responsabile di Business (p.c.)', value=d0['ufficio']).classes('flex-1')
            area = ui.input('Area di Staff (p.c.)', value=d0['area_staff']).classes('w-40')
        avvisi = ui.column().classes('gap-0')
        with avvisi:
            for a in d0['avvisi']:
                ui.label(a).classes('text-xs text-amber-800')
            neg = ui.label(AVVISO_NEGATIVO).classes('text-xs text-amber-800')
            neg.set_visibility(d0['esito'] == 'NEGATIVO')

        def su_esito() -> None:
            negativo = esito.value == 'NEGATIVO'
            neg.set_visibility(negativo)
            if negativo:
                est.value = False
        esito.on_value_change(lambda _: su_esito())
        sovr = ui.checkbox('Sovrascrivi le lettere esistenti (svuota anche la cartella dei PDF da mandare in firma)', value=False)
        ui.label('I .docx vanno nella cartella del rilascio e compaiono in Da firmare quando il collaudo è registrato come svolto; '
                 'i PDF per Arcipelago li prepara il sync del PC master. Rileggi l\'intestazione in Word prima della firma.').classes('text-xs text-slate-500')

        def ctx() -> dict | None:
            lettere = [t for t, c in (('trasmissione', trasm), ('estensione', est)) if c.value]
            if not lettere:
                ui.notify('Seleziona almeno una lettera.', type='warning')
                return None
            a_, s_ = righe(adm.value), righe(sogei.value)
            if 'trasmissione' in lettere and not (a_ and s_):
                ui.notify('Per la Trasmissione servono almeno un nome ADM e uno SOGEI.', type='warning')
                return None
            if 'estensione' in lettere and not ((direzione.value or '').strip() and (ufficio.value or '').strip()):
                ui.notify('Per la Richiesta estensione servono Direzione e Ufficio del referente business.', type='warning')
                return None
            d.close()
            return {'codice': r.codice, 'lettere': lettere, 'adm': a_, 'sogei': s_, 'esito': esito.value,
                    'direzione': (direzione.value or '').strip(), 'ufficio': (ufficio.value or '').strip(),
                    'area_staff': (area.value or '').strip() or 'Area di Staff', 'sovrascrivi': ['--sovrascrivi'] if sovr.value else []}

        with ui.row().classes('gap-3'):
            pulsante_azione(az, rilascio=r.codice, ctx_fn=ctx, props='unelevated')
            ui.button('Annulla', on_click=d.close).props('flat')
    return d
