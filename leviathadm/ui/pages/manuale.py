"""Manuale dell'applicazione: leviathadm/MANUALE.md reso come le note (unica fonte anche per la versione Web)."""
from __future__ import annotations
from pathlib import Path

from nicegui import ui

from leviathadm.ui.shell import shell

MANUALE = Path(__file__).resolve().parents[2] / "MANUALE.md"


def testo() -> str:
    return MANUALE.read_text(encoding="utf-8")


def render_manuale() -> None:
    with shell('Manuale'):
        ui.markdown(testo(), extras=['tables', 'fenced-code-blocks']).classes('w-full lv-card p-4')
