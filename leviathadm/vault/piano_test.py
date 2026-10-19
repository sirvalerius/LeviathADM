"""Piano di Test del rilascio: documento di analisi e casi di test per la convocazione di collaudo."""
from __future__ import annotations
import re
from pathlib import Path

from leviathadm.vault import paths as _paths  # noqa: F401  (scripts/ nel path)
from mail_utils import parse_frontmatter
from leviathadm.vault.parsers import spezza_sezioni, split_body

_BULLET = re.compile(r"^- \*\*(.+?)\*\*\s*$")


def trova_piano(rilascio_dir: Path) -> Path | None:
    return next(iter(sorted(rilascio_dir.glob("*Piano di Test.md"))), None)


def parse_piano_test(text: str) -> tuple[str, list[str]]:
    """(documento_analisi dal frontmatter, elenco dei bullet `- **TCn · nome**` sotto ## Riepilogo)."""
    doc = parse_frontmatter(text).get("documento_analisi", "").strip()
    _, blocchi = spezza_sezioni(split_body(text))
    riepilogo = next((b for b in blocchi if b.heading.strip().lower() == "riepilogo"), None)
    verifiche: list[str] = []
    if riepilogo:
        for riga in riepilogo.body.splitlines():
            m = _BULLET.match(riga.strip()) if riga.startswith("- ") else None
            if m:
                verifiche.append(m.group(1).strip())
    return doc, verifiche
