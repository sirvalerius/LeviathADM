"""Azioni globali: sincronizzazione, rigenerazione, Anagrafica/schede, audit, casella Outlook."""
from __future__ import annotations
from nicegui import ui

from leviathadm.ui import state
from leviathadm.ui.esecuzione_ui import pulsante_azione, testo_stato_deps
from leviathadm.ui.shell import shell
from leviathadm.vault import azioni as A

SEZIONI = [("Sincronizzazione", ["sync", "daily_check"]),
           ("Rigenerazione pagine (master)", ["build_pagine"] + [f"build_{n}" for n in
                                              ("bozze", "scadenze", "stato_invii", "rilasci", "riunioni", "da_collaudare", "da_firmare")]),
           ("Anagrafica e schede (master)", ["schede_excel", "strutture", "refresh_anagrafica"]),
           ("Audit invii", ["audit_dump", "audit_inventario", "audit_match", "audit_deepcheck", "audit_apply"]),
           ("Casella Outlook", ["organizza_outlook"])]


def render_azioni() -> None:
    with shell('Azioni'):
        ui.label(testo_stato_deps(state.MASTER, state.DEPS)).classes('text-xs text-slate-500 font-mono')
        ui.label('Gli script girano in sottoprocesso; nessuna mail viene inviata (solo bozze .eml/.msg). '
                 'Le azioni che scrivono in massa chiedono conferma o mostrano prima un\'anteprima.').classes('text-xs text-slate-500')
        for titolo, ids in SEZIONI:
            with ui.card().classes('w-full lv-card shadow-none'):
                ui.label(titolo).classes('font-bold text-slate-700')
                for i in ids:
                    az = A.CATALOGO[i]
                    with ui.row().classes('w-full items-center gap-3 lv-riga'):
                        pulsante_azione(az).classes('w-64')
                        ui.label(az.descrizione).classes('text-sm text-slate-600')
