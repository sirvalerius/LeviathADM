"""Widget NiceGUI riusabili dell'editor. Nessuna dipendenza dal vault oltre ai modelli."""
from __future__ import annotations
from nicegui import ui

from leviathadm.vault.resoconti import Partecipante


def sposta(lista: list, i: int, delta: int) -> list:
    j = i + delta
    if 0 <= j < len(lista):
        lista = list(lista)
        lista[i], lista[j] = lista[j], lista[i]
    return lista


def ruolo_da_anagrafica(sigla: str, fm: dict) -> str:
    """Prima colonna della tabella partecipanti: "(SIGLA) DIREZIONE" (l'ufficio va nella seconda, ufficio_da_anagrafica)."""
    direzione = fm.get("direzione", "").strip()
    return f"({sigla}) {direzione}".strip() if sigla else direzione


def ufficio_da_anagrafica(fm: dict) -> str:
    return fm.get("ufficio", "").strip()


class ListaRighe:
    """Elenco ordinabile di righe di testo (azioni, nomi SOGEI)."""

    def __init__(self, valori: list[str], *, label: str = "riga", placeholder: str = ""):
        self._valori = list(valori)
        self._label, self._placeholder = label, placeholder
        self._box = ui.column().classes("w-full gap-1")
        self._render()

    @property
    def valori(self) -> list[str]:
        return [v for v in self._valori if v.strip()]

    def sostituisci(self, valori: list[str]) -> None:
        self._valori = list(valori)
        self._render()

    def _set(self, i: int, v: str) -> None:
        self._valori[i] = v or ""

    def _render(self) -> None:
        self._box.clear()
        with self._box:
            for i, v in enumerate(self._valori):
                with ui.row().classes("w-full items-center no-wrap gap-1 lv-riga"):
                    ui.input(value=v, placeholder=self._placeholder,
                             on_change=lambda e, i=i: self._set(i, e.value)).props("dense outlined").classes("grow")
                    ui.button(icon="arrow_upward", on_click=lambda i=i: self._mv(i, -1)).props("flat dense")
                    ui.button(icon="arrow_downward", on_click=lambda i=i: self._mv(i, 1)).props("flat dense")
                    ui.button(icon="delete", on_click=lambda i=i: self._rm(i)).props("flat dense color=negative")
            ui.button(f"Aggiungi {self._label}", icon="add", on_click=self._add).props("flat dense")

    def _mv(self, i: int, d: int) -> None:
        self._valori = sposta(self._valori, i, d)
        self._render()

    def _rm(self, i: int) -> None:
        del self._valori[i]
        self._render()

    def _add(self) -> None:
        self._valori.append("")
        self._render()


class TabellaPartecipanti:
    """Righe (ruolo, ufficio, nome) con riordino e rimozione; `aggiungi`/`sostituisci` per Anagrafica/CSV."""

    def __init__(self, adm: list[Partecipante]):
        self._righe = [p.model_copy() for p in adm]
        self._box = ui.column().classes("w-full gap-1")
        self._render()

    @property
    def valori(self) -> list[Partecipante]:
        return [p for p in self._righe if p.nome.strip()]

    def aggiungi(self, p: Partecipante) -> None:
        self._righe.append(p)
        self._render()

    def sostituisci(self, adm: list[Partecipante]) -> None:
        self._righe = [p.model_copy() for p in adm]
        self._render()

    def _render(self) -> None:
        self._box.clear()
        with self._box:
            with ui.row().classes("w-full no-wrap gap-1 text-xs text-slate-500"):
                ui.label("Ruolo").classes("w-1/2")
                ui.label("Ufficio").classes("w-1/6")
                ui.label("Nome").classes("w-1/4")
            for i, p in enumerate(self._righe):
                with ui.row().classes("w-full items-center no-wrap gap-1 lv-riga"):
                    ui.input(value=p.ruolo, on_change=lambda e, p=p: setattr(p, "ruolo", e.value or "")) \
                        .props("dense outlined").classes("w-1/2")
                    ui.input(value=p.ufficio, on_change=lambda e, p=p: setattr(p, "ufficio", e.value or "")) \
                        .props("dense outlined").classes("w-1/6")
                    ui.input(value=p.nome, on_change=lambda e, p=p: setattr(p, "nome", e.value or "")) \
                        .props("dense outlined").classes("w-1/4")
                    ui.button(icon="arrow_upward", on_click=lambda i=i: self._mv(i, -1)).props("flat dense")
                    ui.button(icon="arrow_downward", on_click=lambda i=i: self._mv(i, 1)).props("flat dense")
                    ui.button(icon="delete", on_click=lambda i=i: self._rm(i)).props("flat dense color=negative")

    def _mv(self, i: int, d: int) -> None:
        self._righe = sposta(self._righe, i, d)
        self._render()

    def _rm(self, i: int) -> None:
        del self._righe[i]
        self._render()


