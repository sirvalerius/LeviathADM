"""Editor a sezioni del resoconto: widget strutturati dove i dati lo sono, testo altrove.
Scrive solo le sezioni cambiate (writers.salva_sezioni) e le chiavi di frontmatter cambiate."""
from __future__ import annotations
import re
from collections.abc import Callable

from nicegui import ui

from leviathadm.ui import state
from leviathadm.ui.pages.resoconto import carica_doc
from leviathadm.ui.shell import shell, vai
from leviathadm.ui.widgets import (ListaRighe, TabellaPartecipanti, TextareaAnteprima, campo_data, campo_persona,
                                   ruolo_da_anagrafica)
from leviathadm.vault import resoconti as R
from leviathadm.vault import writers
from mail_utils import team_from_release
from parse_presenze import parse_presenze_csv

FLAG = ["VINCOLI NORMATIVI", "VARIAZIONE DATE PREVISTE", "VARIAZIONE EFFORT", "PRIVACY"]
_DATA_IT_RE = re.compile(r"\d{2}/\d{2}/\d{4}")


def bodies_modificati(doc: R.ResocontoDoc, nuovi_inner: dict[str, str]) -> dict[str, str]:
    """heading → body completo (via doc.body_di) per le sole sezioni il cui inner è cambiato
    (differenze di soli spazi non contano: "nessuna modifica" non scrive nulla).
    Sezioni nuove in coda: il footer migra dall'ultima sezione esistente all'ultima nuova,
    con il separatore standard tra le due."""
    out: dict[str, str] = {}
    esistenti = {s.heading: s for s in doc.sezioni}
    nuove = [h for h in nuovi_inner if h not in esistenti]
    ultima = doc.sezioni[-1] if doc.sezioni else None
    for h, inner in nuovi_inner.items():
        s = esistenti.get(h)
        if s is None:
            continue
        cambiata = not R.stessa_forma(inner, s.inner)
        if cambiata or (nuove and s is ultima):
            body = doc.body_di(h, inner if cambiata else s.inner)
            if nuove and s is ultima:
                if doc.footer and body.endswith(doc.footer):
                    body = body[: len(body) - len(doc.footer)]
                body = body.rstrip("\n") + "\n\n---\n\n"
            out[h] = body
    for i, h in enumerate(nuove):
        out[h] = "\n" + nuovi_inner[h] + "\n" + (doc.footer if i == len(nuove) - 1 else "\n---\n\n")
    return out


def _data_iso(valore: str) -> str | None:
    v = (valore or "").strip()
    if _DATA_IT_RE.fullmatch(v):
        g, m, a = v.split("/")
        return f"{a}-{m}-{g}"
    return None


def campi_frontmatter_resoconto(nuovo: dict[str, str], vecchio: dict[str, str]) -> tuple[dict[str, str], str | None]:
    """Chiavi di frontmatter da riallineare alla tabella RESOCONTO: (modifiche, errore).
    `data_approvazione` va scritta in ISO (gli script la leggono con fromisoformat) o lasciata vuota."""
    mod: dict[str, str] = {}
    for chiave_tab, chiave_fm in (("Approvato da", "approvato_da"), ("Data approvazione", "data_approvazione")):
        v = R.trova(nuovo, chiave_tab).strip()
        if v == R.trova(vecchio, chiave_tab).strip():
            continue
        if chiave_fm == "data_approvazione" and v:
            iso = _data_iso(v)
            if iso is None:
                return {}, 'Data approvazione non valida: usa GG/MM/AAAA (o lasciala vuota).'
            v = iso
        mod[chiave_fm] = v
    return mod, None


def opzioni_caso(esito: str) -> list[str]:
    """Opzioni del select di un caso di test: il valore già nel file va sempre incluso (ui.select rifiuta valori fuori lista)."""
    base = ['', 'Superato', 'Non superato']
    return base + ([esito] if esito and esito not in base else [])


def render_modifica(nid: str) -> None:
    with shell('Modifica resoconto'):
        editor_resoconto(state.get_index(), nid, dopo_salva=lambda: vai(f'/resoconto/{nid}'),
                         annulla=lambda: vai(f'/resoconto/{nid}'))


