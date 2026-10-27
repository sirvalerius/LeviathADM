"""Unica porta di scrittura sul vault. Frontmatter via mail_utils (writer unico, SCHEMA.md)."""
from __future__ import annotations
import re
import shutil
from datetime import date
from pathlib import Path

from . import paths as _paths  # noqa: F401  (inserisce scripts/ in sys.path prima degli import sotto)
from . import cruscotto as _cruscotto  # noqa: F401  (allinea la radice dei moduli script a VAULT_ROOT)
from mail_utils import update_frontmatter_keys  # noqa: E402
from build_project_pages import write_release_page  # noqa: E402

from .parsers import Blocco, ricomponi, spezza_sezioni, split_body


class ConflittoModifica(Exception):
    def __init__(self, path: Path):
        super().__init__(f"File cambiato sul disco: {path.name} — ricarica la pagina e riprova")
        self.path = path


class ScritturaSospesa(ConflittoModifica):
    """Un'azione (es. Sync) è in corso: nessuna scrittura finché non termina. Sottoclasse di
    ConflittoModifica così ogni pagina la intercetta già; il messaggio dice cosa aspettare."""
    def __init__(self, azione_id: str):
        Exception.__init__(self, f"Azione in corso ({azione_id}): attendi che finisca prima di modificare")
        self.path = None
        self.azione_id = azione_id


def _libero() -> None:
    from .esecutore import in_corso
    azione = in_corso()
    if azione:
        raise ScritturaSospesa(azione)


def _guardia(path: Path, expected_mtime_ns: int) -> None:
    _libero()
    try:
        attuale = path.stat().st_mtime_ns
    except FileNotFoundError:
        raise ConflittoModifica(path) from None
    if attuale != expected_mtime_ns:
        raise ConflittoModifica(path)


def _spezza_file(text: str) -> tuple[str, str, list[Blocco]]:
    corpo = split_body(text)
    fm_raw = text[: len(text) - len(corpo)]
    pre, blocchi = spezza_sezioni(corpo)
    return fm_raw, pre, blocchi


def update_frontmatter(path: Path, updates: dict[str, str], expected_mtime_ns: int) -> int:
    _guardia(path, expected_mtime_ns)
    update_frontmatter_keys(path, updates)
    return path.stat().st_mtime_ns


def avanza_stato_dopo(scheda: Path) -> tuple[str, str] | None:
    """Avanzamento automatico dello stato dopo la scrittura di una milestone nella scheda
    (avanza_stato.avanza_scheda: solo in avanti, mai Rinominato, mai con stato_manuale). Mai un errore:
    la scrittura principale è già avvenuta e non va invalidata. Ritorna (da, a) o None."""
    try:
        import avanza_stato
        return avanza_stato.avanza_scheda(Path(scheda))
    except Exception:  # noqa: BLE001
        return None


def salva_sezioni(path: Path, bodies: dict[str, str], expected_mtime_ns: int) -> int:
    """Riscrive solo le sezioni elencate (body verbatim dopo la riga heading); heading assenti
    vengono aggiunti in coda, nell'ordine dato. Tutto il resto resta identico."""
    _guardia(path, expected_mtime_ns)
    fm_raw, pre, blocchi = _spezza_file(path.read_text(encoding="utf-8"))
    presenti = {b.heading for b in blocchi}
    for b in blocchi:
        if b.heading in bodies:
            b.body = bodies[b.heading]
            if not b.riga.endswith("\n"):
                b.riga += "\n"
    for heading, body in bodies.items():
        if heading not in presenti:
            if blocchi and not blocchi[-1].body.endswith("\n"):
                blocchi[-1].body += "\n"
            elif not blocchi and pre and not pre.endswith("\n"):
                pre += "\n"
            blocchi.append(Blocco(riga=f"## {heading}\n", heading=heading, body=body))
    path.write_text(fm_raw + ricomponi(pre, blocchi), encoding="utf-8")
    return path.stat().st_mtime_ns


