"""Nuovo resoconto: dialogo (fase, numero SAL, data, variante collaudo, trascritto) e creazione dello scheletro."""
from __future__ import annotations
from collections.abc import Callable
from datetime import date
from pathlib import Path

from nicegui import ui

from leviathadm.ui.shell import vai
from leviathadm.ui.widgets import campo_data
from leviathadm.vault import resoconti as R
from leviathadm.vault import writers
from leviathadm.vault.index import VaultIndex
from leviathadm.vault.models import Rilascio
from leviathadm.vault.paths import nota_id
from mail_utils import team_from_release
from parse_presenze import parse_presenze_csv
from update_anagrafica import anagrafica_info, update_from_presenze

VARIANTI = {'firma': 'Approvazione con firma (sezione FIRME nel Word)',
            'telematica': 'Approvazione telematica, da raccogliere via mail',
            'telematica_in_riunione': 'Approvazione telematica già data in riunione'}


def crea_resoconto(idx: VaultIndex, r: Rilascio, fase: str, n_sal: int | None, data: date,
                   variante: str | None, trascritto: str) -> tuple[Path | None, list[str]]:
    """Crea il file dello scheletro, aggiunge la riga in ## Riunioni, ricarica l'indice. (path | None, avvisi)."""
    avvisi: list[str] = []
    etichetta = R.etichetta_fase(fase, n_sal)
    out = r.path.parent / R.nome_file(r.codice, etichetta, data)
    if out.exists():
        return None, [f'Esiste già {out.name}.']
    team = team_from_release(r.path.read_text(encoding='utf-8'))
    csv = R.csv_presenze_per_data(r.path.parent, data.isoformat())   # solo il CSV di QUESTA data
    presenze = None
    if csv is not None:
        presenze = parse_presenze_csv(csv)
        if not (presenze['adm'] or presenze['sogei']):
            avvisi.append(f'CSV {csv.name} senza partecipanti riconosciuti: uso il team della scheda.')
            presenze = None
    else:
        avvisi.append('Nessun CSV presenze per questa data: partecipanti dal team della scheda (lista incompleta).')
    verbale = None
    if etichetta == 'Collaudo':
        if r.verbali:
            vp = r.verbali[-1]
            verbale = R.parse_verbale(vp, vp.read_text(encoding='utf-8'), vp.stat().st_mtime_ns)
        else:
            avvisi.append('Nessun Verbale di Collaudo: ESITO senza casi di test.')
    testo = R.crea_scheletro(r.frontmatter, etichetta, data, team=team, variante=variante, presenze=presenze,
                             verbale=verbale, trascritto=trascritto, info=anagrafica_info)
    writers.crea_file(out, testo)
    if presenze:
        try:
            update_from_presenze(presenze)
        except Exception as e:  # noqa: BLE001 — gli stub Anagrafica non devono bloccare la creazione
            avvisi.append(f'Anagrafica non aggiornata: {e}')
    try:
        writers.aggiungi_riunione(r.path, data.isoformat(), R.fase_tabella(etichetta), trascritto, out.stem,
                                  r.path.stat().st_mtime_ns)
    except writers.ConflittoModifica:
        avvisi.append('Scheda cambiata nel frattempo: riga Riunioni non aggiunta (aggiungila a mano).')
    idx.reload([out, r.path])
    return out, avvisi


def dialogo(idx: VaultIndex, r: Rilascio) -> ui.dialog:
    with ui.dialog() as d, ui.card().classes('w-[560px] max-w-full'):
        ui.label('Nuovo resoconto').classes('text-lg font-bold')

        def dopo(out: Path, avvisi: list[str]) -> None:
            d.close()
            destinazione = f'/resoconto/{nota_id(idx.root, out)}/modifica'
            # con avvisi, lascia il tempo di leggerli: la navigazione li cancellerebbe subito
            ui.timer(2.5 if avvisi else 0.1, lambda: vai(destinazione), once=True)
        form_nuovo(idx, r, dopo=dopo, annulla=d.close)
    return d


def form_nuovo(idx: VaultIndex, r: Rilascio, *, dopo: Callable[[Path, list[str]], None],
               annulla: Callable[[], None] | None = None) -> None:
    """Campi del nuovo resoconto nel contenitore corrente. Fase: uguale o successiva all'ultima già fatta,
    oppure testo libero. Alla creazione (scheletro precompilato da scheda/Anagrafica/CSV) chiama dopo(path, avvisi)."""
    if True:
        ammesse = R.fasi_ammesse([m.fase for m in r.riunioni])
        fase = ui.select(ammesse, value='SAL' if 'SAL' in ammesse else ammesse[0], label='Fase (o testo libero)',
                         with_input=True, new_value_mode='add-unique').classes('w-full')
        n_sal = ui.number('Numero SAL', value=R.prossimo_sal([m.fase for m in r.riunioni]), min=1, format='%.0f') \
            .classes('w-40')
        n_sal.bind_visibility_from(fase, 'value', value='SAL')
        data = campo_data('Data riunione (AAAA-MM-GG)', value=date.today().isoformat(), classes='w-56', props='', conferma_weekend=True)
        variante = ui.select(VARIANTI, label='Variante collaudo').classes('w-full')
        variante.bind_visibility_from(fase, 'value', value='Collaudo')
        trascritto = ui.input('Nome file trascritto (opzionale)').classes('w-full')
        info = ui.label().classes('text-xs text-slate-500')

        def agg_info() -> None:
            csv = R.csv_presenze_per_data(r.path.parent, (data.value or '').strip())
            info.set_text(f'CSV presenze: {csv.name}' if csv else 'CSV presenze: nessuno con questa data (partecipanti dal team)')
        data.on_value_change(lambda _: agg_info())
        agg_info()

        def crea() -> None:
            try:
                dt = date.fromisoformat((data.value or '').strip())
            except ValueError:
                ui.notify('Data non valida: usa AAAA-MM-GG.', type='warning')
                return
            if not (fase.value or '').strip():
                ui.notify('Indica la fase.', type='warning')
                return
            if fase.value == 'Collaudo' and not variante.value:
                ui.notify('Scegli la variante del collaudo.', type='warning')
                return
            try:
                out, avvisi = crea_resoconto(idx, r, fase.value, int(n_sal.value or 1), dt, variante.value,
                                             (trascritto.value or '').strip())
            except writers.ConflittoModifica as e:      # es. azione in corso: nessuna scrittura
                ui.notify(str(e), type='negative', close_button=True)
                return
            for a in avvisi:
                ui.notify(a, type='warning' if out else 'negative', close_button=True, timeout=6000)
            if out:
                dopo(out, avvisi)
        with ui.row().classes('gap-3'):
            ui.button('Crea', icon='note_add', on_click=crea).props('unelevated')
            if annulla:
                ui.button('Annulla', on_click=annulla).props('flat')
