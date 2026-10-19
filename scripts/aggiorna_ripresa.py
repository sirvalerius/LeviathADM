"""
aggiorna_ripresa.py — aggiorna RIPRESA_SESSIONE.md nella root del vault.

Pensato per essere eseguito dal hook Stop di Claude Code (vedi .claude/settings.json).
Il file generato è gitignored: serve solo come punto di ripresa nella sessione successiva.

Contiene:
  - Timestamp ultimo aggiornamento
  - Stato git (file modificati non committati)
  - Ultimi commit
  - Bozze e definitivi in attesa (snapshot da "Bozze da inviare.md")

Esecuzione manuale:
  python scripts/aggiorna_ripresa.py
"""
from __future__ import annotations
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

VAULT = Path(__file__).parent.parent
OUT = VAULT / "RIPRESA_SESSIONE.md"


def _git(*args: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=str(VAULT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _read_session_info_from_stdin() -> dict:
    """Il hook Stop di Claude Code passa un JSON via stdin con session_id, ecc."""
    if sys.stdin.isatty():
        return {}
    try:
        data = sys.stdin.read()
        return json.loads(data) if data else {}
    except json.JSONDecodeError:
        return {}


def _bozze_snapshot() -> str:
    """Estrae le righe '- [ ]' da Bozze da inviare.md per ricordare cosa resta in coda."""
    bozze_md = VAULT / "PO 2026" / "Bozze da inviare.md"
    if not bozze_md.exists():
        return "_pagina Bozze non disponibile_"
    lines = bozze_md.read_text(encoding="utf-8", errors="replace").splitlines()
    items = [l for l in lines if l.strip().startswith("- [ ]")]
    if not items:
        return "_nessuna bozza in attesa_"
    return "\n".join(items[:20])


def build() -> None:
    now = datetime.now()
    session = _read_session_info_from_stdin()
    session_id = session.get("session_id", "")
    transcript = session.get("transcript_path", "")

    git_status = _git("status", "--short") or "_(working tree pulito)_"
    git_log = _git("log", "--oneline", "-5") or "_(nessun commit)_"

    parts = [
        "# Ripresa sessione",
        "",
        f"> Aggiornato: {now.strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    if session_id:
        parts += [
            "## Riprendi questa conversazione",
            "",
            f"```",
            f"claude --resume {session_id}",
            f"```",
            "",
        ]
        if transcript:
            parts += [f"Transcript: `{transcript}`", ""]

    parts += [
        "## Stato git (working tree)",
        "",
        "```",
        git_status,
        "```",
        "",
        "## Ultimi commit",
        "",
        "```",
        git_log,
        "```",
        "",
        "## Bozze e definitivi ancora da inviare",
        "",
        _bozze_snapshot(),
        "",
    ]

    OUT.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    build()