def replace_section(path: Path, heading: str, new_body: str, expected_mtime_ns: int) -> int:
    """Compatibilità Fondamenta: una sola sezione; se manca viene aggiunta con una riga vuota prima."""
    _guardia(path, expected_mtime_ns)
    _, _, blocchi = _spezza_file(path.read_text(encoding="utf-8"))
    if heading not in {b.heading for b in blocchi}:
        if blocchi and not blocchi[-1].body.endswith("\n\n"):
            ultimo = blocchi[-1].body
            expected_mtime_ns = salva_sezioni(
                path, {blocchi[-1].heading: ultimo + ("\n" if ultimo.endswith("\n") else "\n\n")}, expected_mtime_ns)
        new_body = new_body if new_body.startswith("\n") else "\n" + new_body
        if not new_body.endswith("\n"):
            new_body += "\n"
    return salva_sezioni(path, {heading: new_body}, expected_mtime_ns)


def aggiungi_riunione(scheda: Path, data_iso: str, fase_tab: str, trascritto: str, stem: str,
                      expected_mtime_ns: int) -> int:
    """Nuova riga in coda alla tabella ## Riunioni (4 o 5 colonne come l'intestazione; sostituisce
    la riga segnaposto `| — | — | — | — |` delle schede appena generate). Poi avanza lo stato."""
    _aggiungi_riunione(scheda, data_iso, fase_tab, trascritto, stem, expected_mtime_ns)
    avanza_stato_dopo(scheda)
    return scheda.stat().st_mtime_ns


def _aggiungi_riunione(scheda: Path, data_iso: str, fase_tab: str, trascritto: str, stem: str,
                       expected_mtime_ns: int) -> int:
    _guardia(scheda, expected_mtime_ns)
    _, _, blocchi = _spezza_file(scheda.read_text(encoding="utf-8"))
    b = next((x for x in blocchi if x.heading == "Riunioni"), None)
    res = f"[[{stem}]]" if stem != "—" else "—"          # "—": riunione senza resoconto (fonti caricate prima)
    riga5 = f"| {data_iso} | {fase_tab} | `{trascritto}` | {res} | ❌ |"
    riga4 = f"| {data_iso} | {fase_tab} | {res} | ❌ |"
    if b is None:
        body = ("\n| Data | Fase | Trascritto | Resoconto | Inviato |\n"
                "|------|------|-----------|-----------|---------|\n" + riga5 + "\n\n")
        return salva_sezioni(scheda, {"Riunioni": body}, expected_mtime_ns)
    righe = b.body.split("\n")
    idx_tab = [i for i, r in enumerate(righe) if r.strip().startswith("|")]
    if not idx_tab:
        body = b.body.rstrip("\n") + ("\n\n" if b.body.strip() else "\n") + \
            "| Data | Fase | Trascritto | Resoconto | Inviato |\n|------|------|-----------|-----------|---------|\n" + riga5 + "\n\n"
        return salva_sezioni(scheda, {"Riunioni": body}, expected_mtime_ns)
    header = [c.strip() for c in righe[idx_tab[0]].strip().strip("|").split("|")]
    nuova = riga5 if len(header) >= 5 else riga4
    # riga della stessa riunione già presente senza resoconto (fonti caricate prima): la completo, non la duplico
    for i in idx_tab[2:]:
        celle = [c.strip() for c in righe[i].strip().strip("|").split("|")]
        if len(celle) >= 4 and celle[0] == data_iso and celle[1] == fase_tab and celle[-2] == "—":
            celle[-2] = res
            if len(celle) >= 5 and trascritto and not celle[2].strip("` "):
                celle[2] = f"`{trascritto}`"
            righe[i] = "| " + " | ".join(celle) + " |"
            return salva_sezioni(scheda, {"Riunioni": "\n".join(righe)}, expected_mtime_ns)
    ultima = idx_tab[-1]
    if set(righe[ultima].replace("|", "").split()) <= {"—", "-"}:
        righe[ultima] = nuova
    else:
        righe.insert(ultima + 1, nuova)
    return salva_sezioni(scheda, {"Riunioni": "\n".join(righe)}, expected_mtime_ns)


def completa_riga_riunione(scheda: Path, data_iso: str, fase_tab: str, trascritto: str, expected_mtime_ns: int) -> bool:
    """Scrive il nome del trascritto nella riga Riunioni (data, fase) se la colonna è vuota; se la riga manca la
    aggiunge (resoconto "—"); se ha già un trascritto non tocca nulla (False). Tabelle a 4 colonne: solo aggiunta.
    Se scrive, poi avanza lo stato."""
    scritto = _completa_riga_riunione(scheda, data_iso, fase_tab, trascritto, expected_mtime_ns)
    if scritto:
        avanza_stato_dopo(scheda)
    return scritto


