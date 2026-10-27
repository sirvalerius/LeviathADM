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
import proposta_copilot as PC

VARIANTI = {'firma': 'Approvazione con firma (sezione FIRME nel Word)',
            'telematica': 'Approvazione telematica, da raccogliere via mail',
            'telematica_in_riunione': 'Approvazione telematica già data in riunione'}


def campi_prompt(r: Rilascio, data_iso: str, fase_tab: str, trascritto: str) -> dict:
    """Segnaposto del prompt di fallback (Template/copilot/Prompt resoconto.txt): percorsi relativi al vault, con `/`.
    Trascritto: dalla riga ## Riunioni di data+fase, altrimenti dal campo; mai incorporato nel prompt."""
    nome = next((m.trascritto.strip('` ') for m in r.riunioni if m.data == data_iso and m.fase == fase_tab and m.trascritto.strip('` ')), '') or (trascritto or '').strip()
    rel_dir = r.path.parent.relative_to(idx_root(r)).as_posix()
    percorso = ''
    if nome:
        trovato = next((p for p in r.path.parent.rglob('*') if p.name == nome), None)   # nome esatto: `[x]` nei nomi Teams non è un glob
        percorso = f'{rel_dir}/{trovato.relative_to(r.path.parent).as_posix()}' if trovato else f'{rel_dir}/_fonti/{data_iso.replace("-", "")} {fase_tab}/{nome}'
    d = date.fromisoformat(data_iso)
    return {'CODICE': r.codice, 'PIANO': r.path.parents[1].name, 'DESCRIZIONE_RILASCIO': r.descrizione_rilascio, 'FASE': fase_tab, 'DATA': f'{d:%d/%m/%Y}',
            'PERCORSO_TRASCRITTO': percorso,
            'PERCORSO_PROPOSTA': f'{rel_dir}/_fonti/{data_iso.replace("-", "")} {fase_tab}/{PC.NOME}'}


def idx_root(r: Rilascio) -> Path:
    """Radice del vault a partire dalla scheda (…/PO <anno>/<codice>/<codice>.md)."""
    return r.path.parents[2]


def testo_prompt(r: Rilascio, data_iso: str, fase_tab: str, trascritto: str) -> str:
    tpl = (idx_root(r) / 'Template' / 'copilot' / 'Prompt resoconto.txt').read_text(encoding='utf-8')
    return PC.prompt_copilot(tpl, campi_prompt(r, data_iso, fase_tab, trascritto))


