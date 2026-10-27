"""pubblica_pack_demo.py — specchia il pack demo (crea_pack_demo.py) nei due posti in cui deve stare:

  python scripts/crea_pack_demo.py            # 1. rigenera ..\\LeviathADM-demo\\ e lo zip
  python scripts/pubblica_pack_demo.py        # 2. copia il pack (Python embedded compreso) in:
                                              #    - .pack\\ nella radice del vault (repo privato: arriva sullo slave col sync;
                                              #      cartella con il punto, ignorata dagli indici delle app e da Obsidian)
                                              #    - ..\\LeviathADM\\ (clone del repo pubblico), se esiste
  poi: sync del vault; per il pubblico, nel clone: git add -A && git commit && git push, git tag vX.Y.Z, gh release create con lo zip.

Nel repo pubblico vanno solo i contenuti del pack (le due app, Python embedded, i template, il vault di prova fittizio):
mai file del vault reale. Rigenera il pack prima di pubblicare: non si pubblica mai una copia non rigenerata.
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACK = REPO.parent / "LeviathADM-demo"
NEL_VAULT = REPO / ".pack"
PUBBLICO = REPO.parent / "LeviathADM"
ESCLUSI = {".git", "__pycache__", "Bozze da inviare"}
CONSERVA = {".git", ".gitignore", ".gitattributes"}


def specchia(sorgente: Path, dest: Path) -> int:
    """Copia tutto il pack in `dest` (file in più in `dest` rimossi, tranne i file di git). Ritorna i file copiati."""
    if not (sorgente / "README-DEMO.md").exists():
        raise FileNotFoundError(f"pack assente: {sorgente} (esegui crea_pack_demo.py)")
    dest.mkdir(parents=True, exist_ok=True)
    for p in dest.iterdir():
        if p.name in CONSERVA:
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    n = 0
    for src in sorgente.rglob("*"):
        rel = src.relative_to(sorgente)
        if ESCLUSI & set(rel.parts) or src.is_dir():
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
        n += 1
    shutil.copy2(sorgente / "README-DEMO.md", dest / "README.md")
    return n


def main() -> int:
    n = specchia(PACK, NEL_VAULT)
    print(f"{n} file in {NEL_VAULT} (repo privato: ora sync)")
    if (PUBBLICO / ".git").is_dir():
        n = specchia(PACK, PUBBLICO)
        print(f"{n} file in {PUBBLICO}: commit, push, tag e release con lo zip (vedi docstring)")
    else:
        print(f"clone del repo pubblico assente ({PUBBLICO}): saltato")
    return 0


if __name__ == "__main__":
    sys.exit(main())
