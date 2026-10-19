"""Apertura locale di mail e cartelle dalla versione Python (fase 5): "Apri in Outlook" sul .msg (associazione
di Windows), "Apri cartella" con Esplora file sul file selezionato. Solo lettura: nessuna scrittura nel vault,
nessun invio, nessun sottoprocesso tracciato."""
from __future__ import annotations
import os
import subprocess
from pathlib import Path


def file_mail(md_path: Path, definitivo: bool = False) -> Path | None:
    """Il .msg del resoconto (o " - definitivo.msg"), se esiste."""
    md_path = Path(md_path)
    p = md_path.with_name(md_path.stem + " - definitivo.msg") if definitivo else md_path.with_suffix(".msg")
    return p if p.exists() else None


def comando_cartella(path: Path) -> list[str]:
    return ["explorer", f"/select,{Path(path)}"]


def apri_in_outlook(path: Path) -> None:
    os.startfile(str(path))   # .msg → Outlook (bozza, nessun invio)


def apri_cartella(path: Path) -> None:
    subprocess.Popen(comando_cartella(path))