def _completa_riga_riunione(scheda: Path, data_iso: str, fase_tab: str, trascritto: str, expected_mtime_ns: int) -> bool:
    _guardia(scheda, expected_mtime_ns)
    _, _, blocchi = _spezza_file(scheda.read_text(encoding="utf-8"))
    b = next((x for x in blocchi if x.heading == "Riunioni"), None)
    righe = b.body.split("\n") if b else []
    idx_tab = [i for i, r in enumerate(righe) if r.strip().startswith("|")]
    header = [c.strip() for c in righe[idx_tab[0]].strip().strip("|").split("|")] if idx_tab else []
    for i in idx_tab[2:]:
        celle = [c.strip() for c in righe[i].strip().strip("|").split("|")]
        if len(celle) >= 4 and celle[0] == data_iso and celle[1] == fase_tab:
            if len(header) < 5:
                return False                              # nessuna colonna trascritto
            if celle[2].strip("` "):
                return False                              # già presente: mai sovrascrivere
            celle[2] = f"`{trascritto}`"
            righe[i] = "| " + " | ".join(celle) + " |"
            salva_sezioni(scheda, {"Riunioni": "\n".join(righe)}, expected_mtime_ns)
            return True
    _aggiungi_riunione(scheda, data_iso, fase_tab, trascritto, "—", expected_mtime_ns)
    return True


def riporta_in_bozza(md_path: Path, scheda_path: Path) -> Path:
    """Regola CLAUDE.md 'Rettifica': il resoconto torna nello stato precedente all'invio
    (file fuori da inviati/, inviato: false, scadenza vuota, ❌ nella scheda)."""
    _libero()
    if md_path.parent.name != "inviati":
        raise ValueError(f"{md_path.name} non è in inviati/")
    dest_dir = md_path.parent.parent
    # stesso stem: .md/.docx/.msg/.pdf/.eml — non " - definitivo". Il .msg è la mail GIÀ INVIATA: non torna
    # in bozza, viene eliminato così il sync ne genera uno nuovo con il .docx corretto.
    files = [f for f in md_path.parent.glob(md_path.stem + ".*") if f.suffix != ".msg"]
    collisioni = [f.name for f in files if (dest_dir / f.name).exists()]
    if collisioni:
        raise FileExistsError(f"già presenti nella cartella del rilascio: {', '.join(collisioni)}")
    files.sort(key=lambda f: f.suffix == ".md")      # il .md per ultimo: finché non si muove, lo stato resta coerente
    spostati: list[tuple[Path, Path]] = []
    try:
        for f in files:
            dest = dest_dir / f.name
            shutil.move(str(f), str(dest))
            spostati.append((f, dest))
    except OSError:
        for src, dest in reversed(spostati):     # ripristina quanto già spostato
            shutil.move(str(dest), str(src))
        raise
    for f in md_path.parent.glob(md_path.stem + ".msg"):
        f.unlink()
    nuovo = dest_dir / md_path.name
    update_frontmatter_keys(nuovo, {"inviato": "false", "data_scadenza_approvazione": ""})
    set_riunione_inviata(scheda_path, md_path.stem, False, scheda_path.stat().st_mtime_ns)
    return nuovo


def rigenera_docx(md_path: Path, expected_mtime_ns: int) -> tuple[Path, int]:
    """Identico a scripts/rigenera_resoconto.py: forza DATA COMPILAZIONE a oggi, genera il .docx,
    rimuove il .msg obsoleto (il sync lo rigenera)."""
    _guardia(md_path, expected_mtime_ns)
    if md_path.parent.name == "inviati":
        raise ValueError("resoconto già inviato: prima 'Riporta in bozza' (regola di rettifica), poi rigenera")
    _, _, blocchi = _spezza_file(md_path.read_text(encoding="utf-8"))
    headings = {b.heading for b in blocchi}
    if not {"RIUNIONE", "OBIETTIVO"} <= headings:
        raise ValueError("resoconto senza le sezioni ## RIUNIONE/OBIETTIVO (export docx2md?): "
                         "il .docx generato sarebbe vuoto")
    from rigenera_resoconto import parse_resoconto_md, _forza_data_compilazione_oggi
    from fill_template import fill_resoconto
    data = parse_resoconto_md(md_path)
    _forza_data_compilazione_oggi(md_path, data)
    out = fill_resoconto(data, md_path.with_suffix(".docx"))
    msg = md_path.with_suffix(".msg")
    if msg.exists():
        msg.unlink()
    return Path(out), md_path.stat().st_mtime_ns


