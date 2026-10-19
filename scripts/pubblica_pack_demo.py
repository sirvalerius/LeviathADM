"""pubblica_pack_demo.py — specchia il pack demo (crea_pack_demo.py) nel clone del repo pubblico LeviathADM.

  python scripts/crea_pack_demo.py            # 1. rigenera ..\\LeviathADM-demo\\ e lo zip
  python scripts/pubblica_pack_demo.py        # 2. copia tutto il pack, Python embedded compreso, in ..\\LeviathADM\\ (clone di github.com/sirvalerius/LeviathADM)
  poi, nel clone: git add -A && git commit && git push, git tag vAAAA.MM.GG && git push origin <tag>,
  gh release create <tag> "../LeviathADM-demo.zip" --title ... --notes ...   # lo zip = stesso contenuto, pronto da scompattare

Nel repo pubblico vanno solo i contenuti del pack (le due app, Python embedded, i template, il vault di prova fittizio):
mai file del vault reale.
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACK = REPO.parent / "LeviathADM-demo"
PUBBLICO = REPO.parent / "LeviathADM"
ESCLUSI = {".git", "__pycache__", "Bozze da inviare"}


def main() -> int:
    if not (PACK / "README-DEMO.md").exists():
        sys.exit(f"pack assente: {PACK} (esegui crea_pack_demo.py)")
    if not (PUBBLICO / ".git").is_dir():
        sys.exit(f"clone del repo pubblico assente: {PUBBLICO}")
    for p in PUBBLICO.iterdir():                 # resta solo ciò che governa git
        if p.name in (".git", ".gitignore", ".gitattributes"):
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    n = 0
    for src in PACK.rglob("*"):
        rel = src.relative_to(PACK)
        if ESCLUSI & set(rel.parts) or src.is_dir():
            continue
        dst = PUBBLICO / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    shutil.copy2(PACK / "README-DEMO.md", PUBBLICO / "README.md")
    print(f"{n} file copiati in {PUBBLICO}: ora commit, push, tag e release con lo zip (vedi docstring)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