class TextareaAnteprima:
    """Textarea markdown con anteprima affiancata e contatore di paragrafi."""

    def __init__(self, testo: str, *, label: str):
        with ui.row().classes("w-full no-wrap gap-3"):
            self._ta = ui.textarea(label, value=testo).props("outlined autogrow").classes("w-1/2")
            with ui.column().classes("w-1/2"):
                self._md = ui.markdown(testo, extras=["tables"]).classes("text-sm")
                self._cnt = ui.label().classes("text-xs text-slate-500")
        self._ta.on_value_change(lambda e: self._agg(e.value or ""))
        self._agg(testo)

    def _agg(self, t: str) -> None:
        self._md.set_content(t)
        n = len([p for p in t.split("\n\n") if p.strip()])
        self._cnt.set_text(f"{n} paragrafi")

    @property
    def valore(self) -> str:
        return (self._ta.value or "").strip("\n")


import re as _re
from datetime import date as _date

_DATA_IT = _re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def data_iso(valore: str) -> str | None:
    """'GG/MM/AAAA' o 'AAAA-MM-GG' (spazi tollerati) → 'AAAA-MM-GG'; None se non è una data."""
    v = (valore or '').strip()
    m = _DATA_IT.fullmatch(v)
    if m:
        v = f'{m.group(3)}-{m.group(2)}-{m.group(1)}'
    try:
        return _date.fromisoformat(v).isoformat()
    except ValueError:
        return None


_GIORNI_WEEKEND = {5: 'sabato', 6: 'domenica'}


def giorno_weekend(valore: str) -> str | None:
    """'sabato'/'domenica' se la data (ISO o GG/MM/AAAA) cade nel fine settimana, altrimenti None (anche se non è una data)."""
    iso = data_iso(valore)
    return _GIORNI_WEEKEND.get(_date.fromisoformat(iso).weekday()) if iso else None


def campo_data(label: str, value: str = '', *, formato: str = 'iso', props: str = 'dense outlined', classes: str = 'w-56',
               conferma_weekend: bool = False) -> ui.input:
    """Campo data con pulsante calendario: il picker scrive nel formato del campo ('iso' = AAAA-MM-GG, 'it' = GG/MM/AAAA);
    la digitazione a mano resta possibile. Ritorna la ui.input (si usa .value come prima).
    conferma_weekend (date di riunione): se la data cade di sabato o domenica chiede conferma; "Cambia data" svuota il campo."""
    mask = 'DD/MM/YYYY' if formato == 'it' else 'YYYY-MM-DD'
    campo = ui.input(label, value=value).props(props).classes(classes)
    with campo:
        with ui.menu().props('no-parent-event') as menu:
            with ui.date(mask=mask).bind_value(campo):
                with ui.row().classes('justify-end'):
                    ui.button('Chiudi', on_click=menu.close).props('flat')
        with campo.add_slot('append'):
            ui.icon('event').on('click', menu.open).classes('cursor-pointer')
    if conferma_weekend:
        with ui.dialog() as dlg, ui.card().classes('lv-conferma-weekend'):
            msg = ui.label().classes('font-bold')
            ui.label('Le riunioni si tengono di norma nei giorni lavorativi.').classes('text-sm text-slate-600')
            with ui.row().classes('gap-3'):
                ui.button('Confermo la data', on_click=dlg.close).props('unelevated')
                ui.button('Cambia data', on_click=lambda: (campo.set_value(''), dlg.close())).props('flat')

        def controlla(e) -> None:
            giorno = giorno_weekend(e.value or '')
            if giorno:
                menu.close()
                msg.set_text(f'{e.value}: è {giorno}. Confermi la data della riunione?')
                dlg.open()
        campo.on_value_change(controlla)
    return campo