def salva_verbale(doc) -> int:
    """Riscrive le tre sezioni del Verbale dallo stesso elenco e aggiorna esito_collaudo/aggiornato."""
    from .resoconti import MAPPA_ESITO, sezioni_verbale
    m = salva_sezioni(doc.path, sezioni_verbale(doc), doc.mtime_ns)
    return update_frontmatter(doc.path, {"esito_collaudo": MAPPA_ESITO.get(doc.esito_complessivo, ("", ""))[0],
                                         "aggiornato": date.today().isoformat()}, m)


def _collisioni_in_inviati(src: Path, estensioni: tuple[str, ...]) -> list[str]:
    inviati = src.parent / "inviati"
    return [src.with_suffix(e).name for e in estensioni
            if src.with_suffix(e).exists() and (inviati / src.with_suffix(e).name).exists()]


def _verifica_non_aperti(src: Path, estensioni: tuple[str, ...]) -> None:
    """Lo script scrive il frontmatter e poi sposta: un .docx aperto in Word lascerebbe metà lavoro
    fatto. Un file con share-deny (Word/Outlook) non si apre nemmeno in lettura-scrittura."""
    for e in estensioni:
        p = src.with_suffix(e)
        if p.exists():
            try:
                with open(p, "r+b"):
                    pass
            except PermissionError:
                raise PermissionError(f"{p.name} è aperto in un altro programma (Word/Outlook?): chiudilo e riprova") from None


def archivia_bozza(md_path: Path, expected_mtime_ns: int) -> Path:
    """Come la checkbox di Bozze da inviare.md: inviato: true + scadenza +5gg lavorativi, file in
    inviati/, ✅ nella scheda (delega ad archivia_inviati). Rifiuta collisioni: lo script sovrascrive."""
    _guardia(md_path, expected_mtime_ns)
    if md_path.parent.name == "inviati":
        raise ValueError(f"{md_path.name} è già in inviati/")
    coll = _collisioni_in_inviati(md_path, (".md", ".docx", ".msg"))
    if coll:
        raise FileExistsError(f"già presenti in inviati/: {', '.join(coll)}")
    _verifica_non_aperti(md_path, (".md", ".docx", ".msg"))
    import archivia_inviati
    if not archivia_inviati._archivia_bozza(md_path.stem):
        raise ValueError(f"{md_path.name} non trovato nella root del rilascio")
    return md_path.parent / "inviati" / md_path.name


def archivia_convocazione(eml_path: Path) -> Path:
    _libero()
    coll = _collisioni_in_inviati(eml_path, (".eml", ".ics"))
    if coll:
        raise FileExistsError(f"già presenti in inviati/: {', '.join(coll)}")
    import archivia_inviati
    if not archivia_inviati._archivia_convocazione(eml_path.stem):
        raise ValueError(f"{eml_path.name} non trovata nella root del rilascio")
    return eml_path.parent / "inviati" / eml_path.name


def segna_definitivo_inviato(md_path: Path, expected_mtime_ns: int) -> int:
    return update_frontmatter(md_path, {"definitivo_inviato": "true"}, expected_mtime_ns)


def registra_collaudo(scheda: Path, data_iso: str, expected_mtime_ns: int, *, oggi: date | None = None) -> int:
    """Come la colonna 'Data collaudo effettiva' di Da collaudare.md, ma rifiuta le date future
    (lo script le accetta e le viste a valle le ignorano in silenzio)."""
    d = date.fromisoformat(data_iso)              # ValueError se non ISO
    if d > (oggi or date.today()):
        raise ValueError(f"data futura: {data_iso}")
    update_frontmatter(scheda, {"data_collaudo_effettiva": d.isoformat()}, expected_mtime_ns)
    avanza_stato_dopo(scheda)
    return scheda.stat().st_mtime_ns


