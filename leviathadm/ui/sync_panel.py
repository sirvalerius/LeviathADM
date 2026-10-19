"""Pulsante Sync nell'header: l'azione "sync" del catalogo tramite il pannello generico; in coda al
pannello il riepilogo di .sync_pending.json (operazioni rinviate dal sync)."""
from __future__ import annotations
import json
from pathlib import Path

from nicegui import ui

from leviathadm.ui.esecuzione_ui import pulsante_azione
from leviathadm.vault import azioni as A
from leviathadm.vault.paths import VAULT_ROOT


def riepilogo_pending(root: Path) -> list[str]:
    f = root / ".sync_pending.json"
    if not f.exists():
        return []
    p = json.loads(f.read_text(encoding="utf-8"))
    out = [f"Passo fallito: {s['step']} — {s['errore']}" for s in p.get("step_falliti", [])]
    out += [f"File bloccato: {b['file']} ({b['azione']}) — {b['errore']}" for b in p.get("file_bloccati", [])]
    if p.get("push_fallito"):
        out.append(f"Push non riuscito: {p['push_fallito']}")
    if p.get("pull_fallito"):
        out.append(f"Pull non riuscito: {p['pull_fallito']}")
    return out


def _dopo(exit_code: int, log: ui.log) -> None:
    for r in riepilogo_pending(VAULT_ROOT):
        log.push('⚠ ' + r)
    if exit_code != 0:
        log.push('Per problemi di proxy: python scripts/sync.py --change-proxy-password da console.')


def pulsante_sync() -> None:
    pulsante_azione(A.CATALOGO['sync'], props='flat color=white', dopo=_dopo)