def editor_resoconto(idx, nid: str, *, dopo_salva: Callable[[], None], annulla: Callable[[], None]) -> None:
    """Editor a sezioni del resoconto, reso nel contenitore corrente (pagina /modifica o pannello
    "Ciclo di vita" del rilascio). Salva scrive solo le sezioni cambiate, poi chiama dopo_salva()."""
    doc, r, err = carica_doc(idx, nid)
    if True:   # corpo storico della pagina, rientrato di un livello
        if err or not doc.ha_sezioni:
            ui.label(err or 'Resoconto senza sezioni ##: modificabile solo come nota grezza.') \
                .classes('text-lg text-slate-700')
            ui.link('Indietro', f'/resoconto/{nid}' if not err else '/').classes('text-blue-900')
            return
        if doc.path.parent.name == 'inviati':
            ui.label('Resoconto già inviato: usa "Riporta in bozza" dalla pagina del resoconto.') \
                .classes('text-slate-700')
            ui.link('Indietro', f'/resoconto/{nid}').classes('text-blue-900')
            return
        ui.label(doc.titolo).classes('text-xl font-bold text-slate-800')
        if doc.problemi:
            ui.label('; '.join(doc.problemi)).classes('text-xs text-amber-800')
        getter: dict[str, Callable[[], str]] = {}       # heading → nuovo inner
        fm_inputs: dict[str, ui.input] = {}
        persone = sorted((n for n in idx.note.values() if n.tipo == 'persona'), key=lambda n: n.titolo)
        fm_tot = {**(r.frontmatter if r else {}), **doc.frontmatter}

        for s in doc.sezioni:
            with ui.card().classes('w-full lv-card shadow-none'):
                ui.label(s.heading).classes('font-bold text-slate-700')
                if s.grezza or s.heading not in R.SEZIONI_NOTE:
                    ta = ui.textarea(value=s.inner).props('outlined autogrow').classes('w-full')
                    if s.grezza:
                        ui.label('Formato non standard: modifica come testo.').classes('text-xs text-amber-800')
                    getter[s.heading] = (lambda ta=ta: (ta.value or '').strip('\n'))
                elif s.heading in R.SEZIONI_KV:
                    d = {'RIUNIONE': doc.riunione, 'RESOCONTO': doc.resoconto, 'OBIETTIVO': doc.obiettivo}[s.heading]
                    campi: dict[str, ui.element] = {}
                    with ui.row().classes('w-full gap-3 flex-wrap'):
                        for k, v in d.items():
                            if s.heading == 'OBIETTIVO' and k in FLAG:
                                campi[k] = ui.select(sorted({'SI', 'NO', v} - {''}), value=v or 'NO', label=k) \
                                    .classes('w-56')
                            elif s.heading == 'OBIETTIVO' or k.upper() == 'DATA COMPILAZIONE':
                                campi[k] = ui.input(k, value=v).props('readonly').classes('w-72')
                            else:
                                campi[k] = (campo_data(k, value=v, formato='it', classes='w-72', props='', conferma_weekend=(k.upper() == 'DATA')) if 'DATA' in k.upper()
                                            else ui.input(k, value=v).classes('w-72'))
                    getter[s.heading] = (lambda campi=campi: R.ser_kv({k: str(c.value or '').strip()
                                                                       for k, c in campi.items()}))
                    if s.heading == 'RIUNIONE' and 'DATA' in campi:
                        fm_inputs['data'] = campi['DATA']
                elif s.heading == 'LISTA PARTECIPANTI':
                    tab = TabellaPartecipanti(doc.adm)
                    with ui.row().classes('w-full items-end gap-2'):
                        sel = campo_persona('Persona (Anagrafica)', '', [n.titolo for n in persone], idx=idx, classes='w-72')
                        sigla = ui.select(['', 'PM', 'RA', 'RP', 'RB'], value='', label='Sigla').classes('w-24')

                        def aggiungi(sel=sel, sigla=sigla, tab=tab):
                            n = idx.nota(f'Anagrafica~{sel.value}') if sel.value else None   # anche appena creata
                            if n is None:
                                ui.notify('Scegli una persona dall\'Anagrafica.', type='warning')
                                return
                            tab.aggiungi(R.Partecipante(ruolo=ruolo_da_anagrafica(sigla.value or '', n.frontmatter),
                                                        nome=n.titolo))
                        ui.button('Aggiungi da Anagrafica', icon='person_add', on_click=aggiungi).props('flat dense')
                    ui.label('SOGEI').classes('text-sm text-slate-600 mt-2')
                    lista_sogei = ListaRighe(doc.sogei, label='nome SOGEI')

                    def importa_csv(tab=tab, lista_sogei=lista_sogei):
                        csv = R.csv_presenze_per_data(doc.path.parent, doc.frontmatter.get('data_riunione', ''))
                        if csv is None:
                            ui.notify('Nessun CSV presenze con la data di questa riunione nella cartella del rilascio.',
                                      type='warning')
                            return
                        team = team_from_release(r.path.read_text(encoding='utf-8')) if r else {}
                        adm, sogei = R.partecipanti_da_presenze(parse_presenze_csv(csv), team, fm_tot)
                        tab.sostituisci(adm)
                        lista_sogei.sostituisci(sogei)
                        ui.notify(f'Importati {len(adm)} ADM e {len(sogei)} SOGEI da {csv.name}', type='positive')
                    ui.button('Importa CSV presenze', icon='upload_file', on_click=importa_csv).props('flat dense')
                    nota = ui.input('Nota', value=doc.nota_partecipanti).classes('w-full')
                    getter[s.heading] = (lambda tab=tab, lista_sogei=lista_sogei, nota=nota:
                                         R.ser_partecipanti(tab.valori, lista_sogei.valori, (nota.value or '').strip()))
                elif s.heading in R.SEZIONI_TESTO:
                    w = TextareaAnteprima(s.inner, label=s.heading.title())
                    getter[s.heading] = (lambda w=w: w.valore)
                elif s.heading == 'AZIONI CONCORDATE':
                    lr = ListaRighe(doc.azioni, label='azione', placeholder='Responsabile — cosa — entro quando')
                    getter[s.heading] = (lambda lr=lr: R.ser_azioni(lr.valori))
                elif s.heading == 'ESITO':
                    getter[s.heading] = _editor_esito(doc, r)

        with ui.card().classes('w-full lv-card shadow-none'):
            ui.label('Aggiungi sezione').classes('font-bold text-slate-700')
            with ui.row().classes('w-full items-end gap-2'):
                nuovo_h = ui.input('Titolo', placeholder='AGGIORNAMENTO DEL GG-MM-AAAA').classes('w-96')
            nuovo_t = ui.textarea('Testo').props('outlined autogrow').classes('w-full')

        ricarica_box = ui.row().classes('gap-3')

        def salva():
            nuovi = {h: g() for h, g in getter.items()}
            h_new = (nuovo_h.value or '').strip().upper()
            if h_new:
                if h_new in nuovi:
                    ui.notify(f'La sezione {h_new} esiste già.', type='warning')
                    return
                nuovi[h_new] = (nuovo_t.value or '').strip('\n')
            bodies = bodies_modificati(doc, nuovi)
            fm_mod: dict[str, str] = {}
            d = fm_inputs.get('data')
            if d is not None:
                iso = _data_iso(d.value)
                if (d.value or '').strip() != doc.riunione.get('DATA', '') and iso is None:
                    ui.notify('Data riunione non valida: usa GG/MM/AAAA.', type='warning')
                    return
                if iso and iso != doc.frontmatter.get('data_riunione', ''):
                    fm_mod['data_riunione'] = iso
            res = getter.get('RESOCONTO')
            if res is not None:
                mod, errore = campi_frontmatter_resoconto(R.parse_kv(res()) or {}, doc.resoconto)
                if errore:
                    ui.notify(errore, type='warning')
                    return
                if 'data_approvazione' in mod and mod['data_approvazione']:
                    ui.notify('Attenzione: con "Data approvazione" compilata il resoconto esce dalla convalida tacita '
                              '(scadenze e definitivo automatici).', type='warning', close_button=True, timeout=8000)
                fm_mod.update(mod)
            if not bodies and not fm_mod:
                ui.notify('Nessuna modifica da salvare.', type='info')
                return
            try:
                m = writers.salva_sezioni(doc.path, bodies, doc.mtime_ns) if bodies else doc.mtime_ns
                if fm_mod:
                    writers.update_frontmatter(doc.path, fm_mod, m)
            except writers.ConflittoModifica as e:
                ui.notify(str(e),
                          type='negative', timeout=0, close_button=True)
                ricarica_box.clear()
                with ricarica_box:
                    ui.button('Ricarica', icon='refresh', on_click=ui.navigate.reload).props('outline color=negative')
                return
            idx.reload([doc.path])
            ui.notify(f'Salvato: {", ".join(list(bodies) + list(fm_mod))}.', type='positive')
            if bodies and (doc.path.with_suffix('.docx').exists() or doc.path.with_suffix('.msg').exists()):
                ui.notify('Il .docx/.msg esistenti sono ora superati: usa "Rigenera .docx" prima dell\'invio.',
                          type='warning', close_button=True, timeout=0)
                ui.timer(3.0, dopo_salva, once=True)
                return
            dopo_salva()

        with ui.row().classes('gap-3'):
            ui.button('Salva', icon='save', on_click=salva).props('unelevated')
            ui.button('Annulla', on_click=annulla).props('flat')


