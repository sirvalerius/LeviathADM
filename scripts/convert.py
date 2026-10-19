"""
convert.py — conversione bidirezionale docx ↔ md

Uso:
  python convert.py docx2md <file.docx>            # converte in .md nella stessa cartella
  python convert.py docx2md <file.docx> -o <out>   # specifica destinazione
  python convert.py md2docx <file.md>              # converte in .docx usando il template
  python convert.py md2docx <file.md> -o <out>     # specifica destinazione

  python convert.py docx2md <cartella>             # converte tutti i .docx in una cartella
  python convert.py md2docx <cartella>             # converte tutti i .md in una cartella

Opzioni:
  --no-template    (md2docx) non usare il template Word, output senza stili
"""

import glob
import re
import sys
import argparse
import tempfile
from pathlib import Path
import pypandoc

VAULT_ROOT    = Path(__file__).parent.parent
WORD_TEMPLATE = VAULT_ROOT / "Template" / "Template - 2026MMGG Resoconto Startup.docx"

# Cartelle dove non eseguire mai conversioni batch
SKIP_DIRS = {".obsidian", ".claude", "mcp-graph-email", "__pycache__"}


# ---------------------------------------------------------------------------
# Conversioni
# ---------------------------------------------------------------------------

def docx_to_md(src: Path, dst: Path | None = None) -> Path:
    dst = dst or src.with_suffix(".md")
    # Redirect extracted images outside the vault so Obsidian doesn't see them
    media_dir = Path(tempfile.gettempdir()) / "obsiclaude-media"
    # glob.escape: pypandoc tratta la stringa come pattern glob; senza escape,
    # nomi Teams con "[Titolo Riunione]" vengono letti come classe di
    # caratteri, non trovano match e mandano in errore la libreria.
    pypandoc.convert_file(
        glob.escape(str(src)),
        "markdown",
        outputfile=str(dst),
        extra_args=["--wrap=none", f"--extract-media={media_dir}"],
    )
    # Strip image references (Teams avatars, logos) — useless in text transcripts
    text = dst.read_text(encoding="utf-8")
    text = re.sub(r"!\[.*?\]\([^)]+\)\{[^}]*\}", "", text)
    text = re.sub(r"!\[.*?\]\([^)]+\)", "", text)
    dst.write_text(text, encoding="utf-8")
    return dst


def md_to_docx(src: Path, dst: Path | None = None, use_template: bool = True) -> Path:
    dst = dst or src.with_suffix(".docx")
    extra_args = []
    if use_template and WORD_TEMPLATE.exists():
        extra_args = [f"--reference-doc={WORD_TEMPLATE}"]
    elif use_template and not WORD_TEMPLATE.exists():
        print(f"  ATTENZIONE: template non trovato in {WORD_TEMPLATE} — output senza stili.")
    pypandoc.convert_file(
        glob.escape(str(src)),
        "docx",
        outputfile=str(dst),
        extra_args=extra_args,
    )
    return dst


# ---------------------------------------------------------------------------
# Batch su cartella
# ---------------------------------------------------------------------------

def batch_docx_to_md(folder: Path) -> None:
    files = [f for f in folder.rglob("*.docx") if not any(p in SKIP_DIRS for p in f.parts)]
    if not files:
        print(f"Nessun .docx trovato in {folder}")
        return
    print(f"Trovati {len(files)} file .docx\n")
    for f in files:
        out = docx_to_md(f)
        print(f"  OK {f.relative_to(VAULT_ROOT)}  ->  {out.name}")


def batch_md_to_docx(folder: Path, use_template: bool = True) -> None:
    files = [f for f in folder.rglob("*.md") if not any(p in SKIP_DIRS for p in f.parts)]
    if not files:
        print(f"Nessun .md trovato in {folder}")
        return
    print(f"Trovati {len(files)} file .md\n")
    for f in files:
        out = md_to_docx(f, use_template=use_template)
        print(f"  OK {f.relative_to(VAULT_ROOT)}  ->  {out.name}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Conversione docx ↔ md")
    parser.add_argument("direction", choices=["docx2md", "md2docx"])
    parser.add_argument("source", help="File o cartella sorgente")
    parser.add_argument("-o", "--output", help="File di destinazione (solo per file singolo)")
    parser.add_argument("--no-template", action="store_true", help="md2docx: non usare il template Word")
    args = parser.parse_args()

    src = Path(args.source)
    if not src.exists():
        print(f"ERRORE: {src} non trovato.")
        sys.exit(1)

    use_template = not args.no_template

    if src.is_dir():
        if args.direction == "docx2md":
            batch_docx_to_md(src)
        else:
            batch_md_to_docx(src, use_template=use_template)
    else:
        dst = Path(args.output) if args.output else None
        if args.direction == "docx2md":
            out = docx_to_md(src, dst)
            print(f"OK {src.name}  ->  {out}")
        else:
            out = md_to_docx(src, dst, use_template=use_template)
            print(f"OK {src.name}  ->  {out}")


if __name__ == "__main__":
    main()
