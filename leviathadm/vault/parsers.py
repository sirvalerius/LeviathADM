"""Parser puri del markdown del vault (nessun I/O). Convenzioni: SCHEMA.md."""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime

_FM_RE = re.compile(r"^---[ \t]*\n.*?\n---[ \t]*\n?", re.DOTALL)
_H2_RE = re.compile(r"^## +(.+?) *\n", re.MULTILINE)  # consuma il newline: il corpo parte dalla riga dopo
_H1_RE = re.compile(r"^# +(.+?) *$", re.MULTILINE)
_CHECK_RE = re.compile(r"^- \[( |x|X)\] (.+?)\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^[-*]\s+(.+?)\s*$", re.MULTILINE)
_WIKI_RE = re.compile(r"(!?)\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
_TAG_RE = re.compile(r"(?<![\w/#])#([A-Za-z][\w\-]*)")


@dataclass(frozen=True)
class Wikilink:
    target: str
    alias: str | None
    embed: bool


def split_body(text: str) -> str:
    return _FM_RE.sub("", text, count=1) if text.startswith("---") else text


_H2_RIGA_RE = re.compile(r"^## [^\n]*(?:\n|$)", re.MULTILINE)
_CODA_RE = re.compile(r"(\n+---[ \t]*)?(\n*)$")


@dataclass
class Blocco:
    riga: str      # riga heading verbatim, newline incluso se presente
    heading: str   # titolo normalizzato (strip)
    body: str      # tutto fino alla riga heading successiva (o EOF), verbatim


def spezza_sezioni(corpo: str) -> tuple[str, list[Blocco]]:
    """Preambolo + sezioni H2 in ordine, senza perdita: ricomponi(*spezza_sezioni(c)) == c."""
    ms = list(_H2_RIGA_RE.finditer(corpo))
    if not ms:
        return corpo, []
    out: list[Blocco] = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(corpo)
        out.append(Blocco(riga=m.group(0), heading=m.group(0)[3:].strip(), body=corpo[m.end():end]))
    return corpo[:ms[0].start()], out


def ricomponi(pre: str, blocchi: list[Blocco]) -> str:
    return pre + "".join(b.riga + b.body for b in blocchi)


def scomponi_body(body: str) -> tuple[str, str, str]:
    """(testa, inner, coda): newline iniziali · contenuto senza newline ai bordi · tutto ciò che
    segue (newline finali ed eventuale separatore `---`). testa+inner+coda == body."""
    stripped = body.lstrip("\n")
    testa = body[: len(body) - len(stripped)]
    if stripped.startswith("---") and _CODA_RE.fullmatch("\n" + stripped):
        # sezione vuota: il separatore si porta dietro (fino a) due newline, come nella forma standard
        k = min(2, len(testa))
        return testa[: len(testa) - k], "", testa[len(testa) - k:] + stripped
    m = _CODA_RE.search(stripped)
    coda = stripped[m.start():] if m else ""
    inner = stripped[: len(stripped) - len(coda)]
    return testa, inner, coda


def split_sections(body: str) -> dict[str, str]:
    parts = _H2_RE.split(body)
    sections: dict[str, str] = {}
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i].strip()] = parts[i + 1]
    return sections


def parse_table(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    header_skipped = False
    for line in section.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            if rows:
                break
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            continue  # separatore
        if not header_skipped:
            header_skipped = True
            continue
        rows.append(cells)
    return rows


def parse_checkboxes(section: str) -> list[tuple[bool, str]]:
    return [(mark != " ", testo) for mark, testo in _CHECK_RE.findall(section)]


def parse_bullets(section: str) -> list[str]:
    return list(_BULLET_RE.findall(section))


def parse_wikilinks(text: str) -> list[Wikilink]:
    return [Wikilink(target=t.strip(), alias=(a.strip() if a else None), embed=(bang == "!"))
            for bang, t, a in _WIKI_RE.findall(text)]


def parse_tags(text: str) -> list[str]:
    tags: list[str] = []
    for line in text.splitlines():
        if re.match(r"^\s*#{1,6}\s", line):
            continue  # titolo markdown
        for t in _TAG_RE.findall(line):
            if t not in tags:
                tags.append(t)
    return tags


def strip_markdown_inline(text: str) -> str:
    text = _WIKI_RE.sub(lambda m: (m.group(3) or m.group(2)).strip(), text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    return text.replace("`", "")


def parse_data(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def ha_vincoli_normativi(valore: str) -> bool:
    """`Sì`, `Sì (GDPR, NIS2)`, `si`, `true`, `yes` → True; `No`/`NO`/vuoto → False."""
    v = normalizza(valore).strip()
    return v.startswith(("si", "sì", "true", "yes"))


def titolo_h1(text: str) -> str | None:
    m = _H1_RE.search(text)
    return m.group(1).strip() if m else None


def normalizza(text: str) -> str:
    """Minuscolo senza accenti, per ricerca e confronto titoli."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()