def _editor_esito(doc: R.ResocontoDoc, r) -> Callable[[], str]:
    """Widget della sezione ESITO; restituisce il getter del nuovo inner."""
    e = doc.esito
    casi_box = ui.column().classes('w-full gap-1')
    casi_w: list[tuple[ui.input, ui.select]] = []

    def render_casi(casi: list[R.CasoTest]) -> None:
        casi_box.clear()
        casi_w.clear()
        with casi_box:
            for c in casi:
                with ui.row().classes('w-full items-center no-wrap gap-2'):
                    i = ui.input(value=c.nome).props('dense outlined').classes('grow')
                    sl = ui.select(opzioni_caso(c.esito), value=c.esito).props('dense').classes('w-40')
                    casi_w.append((i, sl))
    render_casi(e.casi)

    def casi_correnti() -> list[R.CasoTest]:
        return [R.CasoTest(nome=(i.value or '').strip(), esito=sl.value or '') for i, sl in casi_w]

    def riallinea() -> None:
        if not (r and r.verbali):
            ui.notify('Nessun Verbale di Collaudo nella cartella del rilascio.', type='warning')
            return
        vp = r.verbali[-1]
        v = R.parse_verbale(vp, vp.read_text(encoding='utf-8'), vp.stat().st_mtime_ns)
        nuovo = R.riallinea_esito_da_verbale(e, v)
        render_casi(nuovo.casi)
        if nuovo.esito:
            esito_sel.set_value(nuovo.esito)
        if any(not c.esito for c in nuovo.casi):
            ui.notify('Alcune verifiche del Verbale non hanno ancora esito.', type='warning')

    with ui.row().classes('gap-2'):
        ui.button('Aggiungi caso', icon='add',
                  on_click=lambda: render_casi(casi_correnti() + [R.CasoTest(nome='')])).props('flat dense')
        ui.button('Riallinea dal Verbale', icon='sync', on_click=riallinea).props('flat dense')
    esito_sel = ui.select(R.ESITI + ([e.esito] if e.esito and e.esito not in R.ESITI else []),
                          value=e.esito or None, label='Esito complessivo', clearable=True).classes('w-48')
    chiusure = {v: k for k, v in R.CHIUSURE.items()}
    opz = {**{v: f'{k}: {v}' for k, v in R.CHIUSURE.items()}, '__altro__': 'altro (testo libero)'}
    chiusura_sel = ui.select(opz, value=e.chiusura if e.chiusura in chiusure else '__altro__',
                             label='Formula di chiusura').classes('w-full')
    chiusura_ta = ui.textarea('Chiusura (testo libero)', value=e.chiusura if e.chiusura not in chiusure else '') \
        .props('outlined autogrow').classes('w-full')
    chiusura_ta.bind_visibility_from(chiusura_sel, 'value', value='__altro__')
    oss = ui.textarea("Osservazioni (tra i casi di test e l'esito)", value=e.osservazioni) \
        .props('outlined autogrow').classes('w-full')

    def inner_esito() -> str:
        chiusura = (chiusura_ta.value or '').strip('\n') if chiusura_sel.value == '__altro__' else chiusura_sel.value
        return R.ser_esito(R.Esito(intro=e.intro, casi=[c for c in casi_correnti() if c.nome],
                                   osservazioni=(oss.value or '').strip('\n'), esito=esito_sel.value or '',
                                   chiusura=chiusura or ''))
    return inner_esito
