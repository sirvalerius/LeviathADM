"""machine_config.py — ruolo del PC corrente (master / slave).

La mappa hostname -> ruolo vive in scripts/machines.json (versionato in git,
quindi condiviso tra le macchine). Il master è l'unica macchina che esegue
l'automazione mutante (daily_check: archiviazione, chiusura approvazioni
tacite, rigenerazione pagine, sync cartella bozze); gli slave leggono e
modificano i contenuti ma lasciano l'automazione al master, evitando che due
PC generino/eliminino gli stessi file in concorrenza via git.

Uso:
    python scripts/machine_config.py              # mostra hostname e ruolo
    python scripts/machine_config.py set master   # assegna un ruolo a questo PC
    python scripts/machine_config.py set slave
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "machines.json"


def _load() -> dict:
    if CONFIG_PATH.is_file():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"default_role": "slave", "machines": {}}


def get_role() -> str:
    """Ruolo del PC corrente: 'master' o 'slave'."""
    cfg = _load()
    return cfg.get("machines", {}).get(socket.gethostname(), cfg.get("default_role", "slave"))


def is_master() -> bool:
    return get_role() == "master"


def set_role(role: str) -> None:
    if role not in ("master", "slave"):
        raise ValueError(f"Ruolo non valido: {role!r} (ammessi: master, slave)")
    cfg = _load()
    cfg.setdefault("machines", {})[socket.gethostname()] = role
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "set":
        set_role(sys.argv[2])
        print(f"{socket.gethostname()} -> {sys.argv[2]} (salvato in {CONFIG_PATH.name})")
    elif len(sys.argv) == 1:
        print(f"Hostname: {socket.gethostname()}")
        print(f"Ruolo   : {get_role()}")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