def segna_lettera(scheda: Path, field_base: str, stato: str, expected_mtime_ns: int) -> int:
    if stato not in ("in_firma", "protocollata"):
        raise ValueError(f"stato lettera non valido: {stato}")
    update_frontmatter(scheda, {f"{field_base}_{stato}": "true"}, expected_mtime_ns)
    avanza_stato_dopo(scheda)
    return scheda.stat().st_mtime_ns


def chiudi_approvazione_tacita(md_path: Path, expected_mtime_ns: int, *, oggi: date | None = None) -> int:
    """Solo frontmatter: data_approvazione = data_scadenza_approvazione (regola di chiudi_approvazione).
    PDF e .msg definitivo li completa il sync del master (chiudi_approvazione.find_approvati_incompleti)."""
    from mail_utils import parse_frontmatter
    fm = parse_frontmatter(md_path)
    if fm.get("inviato", "").lower() != "true":
        raise ValueError("resoconto non inviato")
    if fm.get("data_approvazione", "").strip():
        raise ValueError("approvazione già registrata")
    scadenza = fm.get("data_scadenza_approvazione", "").strip()
    if not scadenza:
        raise ValueError("senza data_scadenza_approvazione")
    if date.fromisoformat(scadenza) > (oggi or date.today()):
        raise ValueError(f"scadenza futura: {scadenza}")
    return update_frontmatter(md_path, {"data_approvazione": scadenza}, expected_mtime_ns)


def crea_persona(root: Path, nome: str, *, organizzazione: str = "ADM", direzione: str = "", ufficio: str = "",
                 email: str = "", ruolo_tipico: str = "") -> Path:
    """Nuova scheda Anagrafica/<Nome Cognome>.md nello stesso formato degli stub di update_anagrafica
    (frontmatter + titolo + wikilink alle strutture). FileExistsError se esiste."""
    nome = " ".join(nome.split())
    if not nome:
        raise ValueError("nome vuoto")
    if any(c in nome for c in '\\/:*?"<>|'):
        raise ValueError("il nome non può contenere \\ / : * ? \" < > |")
    out = root / "Anagrafica" / f"{nome}.md"
    link = [s for s in (direzione, ufficio) if s] or [organizzazione]
    testo = ("---\n" f"organizzazione: {organizzazione}\n" f"direzione: {direzione}\n" f"ufficio: {ufficio}\n"
             f"email: {email}\n" f"ruolo_tipico: {ruolo_tipico}\n" "---\n\n" f"# {nome}\n\n"
             + "".join(f"[[{s}]]\n" for s in link))
    crea_file(out, testo)
    return out


def scrivi_testo(path: Path, text: str) -> int:
    """Crea o sovrascrive un file di testo del vault (es. Proposta Copilot incollata: l'ultima parola è dell'utente)."""
    _libero()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path.stat().st_mtime_ns


def crea_file(path: Path, text: str) -> int:
    _libero()
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path.stat().st_mtime_ns


def set_riunione_inviata(path: Path, resoconto_stem: str, inviata: bool, expected_mtime_ns: int) -> int:
    """✅/❌ nella riga Riunioni del resoconto; se cambia qualcosa, poi avanza lo stato."""
    if _set_riunione_inviata(path, resoconto_stem, inviata, expected_mtime_ns):
        avanza_stato_dopo(path)
    return path.stat().st_mtime_ns


def _set_riunione_inviata(path: Path, resoconto_stem: str, inviata: bool, expected_mtime_ns: int) -> bool:
    _guardia(path, expected_mtime_ns)
    text = path.read_text(encoding="utf-8")
    da, a = ("❌", "✅") if inviata else ("✅", "❌")
    pattern = rf"(\|[^\n]*\[\[{re.escape(resoconto_stem)}[^\]]*\]\][^\n]*)\|\s*{da}\s*\|"
    nuovo = re.sub(pattern, rf"\1| {a} |", text)
    if nuovo != text:
        path.write_text(nuovo, encoding="utf-8")
        return True
    return False


def crea_rilascio(rel: dict, piano_root: Path) -> Path:
    _libero()
    cod = rel["cod_rilascio"]
    out = piano_root / cod / f"{cod}.md"
    if out.exists():
        raise FileExistsError(out)
    try:
        write_release_page(rel, piano_root / cod)
    except ValueError:
        # write_release_page stampa out.relative_to(VAULT) dopo aver scritto: fuori dal
        # vault reale (test, altro piano) la stampa fallisce ma il file c'è già.
        if not out.exists():
            raise
    return out
