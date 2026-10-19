"""Riavvio del backend dall'app: apre una nuova console con leviathadm.cmd (che aspetta la porta) e spegne questo processo."""
from __future__ import annotations
import subprocess

from nicegui import app, ui

from leviathadm.vault import esecutore
from leviathadm.vault.paths import _REPO_ROOT, VAULT_ROOT

CMD = _REPO_ROOT / "leviathadm.cmd"


def comando_riavvio(porta: int) -> list[str]:
    """Rifiuta su un vault di prova (LEVIATHADM_ROOT): rilancerebbe l'app sul vault reale."""
    if VAULT_ROOT != _REPO_ROOT:
        raise RuntimeError("app avviata con LEVIATHADM_ROOT: il riavvio è disabilitato")
    return [str(CMD), "--porta", str(porta), "--attendi-porta"]


def riavvia_backend(porta: int) -> None:
    if esecutore.in_corso():
        ui.notify("Un'azione è in corso: attendi che finisca prima di riavviare.", type='warning')
        return
    try:
        cmd = comando_riavvio(porta)
    except RuntimeError as e:
        ui.notify(str(e), type='negative', close_button=True)
        return
    # nuova console: l'utente ritrova l'output del server come con il doppio clic su leviathadm.cmd
    subprocess.Popen(cmd, cwd=_REPO_ROOT, creationflags=subprocess.CREATE_NEW_CONSOLE)
    ui.notify('Riavvio in corso: ricarica la pagina tra qualche secondo.', type='info')
    ui.timer(0.8, app.shutdown, once=True)


def pulsante_riavvio(porta: int) -> None:
    with ui.dialog() as d, ui.card():
        ui.label('Riavviare il backend? Il server si spegne e riparte in una nuova console (venv e check delle dipendenze inclusi). '
                 'Le pagine aperte vanno ricaricate.').classes('text-sm')
        with ui.row():
            ui.button('Riavvia', on_click=lambda: (d.close(), riavvia_backend(porta))).props('unelevated color=orange-9')
            ui.button('Annulla', on_click=d.close).props('flat')
    b = ui.button('Riavvia backend', icon='restart_alt', on_click=d.open).props('flat dense').classes('w-full justify-start')
    if VAULT_ROOT != _REPO_ROOT:
        b.disable()
        b.tooltip('disabilitato su un vault di prova')
