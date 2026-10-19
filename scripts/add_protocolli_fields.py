"""add_protocolli_fields.py — aggiunge a ogni scheda ADMxxx-xx-xX.md i campi
frontmatter dei numeri di protocollo e la sezione "## Allegati protocolli",
se non già presenti. Non tocca schede già dotate della sezione.

Uso:
    python scripts/add_protocolli_fields.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import update_frontmatter_keys

VAULT = Path(__file__).parent.parent
LAVORI = VAULT / "PO 2026"

PROTOCOLLO_KEYS = {
    "protocollo_analisi": "",
    "protocollo_approvazione_analisi": "",
    "protocollo_collaudo": "",
    "protocollo_estensione_esercizio": "",
    "protocollo_disponibilita_collaudo": "",
    "data_disponibilita_collaudo": "",
}

ALLEGATI_SECTION = """## Allegati protocolli

- Analisi:
- Approvazione analisi:
- Collaudo:
- Estensione esercizio:
"""


def find_schede() -> list[Path]:
    out = []
    for rel_dir in sorted(LAVORI.glob("ADM*")):
        if not rel_dir.is_dir():
            continue
        scheda = rel_dir / f"{rel_dir.name}.md"
        if scheda.exists():
            out.append(scheda)
    return out


def add_frontmatter(scheda: Path) -> bool:
    fm_text = scheda.read_text(encoding="utf-8")
    m = re.match(r"^---[ \t]*\n(.*?)\n---", fm_text, re.DOTALL)
    existing_keys = set()
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                existing_keys.add(line.partition(":")[0].strip())
    missing = {k: v for k, v in PROTOCOLLO_KEYS.items() if k not in existing_keys}
    if not missing:
        return False
    update_frontmatter_keys(scheda, missing)
    return True


def add_section(scheda: Path) -> bool:
    text = scheda.read_text(encoding="utf-8")
    if "## Allegati protocolli" in text:
        return False
    text = text.rstrip("\n") + "\n\n" + ALLEGATI_SECTION
    scheda.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    schede = find_schede()
    print(f"Trovate {len(schede)} schede.\n")
    for scheda in schede:
        fm_added = add_frontmatter(scheda)
        sec_added = add_section(scheda)
        if fm_added or sec_added:
            parts = []
            if fm_added:
                parts.append("frontmatter")
            if sec_added:
                parts.append("sezione")
            print(f"  AGGIORNATA {scheda.relative_to(VAULT)} ({', '.join(parts)})")
        else:
            print(f"  INVARIATA  {scheda.relative_to(VAULT)}")


if __name__ == "__main__":
    main()
