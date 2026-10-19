"""Compone parser e modelli: dal file .md agli oggetti del dominio."""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path

from . import paths as _paths  # noqa: F401  (inserisce scripts/ in sys.path prima di mail_utils)
from mail_utils import parse_frontmatter  # noqa: E402

from . import parsers as P
from .models import Azione, Decisione, Nota, Protocollo, Resoconto, Riunione, Rilascio
from .paths import is_scheda_rilascio, nota_id

_SCADENZA_RE = re.compile(r"scadenza:\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", re.IGNORECASE)
_RESOCONTO_RE = re.compile(r"^(ADM[0-9A-Z-]+) - (\d{8}) Resoconto (.+?)(?: - rev\s*\d+|-rev.*)?$")
_LINK_RE = re.compile(r"\[\[([^\]|]+)")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _pulisci_sezione(testo: str) -> str:
    return _HTML_COMMENT_RE.sub("", testo).strip()


def _riunioni(sezione: str) -> list[Riunione]:
    out: list[Riunione] = []
    for row in P.parse_table(sezione):
        if len(row) == 5:
            data, fase, trascritto, resoconto, inviato = row
        elif len(row) == 4:
            data, fase, resoconto, inviato = row
            trascritto = ""
        else:
            continue
        if data in ("", "—", "-"):
            continue
        m = _LINK_RE.search(resoconto)
        out.append(Riunione(data=data, fase=fase, trascritto=trascritto,
                            resoconto_link=(m.group(1).strip() if m else ""),
                            inviato=("✅" in inviato), raw_row=row))
    return out


def _azioni(sezione: str) -> list[Azione]:
    out = []
    for chiusa, testo in P.parse_checkboxes(sezione):
        m = _SCADENZA_RE.search(testo)
        out.append(Azione(chiusa=chiusa, testo=testo, testo_pulito=P.strip_markdown_inline(testo),
                          scadenza=P.parse_data(m.group(1)) if m else None))
    return out


def _decisioni(sezione: str) -> list[Decisione]:
    out = []
    for testo in P.parse_bullets(sezione):
        prefisso, sep, resto = testo.partition(" — ")
        d = P.parse_data(prefisso) if sep else None
        out.append(Decisione(data=d, testo=P.strip_markdown_inline(resto if d else testo)))
    return out


def _protocolli(sezione: str) -> list[Protocollo]:
    return [Protocollo(tipo=r[0], documento=r[1], numero_adm=r[2], data_adm=r[3], rif_sogei=r[4], registro=r[5])
            for r in P.parse_table(sezione) if len(r) >= 6]


def parse_resoconto(path: Path, text: str) -> Resoconto:
    fm = parse_frontmatter(text)
    m = _RESOCONTO_RE.match(path.stem)
    tipo = fm.get("tipo_riunione", "").strip() or (m.group(3) if m else "")
    data = P.parse_data(fm.get("data_riunione", ""))
    if data is None and m:
        g = m.group(2)
        data = P.parse_data(f"{g[:4]}-{g[4:6]}-{g[6:]}")
    in_inviati = "inviati" in path.parts
    if fm.get("definitivo_inviato", "").lower() == "true":
        stato = "definitivo"
    elif fm.get("inviato", "").lower() == "true" or in_inviati:
        stato = "inviato"  # un file in inviati/ è stato spedito anche se il frontmatter (storico) non lo dice
    else:
        stato = "bozza"
    return Resoconto(path=path, stem=path.stem, tipo_riunione=tipo, data_riunione=data, stato=stato,
                     in_inviati=in_inviati, ha_docx=path.with_suffix(".docx").exists(),
                     ha_msg=path.with_suffix(".msg").exists(), ha_pdf=path.with_suffix(".pdf").exists(),
                     frontmatter=fm)


def trova_resoconti(cartella: Path) -> list[Resoconto]:
    files = list(cartella.glob("* - 20* Resoconto *.md")) + list((cartella / "inviati").glob("* - 20* Resoconto *.md"))
    out = [parse_resoconto(p, p.read_text(encoding="utf-8", errors="replace")) for p in files]
    return sorted(out, key=lambda r: (r.data_riunione or date.min, r.stem))


def trova_verbali(cartella: Path) -> list[Path]:
    return sorted(cartella.glob("* - 20* Verbale di Collaudo.md"))


def resoconti_non_collegati(rilascio: Rilascio) -> list[Resoconto]:
    """Resoconti presenti su disco ma non referenziati da nessuna riga di ## Riunioni
    (tipicamente le revisioni `- rev2`, spesso la versione corrente)."""
    collegati = {m.resoconto_link for m in rilascio.riunioni}
    return [r for r in rilascio.resoconti if r.stem not in collegati]


def tipo_nota(path: Path, frontmatter: dict, root: Path) -> str:
    if is_scheda_rilascio(path):
        return "rilascio"
    t = frontmatter.get("tipo", "").strip().lower()
    if t in ("progetto", "sottoprogetto", "ufficio"):
        return t
    rel = path.relative_to(root).parts
    if rel[0] == "Anagrafica":
        return "ufficio" if len(rel) > 2 and rel[1] == "Strutture" else "persona"
    if len(rel) == 2 and rel[0].startswith("PO "):
        return "pagina"
    return "nota"


def parse_nota(path: Path, text: str, root: Path, mtime_ns: int) -> Nota:
    fm = parse_frontmatter(text)
    corpo = P.split_body(text)
    return Nota(path=path, id=nota_id(root, path), titolo=P.titolo_h1(corpo) or path.stem, frontmatter=fm,
                corpo=corpo, wikilink=P.parse_wikilinks(corpo), tag=P.parse_tags(corpo),
                tipo=tipo_nota(path, fm, root), mtime_ns=mtime_ns)


def parse_rilascio(path: Path, text: str, root: Path, mtime_ns: int) -> Rilascio:
    fm = parse_frontmatter(text)
    corpo = P.split_body(text)
    sez = P.split_sections(corpo)
    problemi: list[str] = []
    if not fm.get("codice_rilascio"):
        problemi.append("frontmatter senza codice_rilascio")
    for nome in ("Riunioni", "Azioni aperte", "Decisioni chiave", "Prossima riunione"):
        if nome not in sez:
            problemi.append(f"sezione mancante: {nome}")
    return Rilascio(
        codice=fm.get("codice_rilascio", path.stem), path=path, id=nota_id(root, path), mtime_ns=mtime_ns,
        frontmatter=fm, stato=fm.get("stato", ""), descrizione_rilascio=fm.get("descrizione_rilascio", ""),
        riunioni=_riunioni(sez.get("Riunioni", "")), azioni=_azioni(sez.get("Azioni aperte", "")),
        decisioni=_decisioni(sez.get("Decisioni chiave", "")),
        protocolli=_protocolli(sez.get("Allegati protocolli", "")),
        prossima_riunione=P.strip_markdown_inline(_pulisci_sezione(sez.get("Prossima riunione", ""))),
        team_raw=sez.get("Team", "").strip(), resoconti=trova_resoconti(path.parent),
        verbali=trova_verbali(path.parent), sezioni=dict(sez), problemi=problemi)
