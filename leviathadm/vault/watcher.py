"""Osservatore del vault in-process (watchfiles). Mai il reloader di uvicorn."""
from __future__ import annotations
import asyncio
import logging
from pathlib import Path

from watchfiles import Change, awatch

from .index import VaultIndex
from .paths import is_excluded_parts

log = logging.getLogger("leviathadm.watcher")


def _filtro(root: Path):
    def accetta(change: Change, path: str) -> bool:
        p = Path(path)
        if p.suffix != ".md":
            return False
        try:
            parts = p.relative_to(root).parts[:-1]
        except ValueError:
            return False
        return not is_excluded_parts(parts)
    return accetta


async def avvia_watcher(index: VaultIndex, stop_event: asyncio.Event, *, debounce_ms: int = 300) -> None:
    root = index.root
    log.info("watcher avviato su %s", root)
    async for changes in awatch(root, watch_filter=_filtro(root), debounce=debounce_ms, step=50,
                                stop_event=stop_event, recursive=True):
        paths = {Path(p) for _, p in changes}
        try:
            index.reload(paths)
            log.info("ricaricati %d file (versione %d)", len(paths), index.versione)
        except Exception:  # noqa: BLE001 — il watcher non deve mai morire
            log.exception("errore nel reload di %s", paths)
    log.info("watcher fermato")