def campo_ora(label: str = 'Ora', value: str = '10:00', *, props: str = 'dense outlined', classes: str = 'w-28') -> ui.input:
    """Campo orario HH:MM con pulsante orologio (time picker a passi di 5 minuti); digitazione a mano possibile."""
    campo = ui.input(label, value=value).props(props).classes(classes)
    with campo:
        with ui.menu().props('no-parent-event') as menu:
            with ui.time(mask='HH:mm').props('format24h :minute-options="[0,5,10,15,20,25,30,35,40,45,50,55]"')                     .bind_value(campo):
                with ui.row().classes('justify-end'):
                    ui.button('Chiudi', on_click=menu.close).props('flat')
        with campo.add_slot('append'):
            ui.icon('schedule').on('click', menu.open).classes('cursor-pointer')
    return campo


ORGANIZZAZIONI = ['ADM', 'SOGEI', 'Altro']


def dialogo_nuova_persona(idx, on_creata=None) -> ui.dialog:
    """Dialogo che crea Anagrafica/<Nome>.md (writers.crea_persona). on_creata(nome): se dato, viene chiamato
    al posto del reload della pagina (inserimento al volo da un campo persona)."""
    from leviathadm.vault import writers
    with ui.dialog() as d, ui.card().classes('w-[560px] max-w-full'):
        ui.label('Nuova persona').classes('text-lg font-bold')
        nome = ui.input('Nome Cognome').classes('w-full')
        org = ui.select(ORGANIZZAZIONI, value='ADM', label='Organizzazione').classes('w-40')
        direzione = ui.input('Direzione (sigla, es. DOTD)').classes('w-full')
        ufficio = ui.input('Ufficio').classes('w-full')
        email = ui.input('Email').classes('w-full')
        ruolo = ui.input('Ruolo tipico (PM, RA, RP, RB, referente…)').classes('w-full')

        def crea() -> None:
            try:
                out = writers.crea_persona(idx.root, nome.value or '', organizzazione=org.value or 'ADM',
                                           direzione=(direzione.value or '').strip(), ufficio=(ufficio.value or '').strip(),
                                           email=(email.value or '').strip(), ruolo_tipico=(ruolo.value or '').strip())
            except FileExistsError:
                ui.notify('Esiste già una scheda con questo nome.', type='negative')
                return
            except (ValueError, writers.ConflittoModifica) as e:
                ui.notify(str(e), type='negative', close_button=True)
                return
            idx.reload([out])
            d.close()
            ui.notify(f'Creata {out.name}.', type='positive')
            if on_creata:
                on_creata(out.stem)
            else:
                ui.navigate.reload()
        with ui.row().classes('gap-3'):
            ui.button('Crea', icon='person_add', on_click=crea).props('unelevated')
            ui.button('Annulla', on_click=d.close).props('flat')
    return d


def campo_persona(label: str, value: str, persone: list[str], *, idx=None, classes: str = 'w-64') -> ui.select:
    """Campo per un nome di persona: suggerimenti dall'Anagrafica, ma accetta anche testo libero
    (es. 'Ortensia - Maestrale' per due RP). Si legge con .value come una ui.input.
    Con idx, l'icona a destra apre "Nuova persona": la scheda viene creata e il nome selezionato."""
    opzioni = sorted(set(persone) | ({value} if value else set()))
    sel = ui.select(opzioni, value=value or None, label=label, with_input=True, new_value_mode='add-unique',) \
        .props('clearable use-input input-debounce=0').classes(classes)
    if idx is not None:
        def creata(nome: str) -> None:
            if nome not in sel.options:
                sel.options.append(nome)
                sel.options.sort()
                sel.update()
            sel.value = nome
        dlg = dialogo_nuova_persona(idx, on_creata=creata)
        with sel.add_slot('append'):
            ui.icon('person_add').on('click', dlg.open).classes('cursor-pointer').tooltip('Nuova persona in Anagrafica')
    return sel
