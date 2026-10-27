"""
Proposta Copilot — il file che un agente Copilot 365 (o l'utente, incollando) scrive in
`PO <anno>/<codice>/_fonti/<AAAAMMGG Fase>/Proposta Copilot.md` con le sezioni di giudizio del resoconto:
PARTECIPANTI (facoltativa), ARGOMENTI TRATTATI, AZIONI CONCORDATE, NOTE PER IL PM.
LeviathADM la importa nello scheletro del nuovo resoconto ("Importa da Copilot"); replica JS in
leviathadm_web/src/43_proposta.js (golden `proposta_copilot`). Contratto: SCHEMA.md, sezione "Proposta Copilot";
design: docs/superpowers/specs/2026-10-27-copilot-resoconto-design.md.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import parse_frontmatter  # noqa: E402

NOME = "Proposta Copilot.md"
TIPO = "proposta_copilot"
SEZIONI = ("PARTECIPANTI", "ARGOMENTI TRATTATI", "AZIONI CONCORDATE", "NOTE PER IL PM")
SEGNAPOSTO = ("CODICE", "DESCRIZIONE_RILASCIO", "FASE", "DATA", "PERCORSO_TRASCRITTO", "PERCORSO_PROPOSTA")
_H2 = re.compile(r"^##(?!#)\s*(.+?)\s*:?\s*$")   # solo `##`: un `###` resta testo della sezione
_BULLET = re.compile(r"^\s*[-*•]\s+")
_NOME_CARTELLA_OK = re.compile(r"^[^\\/:*?\"<>|]+$")   # niente separatori o caratteri vietati nei nomi di cartella
_FM = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n?", re.S)


def _normalizza(text: str) -> str:
    return text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")


def _senza_frontmatter(text: str) -> str:
    return _FM.sub("", text, count=1) if text.startswith("---") else text


def _nomi(riga: str) -> list[str]:
    return [n.strip() for n in riga.split(";") if n.strip()]


def parse_proposta(text: str) -> dict:
    """{"frontmatter", "partecipanti": {"adm", "sogei"}, "argomenti", "azioni", "note"}: sezioni assenti vuote,
    intestazioni senza distinzione di maiuscole e con `:` finale ammesso, bullet `-`/`*`/`•`, BOM e CRLF normalizzati."""
    text = _normalizza(text or "")
    fm = parse_frontmatter(text) if text.startswith("---") else {}
    corpo = _senza_frontmatter(text)
    sezioni: dict[str, list[str]] = {}
    corrente = None
    for riga in corpo.split("\n"):
        m = _H2.match(riga)
        if m:
            nome = m.group(1).strip().upper()
            corrente = nome if nome in SEZIONI else None
            if corrente:
                sezioni.setdefault(corrente, [])
            continue
        if corrente:
            sezioni[corrente].append(riga)
    part = {"adm": [], "sogei": []}
    for riga in sezioni.get("PARTECIPANTI", []):
        m = re.match(r"^\s*(?:[-*•]\s*)?\**\s*(ADM|SOGEI)\s*\**\s*:\s*(.*)$", riga, re.I)   # anche puntato: `- **ADM**: …`
        if m:
            part[m.group(1).lower()] = _nomi(m.group(2))
    argomenti = re.sub(r"\n{3,}", "\n\n", "\n".join(sezioni.get("ARGOMENTI TRATTATI", []))).strip()
    elenco = lambda nome: [_BULLET.sub("", r).strip() for r in sezioni.get(nome, []) if r.strip()]  # noqa: E731
    return {"frontmatter": fm, "partecipanti": part, "argomenti": argomenti,
            "azioni": elenco("AZIONI CONCORDATE"), "note": elenco("NOTE PER IL PM")}


def componi_proposta(testo: str, *, codice: str, data_iso: str, fase_tab: str, fonte: str, oggi: date | None = None) -> str:
    """Frontmatter generato da LeviathADM + testo (senza frontmatter proprio), LF, senza BOM."""
    corpo = _senza_frontmatter(_normalizza(testo)).strip("\n")
    fm = (f"---\ntipo: {TIPO}\ncodice_rilascio: {codice}\ndata_riunione: {data_iso}\nfase: {fase_tab}\n"
          f"fonte: {fonte}\ngenerato: {(oggi or date.today()).isoformat()}\n---\n\n")
    return fm + corpo + "\n"


def _fase_chiave(fase: str) -> str:
    return re.sub(r"\s+", " ", (fase or "").replace("#", "")).strip().lower()


def compatibile(fm: dict, codice: str, data_iso: str, fase_tab: str) -> bool:
    """Frontmatter vuoto = compatibile (proposta incollata); altrimenti codice, data e fase (senza `#`, maiuscole) devono coincidere."""
    if not fm:
        return True
    if fm.get("tipo", TIPO).strip() != TIPO:
        return False
    return ((fm.get("codice_rilascio") or codice).strip() == codice
            and (fm.get("data_riunione") or data_iso).strip() == data_iso
            and _fase_chiave(fm.get("fase") or fase_tab) == _fase_chiave(fase_tab))


def percorso_proposta(rilascio_dir: Path, data_iso: str, fase_tab: str) -> Path:
    """Percorso canonico (= fonti.cartella_fonti / NOME). Fase e data sono testo libero dell'interfaccia:
    niente separatori né `..`, così il file resta sotto _fonti/ del rilascio."""
    if not _NOME_CARTELLA_OK.match(fase_tab or "") or not _NOME_CARTELLA_OK.match(data_iso or "") or ".." in (fase_tab, data_iso):
        raise ValueError(f"fase o data non ammesse nel nome della cartella: {data_iso!r} {fase_tab!r}")
    return Path(rilascio_dir) / "_fonti" / f"{data_iso.replace('-', '')} {fase_tab}" / NOME


def trova_proposta(rilascio_dir: Path, data_iso: str, fase_tab: str) -> Path | None:
    """Prima la cartella canonica, poi ogni _fonti/**/Proposta Copilot.md (ordine per percorso minuscolo, come la web)
    con frontmatter compatibile e con data_riunione e fase dichiarate (senza frontmatter vale solo nella canonica: fuori,
    una proposta senza data/fase combacerebbe con ogni riunione). Una proposta di un'altra riunione non viene mai restituita."""
    rilascio_dir = Path(rilascio_dir)
    codice = rilascio_dir.name
    try:
        canon = percorso_proposta(rilascio_dir, data_iso, fase_tab)
    except ValueError:
        return None
    candidati = ([canon] if canon.exists() else []) + sorted(
        (p for p in (rilascio_dir / "_fonti").rglob(NOME) if p != canon), key=lambda p: p.as_posix().lower()) if (rilascio_dir / "_fonti").exists() else []
    for p in candidati:
        try:
            fm = parse_frontmatter(_normalizza(p.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
        if p != canon and not (fm.get("data_riunione", "").strip() and fm.get("fase", "").strip()):
            continue
        if compatibile(fm, codice, data_iso, fase_tab):
            return p
    return None


def prompt_copilot(template: str, campi: dict) -> str:
    """Sostituisce i segnaposto {{NOME}} del template; quelli senza valore diventano "(non disponibile)"."""
    def val(m: re.Match) -> str:
        v = (campi.get(m.group(1)) or "").strip()
        return v or "(non disponibile)"
    return re.sub(r"\{\{([A-Z_]+)\}\}", val, template)
