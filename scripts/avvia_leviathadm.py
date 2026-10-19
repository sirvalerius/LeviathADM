"""Avvio di LeviathADM in un ambiente virtuale, con check delle dipendenze.

  python scripts/avvia_leviathadm.py [--check] [--porta N]

1. crea .venv/ nella radice del vault se manca e si rilancia dentro;
2. installa/aggiorna i requisiti quando requirements.txt cambia (impronta in .venv/requirements.sha256);
3. verifica i pacchetti Python, Outlook/Word/pandoc, il ruolo del PC e la porta;
4. avvia il server (mai reload=True). --check: solo le verifiche, exit 1 se manca un requisito.
Wrapper: leviathadm.cmd nella radice del vault.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib
import os
import socket
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
VENV = VAULT / ".venv"
PY_VENV = VENV / "Scripts" / "python.exe"
REQ = VAULT / "requirements.txt"
STAMP = VENV / "requirements.sha256"
PACCHETTI = {"nicegui": "nicegui", "python-docx": "docx", "openpyxl": "openpyxl", "pypandoc": "pypandoc",
             "docx2pdf": "docx2pdf", "pywin32": "win32com"}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _in_venv() -> bool:
    return Path(sys.prefix).resolve() == VENV.resolve()


def _assicura_venv() -> None:
    """Crea .venv se manca e rilancia questo script con il Python del venv."""
    if _in_venv():
        return
    if sys.version_info < (3, 12):
        sys.exit(f"Serve Python >= 3.12 (trovato {sys.version.split()[0]})")
    if not PY_VENV.exists():
        print(f"Creo l'ambiente virtuale in {VENV} …")
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    # non os.execv: su Windows non quota gli argomenti e un percorso con spazi si spezza
    sys.exit(subprocess.run([str(PY_VENV), __file__, *sys.argv[1:]]).returncode)


def _installa_requisiti() -> None:
    impronta = hashlib.sha256(REQ.read_bytes()).hexdigest()
    if STAMP.exists() and STAMP.read_text().strip() == impronta:
        return
    print("Installo i requisiti (requirements.txt cambiato o primo avvio) …")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", str(REQ)], check=True)
    STAMP.write_text(impronta)
    # i file .pth dei pacchetti appena installati (pywin32) si leggono solo all'avvio dell'interprete: rilancio
    sys.exit(subprocess.run([sys.executable, __file__, *sys.argv[1:]]).returncode)


def _check_pacchetti() -> list[str]:
    mancanti = []
    for nome, modulo in PACCHETTI.items():
        try:
            importlib.import_module(modulo)
            print(f"  ✓ {nome}")
        except ImportError:
            print(f"  ✗ {nome} (modulo {modulo})")
            mancanti.append(nome)
    return mancanti


def _porta_libera(porta: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", porta)) != 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", help="solo verifiche, non avvia il server")
    p.add_argument("--porta", type=int, default=8080)
    p.add_argument("--attendi-porta", action="store_true", help="aspetta (max 30 s) che la porta si liberi: usato dal riavvio dall'app")
    a = p.parse_args()
    _assicura_venv()
    os.chdir(VAULT)
    _installa_requisiti()
    sys.path.insert(0, str(VAULT))

    print("Pacchetti Python:")
    mancanti = _check_pacchetti()
    from leviathadm.vault.esecutore import dipendenze_disponibili
    import machine_config
    deps = dipendenze_disponibili()
    print("Programmi esterni (abilitano le azioni corrispondenti):")
    for nome, chiave in (("Outlook", "outlook"), ("Word", "word"), ("pandoc", "pandoc")):
        print(f"  {'✓' if chiave in deps else '✗'} {nome}")
    print(f"Ruolo del PC: {machine_config.get_role()}")
    if a.attendi_porta:
        import time
        for _ in range(60):
            if _porta_libera(a.porta):
                break
            time.sleep(0.5)
    libera = _porta_libera(a.porta)
    print(f"Porta {a.porta}: {'libera' if libera else 'OCCUPATA (altra istanza in esecuzione?)'}")
    if mancanti:
        print(f"\nMancano: {', '.join(mancanti)} — prova: {PY_VENV} -m pip install -r requirements.txt")
        return 1
    if a.check:
        return 0
    if not libera:
        return 1
    print(f"\nAvvio LeviathADM su http://127.0.0.1:{a.porta} (Ctrl+C per fermare)\n")
    from leviathadm.ui import app
    app.RUN_KWARGS["port"] = a.porta
    app.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
