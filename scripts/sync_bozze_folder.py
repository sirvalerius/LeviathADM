"""
sync_bozze_folder.py — sincronizza la cartella "Bozze da inviare\" con le bozze correnti.

Gestisce due categorie, in due sottocartelle distinte:

1. Bozze iniziali/  (non ancora inviate):
   Hardlink NTFS per ogni .docx e .msg dei resoconti
   presenti nella root del rilascio (non ancora in inviati/).

2. Definitivi/  (approvati, in attesa di invio):
   Hardlink per *_definitivo.msg e .pdf dei resoconti
   in inviati/ che hanno data_approvazione ma non sono ancora
   stati confermati come inviati (definitivo_inviato != true).

Rimuove i link non più pertinenti, compresi eventuali file rimasti
nella root della cartella dal vecchio layout piatto.

Uso:
    python scripts/sync_bozze_folder.py

La cartella "Bozze da inviare\" è nel .gitignore — non viene versionata.
Riesegui lo script (o il daily_check.py) dopo ogni modifica.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

VAULT = Path(__file__).parent.parent
LAVORI = VAULT / "PO 2026"
DEST = VAULT / "Bozze da inviare"
DIR_BOZZE = DEST / "Bozze iniziali"
DIR_DEFINITIVI = DEST / "Definitivi"

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import collaudo_resoconto_pronto, parse_frontmatter  # noqa: E402


def collect_bozze_files() -> list[Path]:
    """Bozze iniziali: .docx e .msg nella root del rilascio (non inviati/).
    Un resoconto di collaudo precompilato in anticipo (per essere mostrato e
    approvato in sede di riunione) resta escluso finché il collaudo non si
    è davvero svolto — vedi collaudo_resoconto_pronto."""
    files = []
    for md in LAVORI.glob("ADM*/*.md"):
        if " - 20" not in md.name:
            continue
        if "inviati" in md.parts:
            continue
        if not collaudo_resoconto_pronto(md):
            continue
        for ext in (".docx", ".msg"):
            f = md.with_suffix(ext)
            if f.exists():
                files.append(f)
    return sorted(files)


def collect_convocazioni_files() -> list[Path]:
    """Convocazioni (riunioni da fissare): .eml e .ics nella root del rilascio.
    Non hanno un .md resoconto abbinato, quindi non vengono raccolte da
    collect_bozze_files: le raccoglie per pattern sul nome file."""
    files = []
    for ext in ("eml", "ics"):
        files.extend(LAVORI.glob(f"ADM*/*Convocazione*.{ext}"))
    return sorted(files)


def collect_definitivi_files() -> list[Path]:
    """Definitivi: *_definitivo.msg e .pdf in inviati/ con approvazione non ancora confermata."""
    files = []
    for md in LAVORI.glob("ADM*/inviati/*.md"):
        if "_archivio" in md.parts:
            continue
        if " - 20" not in md.name:
            continue
        fm = parse_frontmatter(md)
        if not fm.get("data_approvazione", "").strip():
            continue
        if fm.get("definitivo_inviato", "").lower() == "true":
            continue
        msg = md.with_name(md.stem + " - definitivo.msg")
        pdf = md.with_suffix(".pdf")
        for f in (msg, pdf):
            if f.exists():
                files.append(f)
    return sorted(files)


def _try_unlink(path: Path, azione: str, pending: list[dict]) -> bool:
    """Rimuove il file; se è aperto in un'altra applicazione non blocca il sync:
    registra l'operazione come pendente, verrà ritentata alla prossima esecuzione."""
    try:
        path.unlink()
        return True
    except OSError as e:
        print(f"  BLOCCATO {path.name}: file in uso — riproverò al prossimo sync")
        pending.append({"azione": azione, "file": path.name, "errore": str(e)})
        return False


def _generate_missing_emls() -> None:
    """Genera i .msg mancanti per i resoconti che hanno già il .docx."""
    import genera_mail_resoconto as gmr
    for md in sorted(LAVORI.glob("ADM*/*.md")):
        if " - 20" not in md.name or "inviati" in md.parts:
            continue
        if not collaudo_resoconto_pronto(md):
            continue
        if md.with_suffix(".docx").exists() and not md.with_suffix(".msg").exists():
            print(f"  Genero .msg: {md.name}...")
            try:
                gmr.genera_eml(md)
            except Exception as e:
                print(f"  ERRORE genera_eml {md.name}: {e}")


def sync() -> list[dict]:
    """Sincronizza la cartella. Ritorna le operazioni rinviate per file bloccati
    (lista vuota = tutto applicato). Idempotente: una riesecuzione a file chiusi
    completa ciò che è rimasto in sospeso."""
    for d in (DEST, DIR_BOZZE, DIR_DEFINITIVI):
        d.mkdir(exist_ok=True)
    pending: list[dict] = []

    _generate_missing_emls()

    wanted: dict[Path, Path] = {}  # destinazione -> sorgente
    for src in collect_bozze_files():
        wanted[DIR_BOZZE / src.name] = src
    for src in collect_convocazioni_files():
        wanted[DIR_BOZZE / src.name] = src
    for src in collect_definitivi_files():
        wanted[DIR_DEFINITIVI / src.name] = src

    # Rimuove i file non più pertinenti, ovunque si trovino nella cartella
    # (root del vecchio layout piatto inclusa)
    removed = 0
    for existing in sorted(DEST.rglob("*")):
        if existing.is_file() and existing not in wanted:
            if _try_unlink(existing, "rimozione", pending):
                print(f"  RIMOSSO  {existing.relative_to(DEST)}")
                removed += 1

    # Aggiunge/aggiorna hardlink
    added = 0
    for dst, src in sorted(wanted.items()):
        if dst.exists():
            if os.stat(dst).st_ino == os.stat(src).st_ino:
                continue
            if not _try_unlink(dst, "aggiornamento", pending):
                continue
        try:
            os.link(src, dst)
            print(f"  AGGIUNTO {dst.relative_to(DEST)}")
            added += 1
        except OSError as e:
            print(f"  ERRORE   {dst.name}: {e}")
            pending.append({"azione": "aggiunta", "file": dst.name, "errore": str(e)})

    total = sum(1 for f in DEST.rglob("*") if f.is_file())
    print(f"\nCartella: {DEST}")
    print(f"File presenti: {total}  (+{added} aggiunti, -{removed} rimossi)")
    if pending:
        print(f"ATTENZIONE: {len(pending)} operazioni rinviate per file in uso — "
              "chiudi Word/Outlook e rilancia il sync.")
    return pending


if __name__ == "__main__":
    sync()
