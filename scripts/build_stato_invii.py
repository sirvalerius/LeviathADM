"""
Genera PO 2026/Stato invii.md: matrice punti di piano × fase riunione, con lo
stato di invio (provvisorio/definitivo) di ciascun resoconto.

Fonte dati: SOLO i flag locali già usati da Bozze da inviare.md (frontmatter
`inviato` / `definitivo_inviato` / `salta_definitivo` dei resoconti in
PO 2026/*/inviati/ e delle bozze non ancora archiviate in PO 2026/*/). La
pagina si aggiorna quindi da sola ogni volta che una checkbox viene spuntata
in Bozze da inviare.md e archivia_inviati la elabora (stesso momento in cui
si rigenerano Bozze da inviare.md e Scadenze.md).

Non fa nessuna verifica contro Outlook: per quello vedi `audit_invii.py`.

Uso:
    python scripts/build_stato_invii.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

VAULT = Path(__file__).parent.parent
LAVORI = VAULT / "PO 2026"
OUT = LAVORI / "Stato invii.md"

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import salta_definitivo  # noqa: E402
from mail_utils import parse_frontmatter  # noqa: E402

RESOCONTO_RE = re.compile(r"^(ADM\d{3}-\d{2}-[0-9A-Za-z]{2}) - (\d{8}) Resoconto (.+)$")
EXCLUDE_STEM_HINTS = ("piano di test", "documentazione visiva", "verbale di collaudo", "-rev")

# Ordine canonico delle fasi note; le altre (Riunione Urgente, Aggiornamento
# Amministrativo, ecc.) vengono aggiunte in coda in ordine alfabetico, prima
# di Collaudo che chiude sempre il ciclo di vita.
_CANONICAL_PREFIX = ["Startup", "Prima Analisi", "Seconda Analisi"]
_CANONICAL_SUFFIX = ["Collaudo"]


def _normalize_fase(tipo_raw: str) -> str:
    t = tipo_raw.strip()
    tl = t.lower()
    if "startup" in tl:
        return "Startup"
    if "seconda" in tl and "analisi" in tl:
        return "Seconda Analisi"
    if "prima" in tl and "analisi" in tl:
        return "Prima Analisi"
    if tl == "analisi":
        return "Analisi"
    m = re.search(r"sal\s*#?\s*(\d+)", tl)
    if m:
        return f"SAL #{m.group(1)}"
    if "collaudo" in tl:
        return "Collaudo"
    return t  # fase atipica: mantenuta com'è (es. "Riunione Urgente")


def _releases_in_scope() -> list[Path]:
    out = []
    for d in sorted(LAVORI.glob("ADM*")):
        if not d.is_dir() or "(" in d.name:
            continue
        if (d / f"{d.name}.md").exists():
            out.append(d)
    return out


def _find_resoconto_files(release_dir: Path) -> list[Path]:
    found = []
    for glob_pat in ("inviati/*.md", "*.md"):
        for f in release_dir.glob(glob_pat):
            m = RESOCONTO_RE.match(f.stem)
            if not m:
                continue
            if any(h in f.stem.lower() for h in EXCLUDE_STEM_HINTS):
                continue
            found.append(f)
    return found


def collect() -> tuple[dict[str, dict[str, dict]], list[str]]:
    """Ritorna (matrice[codice][fase] = stato, colonne ordinate)."""
    matrix: dict[str, dict[str, dict]] = {}
    fasi_viste: set[str] = set()

    for release_dir in _releases_in_scope():
        codice = release_dir.name
        scheda_fm = parse_frontmatter(release_dir / f"{codice}.md")
        rinominato = scheda_fm.get("stato", "").strip().lower() == "rinominato"

        for f in _find_resoconto_files(release_dir):
            m = RESOCONTO_RE.match(f.stem)
            _, data_str, tipo_raw = m.groups()
            fase = _normalize_fase(tipo_raw)
            fasi_viste.add(fase)

            fm = parse_frontmatter(f)
            inviato = fm.get("inviato", "").lower() == "true"
            salta = salta_definitivo(fm)   # flag o collaudo: D➖
            definitivo_inviato = fm.get("definitivo_inviato", "").lower() == "true"
            ha_scadenza = bool(fm.get("data_scadenza_approvazione", "").strip())

            cell = matrix.setdefault(codice, {}).get(fase)
            entry = {
                "data": data_str, "inviato": inviato, "definitivo": definitivo_inviato,
                "salta": salta, "ha_scadenza": ha_scadenza, "rinominato": rinominato,
                "path": f,   # per i link di LeviathADM; non compare nella pagina
            }
            if cell is None:
                matrix.setdefault(codice, {})[fase] = [entry]
            else:
                cell.append(entry)

    # Ordine colonne: canoniche note in testa, atipiche in mezzo (alfabetico),
    # Collaudo sempre ultima.
    altre = sorted(f for f in fasi_viste
                    if f not in _CANONICAL_PREFIX and f not in _CANONICAL_SUFFIX)
    sal = sorted((f for f in fasi_viste if f.startswith("SAL #")),
                  key=lambda s: int(re.search(r"\d+", s).group()))
    altre = [f for f in altre if f not in sal]
    colonne = ([f for f in _CANONICAL_PREFIX if f in fasi_viste] + sal + altre +
               [f for f in _CANONICAL_SUFFIX if f in fasi_viste])
    return matrix, colonne


def _cell_text(entries: list[dict] | None) -> str:
    if not entries:
        return "—"
    parts = []
    for e in entries:
        p = "✅" if e["inviato"] else "❌"
        if e["salta"]:
            d = "➖"
        elif e["definitivo"]:
            d = "✅"
        elif e["inviato"] and e["ha_scadenza"]:
            d = "❌"
        else:
            d = "—"  # provvisorio non ancora inviato: il definitivo non è ancora nel ciclo
        parts.append(f"P{p} D{d}")
    return " / ".join(parts)


def build() -> None:
    matrix, colonne = collect()

    lines = [
        "# Stato invii — resoconti PO 2026",
        "",
        "> Generata da `build_stato_invii.py` — non editare a mano. Si aggiorna a ogni sync,"
        " subito dopo che una spunta in [[Bozze da inviare]] viene elaborata.",
        "",
        "Ogni cella: **P** = provvisorio inviato, **D** = definitivo inviato "
        "(✅ sì · ❌ no · ➖ non previsto, es. Collaudo · — riunione non svolta/non tracciata). "
        "Più resoconti per la stessa fase sono separati da `/`.",
        "",
    ]

    header = "| Rilascio | " + " | ".join(colonne) + " |"
    sep = "|---|" + "|".join(["---"] * len(colonne)) + "|"
    lines += [header, sep]

    for codice in sorted(matrix):
        row_fasi = matrix[codice]
        rinominato = any(e.get("rinominato") for entries in row_fasi.values() for e in entries)
        label = f"[[{codice}]]" + (" *(storico)*" if rinominato else "")
        cells = [_cell_text(row_fasi.get(fase)) for fase in colonne]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Stato invii: {len(matrix)} punti di piano × {len(colonne)} fasi -> {OUT.name}")


if __name__ == "__main__":
    build()