def crea_resoconto(idx: VaultIndex, r: Rilascio, fase: str, n_sal: int | None, data: date,
                   variante: str | None, trascritto: str, *, proposta_testo: str | None = None,
                   usa_proposta: bool = True) -> tuple[Path | None, list[str]]:
    """Crea il file dello scheletro, aggiunge la riga in ## Riunioni, ricarica l'indice. (path | None, avvisi).
    Proposta Copilot: `proposta_testo` (incollata) viene salvata in _fonti e usata; altrimenti, con `usa_proposta`,
    si usa il file trovato da proposta_copilot.trova_proposta. Mai per il collaudo."""
    avvisi: list[str] = []
    etichetta = R.etichetta_fase(fase, n_sal)
    out = r.path.parent / R.nome_file(r.codice, etichetta, data)
    if out.exists():
        return None, [f'Esiste già {out.name}.']
    fase_tab, data_iso = R.fase_tabella(etichetta), data.isoformat()
    proposta = None
    canon = PC.percorso_proposta(r.path.parent, data_iso, fase_tab)    # ValueError se la fase contiene separatori (il dialogo lo mostra)
    # gli avvisi "collaudo" e "altra riunione" non dipendono da usa_proposta: il dialogo nasconde la casella proprio in quei casi
    if etichetta == 'Collaudo':
        if proposta_testo or canon.exists() or PC.trova_proposta(r.path.parent, data_iso, fase_tab):
            avvisi.append('Proposta Copilot ignorata: collaudo (il resoconto di collaudo ha struttura fissa).')
    elif proposta_testo:
        writers.scrivi_testo(canon, PC.componi_proposta(proposta_testo, codice=r.codice, data_iso=data_iso, fase_tab=fase_tab, fonte='incollata'))
        proposta = PC.parse_proposta(canon.read_text(encoding='utf-8'))
        avvisi.append(f'Proposta Copilot salvata in {canon.relative_to(r.path.parent).as_posix()} e importata.')
    else:
        p = PC.trova_proposta(r.path.parent, data_iso, fase_tab)
        if p is not None and usa_proposta:
            proposta = PC.parse_proposta(p.read_text(encoding='utf-8'))
            avvisi.append(f'Proposta Copilot importata da {p.relative_to(r.path.parent).as_posix()}.')
        elif p is None and canon.exists():
            avvisi.append("Proposta Copilot ignorata: è per un'altra riunione (codice, data o fase diversi nel frontmatter).")
    if proposta:
        avvisi += [f'Copilot: {n}' for n in proposta.get('note', [])]
    team = team_from_release(r.path.read_text(encoding='utf-8'))
    csv = R.csv_presenze_per_data(r.path.parent, data.isoformat())   # solo il CSV di QUESTA data
    presenze = None
    if csv is not None:
        presenze = parse_presenze_csv(csv)
        if not (presenze['adm'] or presenze['sogei']):
            avvisi.append(f'CSV {csv.name} senza partecipanti riconosciuti: uso il team della scheda.')
            presenze = None
        pp = (proposta or {}).get('partecipanti') or {}
        if presenze and (pp.get('adm') or pp.get('sogei')):
            avvisi.append('Partecipanti della proposta Copilot ignorati: usato il report presenze.')
    if not presenze:
        pp = (proposta or {}).get('partecipanti') or {}
        if pp.get('adm') or pp.get('sogei'):
            avvisi.append('Partecipanti dalla proposta Copilot (lista incompleta): integra con il report presenze.')
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
                             verbale=verbale, trascritto=trascritto, info=anagrafica_info, proposta=proposta)
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
        usa_prop = ui.checkbox('Importa da Copilot', value=True).classes('w-full')
        prop_txt = ui.textarea('Proposta (incolla da Copilot: sezioni ARGOMENTI TRATTATI, AZIONI CONCORDATE, …)') \
            .props('outlined autogrow').classes('w-full')
        prop_txt.bind_visibility_from(fase, 'value', backward=lambda v: v != 'Collaudo')

        def fase_tab_corrente() -> str:
            return R.fase_tabella(R.etichetta_fase((fase.value or '').strip(), int(n_sal.value or 1)))

        def agg_info() -> None:
            d_iso = (data.value or '').strip()
            csv = R.csv_presenze_per_data(r.path.parent, d_iso)
            righe = [f'CSV presenze: {csv.name}' if csv else 'CSV presenze: nessuno con questa data (partecipanti dal team)']
            p = PC.trova_proposta(r.path.parent, d_iso, fase_tab_corrente()) if d_iso and fase.value != 'Collaudo' else None
            if p is not None:
                gen = PC.parse_proposta(p.read_text(encoding='utf-8'))['frontmatter'].get('generato', '')
                usa_prop.set_text(f'Importa da Copilot (generata il {gen or "?"}: {p.relative_to(r.path.parent).as_posix()})')
            usa_prop.set_visibility(p is not None)
            info.set_text(' · '.join(righe))
        data.on_value_change(lambda _: agg_info())
        fase.on_value_change(lambda _: agg_info())
        n_sal.on_value_change(lambda _: agg_info())
        agg_info()

        def copia_prompt() -> None:
            d_iso = (data.value or '').strip()
            try:
                date.fromisoformat(d_iso)
            except ValueError:
                ui.notify('Data non valida: usa AAAA-MM-GG.', type='warning')
                return
            testo = testo_prompt(r, d_iso, fase_tab_corrente(), (trascritto.value or '').strip())
            ui.clipboard.write(testo)
            with ui.dialog() as dp, ui.card().classes('w-[640px] max-w-full'):
                ui.label('Prompt per Copilot (copiato negli appunti se il browser lo consente; in ogni caso copialo da qui)').classes('font-bold')
                ui.textarea(value=testo).props('outlined autogrow readonly').classes('w-full')
                ui.button('Chiudi', on_click=dp.close).props('flat')
            dp.open()

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
                                             (trascritto.value or '').strip(),
                                             proposta_testo=(prop_txt.value or '').strip() or None,
                                             usa_proposta=bool(usa_prop.value) and usa_prop.visible)
            except (writers.ConflittoModifica, ValueError) as e:      # azione in corso, o fase con caratteri vietati: nessuna scrittura
                ui.notify(str(e), type='negative', close_button=True)
                return
            for a in avvisi:
                ui.notify(a, type='warning' if out else 'negative', close_button=True, timeout=6000)
            if out:
                dopo(out, avvisi)
        with ui.row().classes('gap-3'):
            ui.button('Crea', icon='note_add', on_click=crea).props('unelevated')
            ui.button('Copia prompt per Copilot', icon='content_copy', on_click=copia_prompt).props('outline') \
                .tooltip('Prompt pronto per la chat di Copilot: cita il trascritto per percorso, non lo incorpora')
            if annulla:
                ui.button('Annulla', on_click=annulla).props('flat')
