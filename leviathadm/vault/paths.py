"""Percorsi del vault: root, piani "PO <anno>", esclusioni, identificazione schede, id nota."""
from __future__ import annotations
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

# LEVIATHADM_ROOT: solo per verifiche headless su un vault di prova (mai in uso normale)
_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
VAULT_ROOT: Path = Path(os.environ["LEVIATHADM_ROOT"]).resolve() if os.environ.get("LEVIATHADM_ROOT") else _REPO_ROOT
SCRIPTS_DIR: Path = _REPO_ROOT / "scripts"   # codice, non dati: sempre quello del pacchetto
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

EXCLUDED_DIRS: frozenset[str] = frozenset({
    ".git", ".claude", "Bozze da inviare", "node_modules", "__pycache__",
    "docs", "LeviathADM", "leviathadm",
})
_PIANO_RE = re.compile(r"^PO (\d{4})$")
_SEP = "~"


def scopri_piani(root: Path) -> list[int]:
    anni = [int(m.group(1)) for d in root.iterdir() if d.is_dir() and (m := _PIANO_RE.match(d.name))]
    return sorted(anni, reverse=True)


def cartella_piano(root: Path, anno: int) -> Path:
    return root / f"PO {anno}"


def is_scheda_rilascio(md: Path) -> bool:
    d = md.parent
    return md.suffix == ".md" and md.stem == d.name and d.name.startswith("ADM") and "(" not in d.name


def is_excluded_parts(parts: tuple[str, ...]) -> bool:
    """True se una delle cartelle del percorso (relativo alla root) è esclusa:
    nomi in EXCLUDED_DIRS o cartelle nascoste (`.obsidian`, `.superpowers`, `.trash`, …)."""
    return any(part in EXCLUDED_DIRS or part.startswith(".") for part in parts)


def itera_note(root: Path) -> Iterator[Path]:
    for p in root.rglob("*.md"):
        if is_excluded_parts(p.relative_to(root).parts[:-1]):
            continue
        yield p


def nota_id(root: Path, path: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if rel.endswith(".md"):
        rel = rel[:-3]
    return rel.replace("/", _SEP)


def path_da_nota_id(root: Path, nid: str) -> Path:
    return root / (nid.replace(_SEP, "/") + ".md")
