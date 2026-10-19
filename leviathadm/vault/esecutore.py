"""Esecutore unico delle azioni: script del vault in sottoprocesso (thread + coda di righe), un'esecuzione
per processo, log in <vault>/azioni.jsonl. Nessun modulo COM importato qui."""
from __future__ import annotations
import json
import os
import queue
import shlex
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from leviathadm.ui import state
from leviathadm.vault.paths import _REPO_ROOT, VAULT_ROOT

LOG_NOME = "azioni.jsonl"


class EsecuzioneInCorso(Exception):
    pass


class Esecuzione:
    def __init__(self, azione_id: str, cmd: list[str], cwd: Path, rilascio: str | None = None):
        self.azione_id, self.cmd, self.cwd, self.rilascio = azione_id, cmd, cwd, rilascio
        self.righe: queue.Queue[str] = queue.Queue()
        self.coda: list[str] = []
        self.exit_code: int | None = None
        self.inizio = time.monotonic()
        self.durata_s: float | None = None
        self.proc: subprocess.Popen | None = None
        self.thread = threading.Thread(target=self._corri, daemon=True)

    def attivo(self) -> bool:
        return self.exit_code is None

    def interrompi(self) -> None:
        """Termina il sottoprocesso (es. script bloccato su una finestra di Word/Outlook): il blocco delle
        scritture si libera appena il thread registra l'uscita."""
        if self.proc is not None and self.proc.poll() is None:
            self._riga("— interrotto dall'utente —")
            self.proc.kill()

    def _riga(self, r: str) -> None:
        self.righe.put(r)
        self.coda = (self.coda + [r])[-20:]

    def _corri(self) -> None:
        # PYTHONUNBUFFERED: su pipe stdout è block-buffered e l'output arriverebbe tutto a fine processo
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
        codice = -1
        try:
            try:
                self.proc = subprocess.Popen(self.cmd, cwd=self.cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT, env=env)
                for raw in self.proc.stdout:
                    self._riga(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
                codice = self.proc.wait()
            except OSError as e:
                self._riga(f"Impossibile avviare: {e}")
            self.durata_s = round(time.monotonic() - self.inizio, 1)
            try:
                log_scrivi(self.cwd, {"ts": datetime.now().isoformat(timespec="seconds"), "azione": self.azione_id,
                                      "rilascio": self.rilascio, "comando": self.cmd, "exit": codice,
                                      "durata_s": self.durata_s, "coda": list(self.coda)})
            except OSError as e:
                self._riga(f"Log non scritto: {e}")
        finally:
            self.exit_code = codice      # SEMPRE, e per ultimo: è il segnale di fine e libera il blocco delle scritture


def in_corso() -> str | None:
    """id dell'azione in esecuzione, o None. Finché c'è, le scritture dell'app sono sospese
    (un git pull --rebase nel sync e uno spostamento di file nello stesso istante si rovinano a vicenda)."""
    e = state.ESECUZIONE
    return e.azione_id if e is not None and e.attivo() else None


def comando_effettivo(cmd: list[str]) -> list[str]:
    finto = os.environ.get("LEVIATHADM_CMD_FINTO")   # solo test: sostituisce qualunque comando
    if finto:
        return shlex.split(finto)
    if VAULT_ROOT != _REPO_ROOT:
        raise RuntimeError("app avviata con LEVIATHADM_ROOT: gli script reali sono disabilitati (usa LEVIATHADM_CMD_FINTO)")
    return cmd


def avvia(azione_id: str, cmd: list[str], *, cwd: Path | None = None, rilascio: str | None = None) -> Esecuzione:
    if state.ESECUZIONE is not None and state.ESECUZIONE.attivo():
        raise EsecuzioneInCorso(state.ESECUZIONE.azione_id)
    run = Esecuzione(azione_id, comando_effettivo(cmd), cwd or VAULT_ROOT, rilascio)
    state.ESECUZIONE = run
    run.thread.start()
    return run


def log_scrivi(root: Path, voce: dict) -> None:
    with open(root / LOG_NOME, "a", encoding="utf-8") as f:
        f.write(json.dumps(voce, ensure_ascii=False, default=str) + "\n")


def log_leggi(root: Path, n: int = 100) -> list[dict]:
    """Ultime n voci, più recenti prima; righe malformate (crash a metà scrittura) saltate."""
    f = root / LOG_NOME
    if not f.exists():
        return []
    voci = []
    for riga in f.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            voci.append(json.loads(riga))
        except json.JSONDecodeError:
            continue
    return voci[-n:][::-1]


def dipendenze_disponibili() -> set[str]:
    """Outlook/Word dalle classi COM registrate; pandoc dal PATH. Calcolato una volta all'avvio."""
    out: set[str] = set()
    try:
        import winreg
        for nome, chiave in (("outlook", "Outlook.Application"), ("word", "Word.Application")):
            try:
                winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, chiave))
                out.add(nome)
            except OSError:
                pass
    except ImportError:
        pass
    if shutil.which("pandoc"):
        out.add("pandoc")
    return out
