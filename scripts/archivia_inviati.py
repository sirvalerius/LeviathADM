"""
archivia_inviati.py — archivia i resoconti marcati come inviati nella pagina Bozze.

Legge PO 2026/Bozze da inviare.md, trova gli item con - [x], e per ciascuno:

Bozze iniziali (sezione "## Bozze iniziali"):
  1. Imposta inviato: true e data_scadenza_approvazione (5 gg lavorativi) nel frontmatter
  2. Sposta .md, .docx, .msg → ADMxxx/inviati/
  3. Aggiorna scheda rilascio ADMxxx.md: ❌ → ✅ nella riga Riunioni

Convocazioni da inviare (sezione "## Convocazioni da inviare"):
  1. Sposta la convocazione .eml (e .ics se presente) → ADMxxx/inviati/

Definitivi (sezione "## Definitivi"):
  1. Imposta definitivo_inviato: true nel frontmatter .md in inviati/
"""
from __future__ import annotations
import re
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import business_days_after, update_frontmatter_keys

VAULT = Path(__file__).parent.parent
LAVORI = VAULT / "PO 2026"
BOZZE_PAGE = LAVORI / "Bozze da inviare.md"


def _find_md_in_root(stem: str) -> Path | None:
    codice = stem.split(" - ")[0]
    candidate = LAVORI / codice / (stem + ".md")
    return candidate if candidate.exists() else None


def _find_md_in_inviati(stem: str) -> Path | None:
    codice = stem.split(" - ")[0]
    candidate = LAVORI / codice / "inviati" / (stem + ".md")
    return candidate if candidate.exists() else None


def _update_scheda_inviato(scheda: Path, stem: str) -> None:
    text = scheda.read_text(encoding="utf-8")
    pattern = rf"(\|[^\n]*\[\[{re.escape(stem)}[^\]]*\]\][^\n]*)\|\s*❌\s*\|"
    new_text = re.sub(pattern, r"\1| ✅ |", text)
    if new_text != text:
        scheda.write_text(new_text, encoding="utf-8")
        print(f"    Scheda aggiornata: {scheda.name}")


def _archivia_bozza(stem: str) -> bool:
    md_path = _find_md_in_root(stem)
    if not md_path:
        print(f"    WARN: {stem}.md non trovato nella root del rilascio")
        return False

    codice = stem.split(" - ")[0]
    inviati_dir = md_path.parent / "inviati"
    inviati_dir.mkdir(exist_ok=True)

    scadenza = business_days_after(date.today(), 5)
    update_frontmatter_keys(md_path, {
        "inviato": "true",
        "data_scadenza_approvazione": scadenza.isoformat(),
    })
    print(f"    Frontmatter: inviato=true, scadenza={scadenza.isoformat()}")

    for ext in (".md", ".docx", ".msg"):
        src = md_path.with_suffix(ext)
        if src.exists():
            dst = inviati_dir / src.name
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))
            print(f"    Spostato: {src.name} -> inviati/")

    scheda = LAVORI / codice / f"{codice}.md"
    if scheda.exists():
        _update_scheda_inviato(scheda, stem)

    return True


def _archivia_convocazione(stem: str) -> bool:
    codice = stem.split(" - ")[0]
    root = LAVORI / codice
    inviati_dir = root / "inviati"
    moved = False
    for ext in (".eml", ".ics"):
        src = root / (stem + ext)
        if src.exists():
            inviati_dir.mkdir(exist_ok=True)
            dst = inviati_dir / src.name
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))
            print(f"    Spostato: {src.name} -> inviati/")
            moved = True
    if not moved:
        print(f"    WARN: convocazione {stem} non trovata nella root del rilascio")
    return moved


def _segna_definitivo_inviato(stem: str) -> bool:
    md_path = _find_md_in_inviati(stem)
    if not md_path:
        print(f"    WARN: {stem}.md non trovato in inviati/")
        return False
    update_frontmatter_keys(md_path, {"definitivo_inviato": "true"})
    print(f"    definitivo_inviato: true → {md_path.name}")
    return True


def _parse_bozze_page() -> tuple[list[str], list[str], list[str]]:
    if not BOZZE_PAGE.exists():
        return [], [], []
    text = BOZZE_PAGE.read_text(encoding="utf-8")
    bozze_checked: list[str] = []
    convocazioni_checked: list[str] = []
    definitivi_checked: list[str] = []
    current_section: str | None = None
    for line in text.splitlines():
        ls = line.strip()
        if "## Bozze iniziali" in ls:
            current_section = "bozze"
        elif "## Convocazioni da inviare" in ls:
            current_section = "convocazioni"
        elif "## Definitivi" in ls:
            current_section = "definitivi"
        elif ls.startswith("- [x]") or ls.startswith("- [X]"):
            m = re.search(r"\[\[([^\]|]+)", ls)
            if m:
                stem = m.group(1).strip()
                if current_section == "bozze":
                    bozze_checked.append(stem)
                elif current_section == "convocazioni":
                    convocazioni_checked.append(stem)
                elif current_section == "definitivi":
                    definitivi_checked.append(stem)
    return bozze_checked, convocazioni_checked, definitivi_checked


def main() -> None:
    bozze_checked, convocazioni_checked, definitivi_checked = _parse_bozze_page()
    if not bozze_checked and not convocazioni_checked and not definitivi_checked:
        return

    print("=== archivia_inviati ===")
    for stem in bozze_checked:
        print(f"\n  Bozza: {stem}")
        _archivia_bozza(stem)
    for stem in convocazioni_checked:
        print(f"\n  Convocazione: {stem}")
        _archivia_convocazione(stem)
    for stem in definitivi_checked:
        print(f"\n  Definitivo: {stem}")
        _segna_definitivo_inviato(stem)
    print("\nArchiviazione completata.")


if __name__ == "__main__":
    main()
