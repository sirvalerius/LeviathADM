"""
prepara_firma.py — popola "<rilascio>/da mandare in firma/<Lettera>/" con
tutti i PDF da caricare su Arcipelago per protocollare una lettera di fine
collaudo (vedi Manuale protocollo/Guida alla protocollazione...).

Per ogni lettera pronta (quelle elencate in "## Da mandare in firma" di
Da firmare.md) crea una cartella dedicata con dentro, già in PDF:

  Trasmissione copia verbale di collaudo:
    - documento principale (lettera)
    - resoconto di collaudo (root o inviati/)
    - documento di analisi protocollato da SOGEI (ultima riga "Analisi..."
      della tabella "## Allegati protocolli") + i suoi allegati _AllN

  Richiesta estensione in esercizio:
    - solo il documento principale, nessun allegato (vedi guida)

Idempotente: se la cartella esiste già e non è vuota, non rifà nulla (evita
di riconvertire gli stessi file via Word COM a ogni sync).

Uso come modulo:
    from prepara_firma import prepara_cartella
    prepara_cartella(codice, label)   # label = una delle due stringhe sopra
"""
from __future__ import annotations
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import parse_frontmatter

VAULT = Path(__file__).parent.parent
LAVORI = VAULT / "PO 2026"

ALLEGATI_ANALISI_RE = re.compile(r"^\|\s*Analisi[^|]*\|\s*`([^`]+)`")


def _convert_docx(src: Path, dst_pdf: Path) -> bool:
    try:
        from docx2pdf import convert
        convert(str(src), str(dst_pdf))
        return dst_pdf.exists()
    except Exception as e:
        print(f"    WARN conversione PDF fallita ({src.name}): {e}")
        return False


def _trova_documento_analisi(release_dir: Path, codice: str) -> Path | None:
    scheda = release_dir / f"{codice}.md"
    if not scheda.exists():
        return None
    text = scheda.read_text(encoding="utf-8", errors="replace")
    ultimo = None
    for line in text.splitlines():
        m = ALLEGATI_ANALISI_RE.match(line.strip())
        if m:
            ultimo = m.group(1).strip()
    if not ultimo:
        return None
    path = release_dir / ultimo
    return path if path.exists() else None


def _trova_resoconto_collaudo(release_dir: Path, codice: str) -> Path | None:
    candidati = list(release_dir.glob(f"{codice} - * Resoconto Collaudo*.docx"))
    candidati += list((release_dir / "inviati").glob(f"{codice} - * Resoconto Collaudo*.docx"))
    if not candidati:
        return None
    return max(candidati, key=lambda p: p.stat().st_mtime)


def prepara_cartella(codice: str, label: str) -> bool:
    release_dir = LAVORI / codice
    dest = release_dir / "da mandare in firma" / label
    if dest.is_dir() and any(dest.iterdir()):
        return True  # già pronta

    pattern = f"*{label}.docx"
    principali = [p for p in release_dir.glob(pattern) if "inviati" not in p.parts]
    if not principali:
        print(f"    WARN: documento principale non trovato per {codice} · {label}")
        return False
    principale = max(principali, key=lambda p: p.stat().st_mtime)

    dest.mkdir(parents=True, exist_ok=True)
    ok = _convert_docx(principale, dest / (principale.stem + ".pdf"))

    if label == "Trasmissione copia verbale di collaudo":
        resoconto = _trova_resoconto_collaudo(release_dir, codice)
        if resoconto:
            pdf_esistente = resoconto.with_suffix(".pdf")
            if pdf_esistente.exists():
                shutil.copy2(pdf_esistente, dest / pdf_esistente.name)
            else:
                ok = _convert_docx(resoconto, dest / (resoconto.stem + ".pdf")) and ok
        else:
            print(f"    WARN: resoconto di collaudo non trovato per {codice}")

        analisi = _trova_documento_analisi(release_dir, codice)
        if analisi:
            shutil.copy2(analisi, dest / analisi.name)
            for allegato in sorted(release_dir.glob(f"{analisi.stem}_All*.pdf")):
                shutil.copy2(allegato, dest / allegato.name)
        else:
            print(f"    WARN: documento di analisi protocollato non trovato per {codice}")

    print(f"    Pronta: {dest.relative_to(VAULT)} ({len(list(dest.iterdir()))} file)")
    return ok
