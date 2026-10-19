"""vtt2md.py — converte i sottotitoli WebVTT di Teams in trascritto markdown.

Per le riunioni di cui esiste solo la registrazione video: Teams salva i
sottotitoli in un .vtt con tag <v PARLANTE>testo</v>. Lo script li converte
nello stesso formato dei trascritti .docx (PARLANTE M:SS + battute),
unendo le battute consecutive dello stesso parlante.

Uso:
    python scripts/vtt2md.py "<file.vtt>"      # scrive <file>.md accanto
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def parse_vtt(path: Path) -> list[tuple[str, str, str]]:
    """Ritorna [(speaker, mm:ss inizio, testo)] unendo battute consecutive."""
    text = path.read_text(encoding="utf-8", errors="replace")
    cues = []
    for m in re.finditer(
        r"(\d{2}):(\d{2}):(\d{2})\.\d+\s*-->.*?\n<v ([^>]+)>(.*?)</v>",
        text, re.DOTALL,
    ):
        h, mi, s, speaker, battuta = m.groups()
        start = f"{int(h) * 60 + int(mi)}:{s}"
        battuta = " ".join(battuta.split())
        if cues and cues[-1][0] == speaker.strip():
            cues[-1] = (cues[-1][0], cues[-1][1], cues[-1][2] + " " + battuta)
        else:
            cues.append((speaker.strip(), start, battuta))
    return cues


def vtt2md(path: Path) -> Path:
    cues = parse_vtt(path)
    out = path.with_suffix(".md")
    durata = cues[-1][1] if cues else "?"
    lines = [f"**{path.stem}** (da sottotitoli VTT)", "", f"Durata circa {durata}", ""]
    for speaker, start, battuta in cues:
        lines.append(f"**{speaker}** {start}\\")
        lines.append(battuta)
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    src = Path(sys.argv[1])
    if not src.is_file():
        sys.exit(f"File non trovato: {src}")
    dst = vtt2md(src)
    print(f"OK {src.name} -> {dst}")
