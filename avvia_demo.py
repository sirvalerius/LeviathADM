"""Avvio della demo con il Python embedded in python/ (nessun venv). Mai reload=True."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
p = argparse.ArgumentParser()
p.add_argument("--porta", type=int, default=8080)
p.add_argument("--attendi-porta", action="store_true")   # usato da "Riavvia backend" dell'app
a, _ = p.parse_known_args()
if a.attendi_porta:   # il vecchio server si spegne dopo il lancio: aspetto (max 30 s) che liberi la porta
    import socket
    import time
    for _ in range(60):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", a.porta)) != 0:
                break
        time.sleep(0.5)
from leviathadm.ui import app  # noqa: E402

app.RUN_KWARGS["port"] = a.porta
print(f"LeviathADM demo su http://127.0.0.1:{a.porta} (Ctrl+C per fermare)")
app.main()
