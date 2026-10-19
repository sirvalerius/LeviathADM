"""Indice in memoria del vault: piani, rilasci, note, backlink, tag, ricerca."""
from __future__ import annotations
import re
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path

from . import loader, paths
from .models import Nota, Piano, Progetto, Rilascio, Risultato, Sottoprogetto
from .parsers import normalizza

_ANNO_RE = re.compile(r"^PO (\d{4})$")


class VaultIndex:
    def __init__(self, root: Path):
        self.root = root
        self.piani: dict[int, Piano] = {}
        self.note: dict[str, Nota] = {}
        self.versione = 0
        self._per_path: dict[Path, str] = {}
        self._norm: dict[str, tuple[str, str, str, str]] = {}  # id → (titolo, id, frontmatter, corpo) normalizzati
        self._per_titolo: dict[str, str] = {}
        self._backlinks: dict[str, set[str]] = {}
        self._tags: dict[str, set[str]] = {}
        self._listeners: list[Callable[[int], None]] = []

    # ---- carico -----------------------------------------------------------
    def load_all(self) -> None:
        self.piani.clear()
        self.note.clear()
        self._per_path.clear()
        self._norm.clear()
        for anno in paths.scopri_piani(self.root):
            self.piani[anno] = Piano(anno=anno, root=paths.cartella_piano(self.root, anno))
        for p in paths.itera_note(self.root):
            self._carica(p)
        self._ricalcola_derivati()
        self.versione += 1

    def _anno_di(self, p: Path) -> int | None:
        parts = p.relative_to(self.root).parts
        m = _ANNO_RE.match(parts[0]) if parts else None
        return int(m.group(1)) if m else None

    def _carica(self, p: Path) -> None:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            mtime = p.stat().st_mtime_ns
        except OSError:
            return
        nota = loader.parse_nota(p, text, self.root, mtime)
        self.note[nota.id] = nota
        self._per_path[p] = nota.id
        self._norm[nota.id] = (normalizza(nota.titolo), normalizza(nota.id),
                               normalizza(" ".join(nota.frontmatter.values())), normalizza(nota.corpo))
        anno = self._anno_di(p)
        if anno is None:
            return
        piano = self.piani.setdefault(anno, Piano(anno=anno, root=paths.cartella_piano(self.root, anno)))
        if nota.tipo == "rilascio":
            r = loader.parse_rilascio(p, text, self.root, mtime)
            piano.rilasci[r.codice] = r
        elif nota.tipo == "progetto":
            cod = nota.frontmatter.get("codice", p.stem)
            piano.progetti[cod] = Progetto(codice=cod, titolo=nota.titolo,
                                           area=nota.frontmatter.get("area", ""), path=p, id=nota.id)
        elif nota.tipo == "sottoprogetto":
            cod = nota.frontmatter.get("codice", p.stem)
            piano.sottoprogetti[cod] = Sottoprogetto(codice=cod, titolo=nota.titolo,
                                                     codice_progetto=cod.split("-")[0], path=p, id=nota.id)

    def _rimuovi(self, p: Path) -> None:
        nid = self._per_path.pop(p, None)
        if nid is None:
            return
        nota = self.note.pop(nid, None)
        self._norm.pop(nid, None)
        anno = self._anno_di(p)
        if nota and anno in self.piani:
            piano = self.piani[anno]
            if nota.tipo == "rilascio":
                piano.rilasci = {k: v for k, v in piano.rilasci.items() if v.path != p}
            piano.progetti = {k: v for k, v in piano.progetti.items() if v.path != p}
            piano.sottoprogetti = {k: v for k, v in piano.sottoprogetti.items() if v.path != p}

    def _escluso(self, p: Path) -> bool:
        try:
            parts = p.relative_to(self.root).parts[:-1]
        except ValueError:
            return True
        return paths.is_excluded_parts(parts)

    def reload(self, files: Iterable[Path]) -> None:
        da_ricaricare: set[Path] = set()
        for p in files:
            p = Path(p)
            da_ricaricare.add(p)
            scheda = self._scheda_della_cartella(p)
            if scheda is not None:
                da_ricaricare.add(scheda)
        for p in da_ricaricare:
            self._rimuovi(p)
            if p.exists() and p.suffix == ".md" and not self._escluso(p):
                self._carica(p)
        self._ricalcola_derivati()
        self.versione += 1
        for cb in list(self._listeners):
            cb(self.versione)

    def _scheda_della_cartella(self, p: Path) -> Path | None:
        for cart in (p.parent, p.parent.parent):
            cand = cart / f"{cart.name}.md"
            if cand != p and paths.is_scheda_rilascio(cand) and cand.exists():
                return cand
        return None

    def on_change(self, cb: Callable[[int], None]) -> None:
        self._listeners.append(cb)

    # ---- indici derivati --------------------------------------------------
    def _ricalcola_derivati(self) -> None:
        self._per_titolo = {}
        for nid, n in self.note.items():
            self._per_titolo.setdefault(normalizza(n.titolo), nid)
            self._per_titolo.setdefault(normalizza(n.path.stem), nid)
        self._backlinks = {}
        self._tags = {}
        for nid, n in self.note.items():
            for w in n.wikilink:
                dest = self.risolvi(w.target)
                if dest is not None:
                    self._backlinks.setdefault(dest.id, set()).add(nid)
            for t in n.tag:
                self._tags.setdefault(t, set()).add(nid)

    # ---- letture ------------------------------------------------------------
    def anni(self) -> list[int]:
        return sorted(self.piani, reverse=True)

    def piano(self, anno: int) -> Piano | None:
        return self.piani.get(anno)

    def anno_default(self) -> int:
        oggi = date.today().year
        return oggi if oggi in self.piani else (self.anni()[0] if self.piani else oggi)

    def rilascio(self, codice: str) -> Rilascio | None:
        for anno in self.anni():
            r = self.piani[anno].rilasci.get(codice)
            if r is not None:
                return r
        return None

    def nota(self, nid: str) -> Nota | None:
        return self.note.get(nid)

    def nota_per_path(self, p: Path) -> Nota | None:
        return self.note.get(self._per_path.get(Path(p), ""))

    def risolvi(self, target: str) -> Nota | None:
        target = target.split("#", 1)[0].strip()
        if target in self.note:
            return self.note[target]
        nid = self._per_titolo.get(normalizza(target))
        return self.note.get(nid) if nid else None

    def backlink_di(self, nid: str) -> list[Nota]:
        return sorted((self.note[i] for i in self._backlinks.get(nid, ()) if i in self.note),
                      key=lambda n: n.titolo)

    def note_con_tag(self, tag: str) -> list[Nota]:
        return sorted((self.note[i] for i in self._tags.get(tag, ()) if i in self.note),
                      key=lambda n: n.titolo)

    # ---- ricerca ------------------------------------------------------------
    def search(self, query: str, limit: int = 20) -> list[Risultato]:
        parole = [w for w in normalizza(query).split() if w]
        if not parole:
            return []
        out: list[Risultato] = []
        for n in self.note.values():
            titolo, nid, fm, corpo = self._norm[n.id]
            score = 0.0
            for w in parole:
                if titolo.startswith(w):
                    score += 100
                elif w in titolo:
                    score += 60
                elif w in nid:
                    score += 50
                elif w in fm:
                    score += 30
                elif w in corpo:
                    score += 10
                else:
                    score = 0
                    break
            if score and n.tipo == "rilascio":
                score += 20  # a parità, prima le schede dei rilasci (è un gestionale)
            if score:
                pos = corpo.find(parole[0])
                snippet = n.corpo[max(0, pos - 40): pos + 80].replace("\n", " ").strip() if pos >= 0 else ""
                out.append(Risultato(tipo=n.tipo, titolo=n.titolo, id=n.id, path=n.path,
                                     snippet=snippet, score=score))
        out.sort(key=lambda r: (-r.score, r.titolo))
        return out[:limit]
