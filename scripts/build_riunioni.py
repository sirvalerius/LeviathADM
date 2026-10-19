"""
Genera PO 2026/Riunioni.md dalla tabella `## Riunioni` e dalla sezione
`## Prossima riunione` di ciascuna scheda rilascio.

- "Ultima riunione": ultima riga della tabella Riunioni della scheda
  (fase · GG/MM), con "(POSITIVO/NEGATIVO/con riserva)" se il resoconto di
  collaudo collegato lo dichiara nel corpo.
- "Resoconto": wikilink della tabella, etichettato "inviato"/"bozza" in base
  al frontmatter `inviato` del file resoconto stesso.
- "Prossima riunione": testo libero della sezione omonima della scheda
  (manutenuta dal PM dopo ogni resoconto — v. CLAUDE.md step 8).

Uso:
    python scripts/build_riunioni.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

VAULT = Path(__file__).parent.parent
LAVORI = VAULT / "PO 2026"
OUT = LAVORI / "Riunioni.md"

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import parse_frontmatter  # noqa: E402

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)")
ESITO_RE = re.compile(r"esito\s*\**\s*(POSITIVO|NEGATIVO|con riserva)", re.IGNORECASE)


def _releases_in_scope() -> list[Path]:
    out = []
    for d in sorted(LAVORI.glob("ADM*")):
        if not d.is_dir() or "(" in d.name:
            continue
        if (d / f"{d.name}.md").exists():
            out.append(d)
    return out


def _section(text: str, heading: str) -> str:
    lines = text.splitlines()
    out, in_sec = [], False
    for line in lines:
        if line.strip().startswith("## "):
            if in_sec:
                break
            in_sec = line.strip() == heading
            continue
        if in_sec:
            out.append(line)
    return "\n".join(out).strip()


def _riunioni_rows(text: str) -> list[list[str]]:
    body = _section(text, "## Riunioni")
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|-") or "Data" in line and "Fase" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 4 and cells[0] not in ("—", "-"):
            rows.append(cells)
    return rows


def _find_resoconto_file(release_dir: Path, wikilink_target: str) -> Path | None:
    for sub in ("", "inviati"):
        p = release_dir / sub / f"{wikilink_target}.md" if sub else release_dir / f"{wikilink_target}.md"
        if p.exists():
            return p
    return None


def _esito_suffix(resoconto_path: Path | None) -> str:
    """Esito del collaudo dal corpo del resoconto — solo se il resoconto è
    stato realmente inviato (un esito "assunto" su una bozza pre-collaudo
    non è un fatto confermato)."""
    if resoconto_path is None:
        return ""
    fm = parse_frontmatter(resoconto_path)
    if fm.get("inviato", "").strip().lower() != "true":
        return ""
    text = resoconto_path.read_text(encoding="utf-8", errors="replace")
    m = ESITO_RE.search(text)
    return f" ({m.group(1).upper()})" if m else ""


def _resoconto_cell(release_dir: Path, raw_cell: str) -> str:
    m = WIKILINK_RE.search(raw_cell)
    if not m:
        return "—"
    target = m.group(1)
    resoconto_path = _find_resoconto_file(release_dir, target)
    inviato = False
    if resoconto_path is not None:
        fm = parse_frontmatter(resoconto_path)
        inviato = fm.get("inviato", "").strip().lower() == "true"
    label = "inviato" if inviato else "bozza"
    mark = "✅" if inviato else "❌"
    return f"[[{target}|{label}]] {mark}"


def _ultima_riunione(release_dir: Path, rows: list[list[str]]) -> tuple[str, str]:
    """Ritorna (testo ultima riunione, cella resoconto)."""
    if not rows:
        return "—", "—"
    data, fase, _trascritto, resoconto = rows[-1][0], rows[-1][1], rows[-1][2], rows[-1][3]
    try:
        gg_mm = "/".join(reversed(data.split("-")[1:])) if "-" in data else data
    except Exception:
        gg_mm = data
    target_match = WIKILINK_RE.search(resoconto)
    esito = ""
    if "collaudo" in fase.lower() and target_match and not ESITO_RE.search(fase):
        esito = _esito_suffix(_find_resoconto_file(release_dir, target_match.group(1)))
    return f"{fase} · {gg_mm}{esito}", _resoconto_cell(release_dir, resoconto)


def build() -> None:
    attivi, storici = [], []
    for release_dir in _releases_in_scope():
        text = (release_dir / f"{release_dir.name}.md").read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        cod = fm.get("codice_rilascio", release_dir.name)
        if fm.get("stato", "").strip().lower() == "rinominato":
            storici.append((cod, fm.get("codice_rilascio_successivo", "")))
            continue
        rows = _riunioni_rows(text)
        ultima, resoconto_cell = _ultima_riunione(release_dir, rows)
        prossima = _section(text, "## Prossima riunione") or "—"
        prossima = re.sub(r"\s+", " ", prossima)
        attivi.append((cod, ultima, resoconto_cell, prossima))

    attivi.sort(key=lambda r: r[0])
    storici.sort(key=lambda r: r[0])

    lines = [
        "---",
        f"aggiornato: {__import__('datetime').date.today():%Y-%m-%d}",
        "---",
        "",
        "# Riunioni — stato avanzamento",
        "",
        "> Generata da `build_riunioni.py` — non editare a mano (si rigenera a ogni sync sul"
        " master). \"Prossima riunione\" riflette la sezione omonima di ciascuna scheda:"
        " aggiornala lì, non qui.",
        "",
        "| Codice | Ultima riunione | Resoconto | Prossima riunione |",
        "|--------|----------------|-----------|-------------------|",
    ]
    for cod, ultima, resoconto_cell, prossima in attivi:
        lines.append(f"| [[{cod}]] | {ultima} | {resoconto_cell} | {prossima} |")

    if storici:
        lines += ["", "## Storico (rinominati / confluiti)", "",
                   "| Codice | Confluito in |", "|---|---|"]
        for cod, succ in storici:
            succ_link = f"[[{succ}]]" if succ else "—"
            lines.append(f"| [[{cod}]] | {succ_link} |")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Riunioni: {len(attivi)} attivi · {len(storici)} storici -> {OUT.name}")


if __name__ == "__main__":
    build()
