"""
build_bozze.py — rigenera PO 2026/Bozze da inviare.md

Sezioni generate:
  ## Bozze iniziali        — .md con .docx/.msg nella root del rilascio (non inviati/)
  ## Convocazioni da inviare — .eml *Convocazione* (startup/collaudo) nella root del rilascio
  ## Definitivi            — in inviati/ con data_approvazione e senza definitivo_inviato

Uso:
    python scripts/build_bozze.py
Chiamare DOPO archivia_inviati.py (che consuma i [x] prima della rigenerazione).
"""
from __future__ import annotations
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import collaudo_resoconto_pronto, format_tipo_riunione, parse_frontmatter

VAULT = Path(__file__).parent.parent
LAVORI = VAULT / "PO 2026"
OUT = LAVORI / "Bozze da inviare.md"


def _fmt_date(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except Exception:
        return iso


def docx_superato(md: Path) -> bool:
    """True se il .md è stato modificato dopo il .docx (es. dalla versione web, che non può rigenerarlo):
    il Word allegato alla mail sarebbe vecchio. Brezza .docx non c'è nulla da rigenerare."""
    docx = md.with_suffix(".docx")
    return docx.exists() and md.stat().st_mtime > docx.stat().st_mtime + 1


def collect_bozze() -> list[dict]:
    items = []
    for md in sorted(LAVORI.glob("ADM*/*.md")):
        if " - 20" not in md.name:
            continue
        if "inviati" in md.parts:
            continue
        fm = parse_frontmatter(md)
        if not fm.get("tipo_riunione", "").strip() or not fm.get("data_riunione", "").strip():
            continue  # non è un resoconto (es. Verbale di Collaudo, Demo frontend, ...)
        if not collaudo_resoconto_pronto(md):
            continue  # resoconto di collaudo precompilato: il collaudo non si è ancora svolto
        items.append({
            "stem": md.stem,
            "codice": fm.get("codice_rilascio", md.parent.name),
            "tipo": format_tipo_riunione(fm.get("tipo_riunione", "")),
            "data": _fmt_date(fm.get("data_riunione", "")),
            "has_docx": md.with_suffix(".docx").exists(),
            "has_msg": md.with_suffix(".msg").exists(),
            "docx_superato": docx_superato(md),
        })
    return items


def collect_definitivi() -> list[dict]:
    items = []
    for md in sorted(LAVORI.glob("ADM*/inviati/*.md")):
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
        if not msg.exists() and not pdf.exists():
            continue
        items.append({
            "stem": md.stem,
            "codice": fm.get("codice_rilascio", md.parent.parent.name),
            "tipo": format_tipo_riunione(fm.get("tipo_riunione", "")),
            "data": _fmt_date(fm.get("data_riunione", "")),
            "scadenza": _fmt_date(fm.get("data_approvazione", "")),
            "has_msg": msg.exists(),
            "has_pdf": pdf.exists(),
        })
    return items


def collect_convocazioni() -> list[dict]:
    """Convocazioni (startup/collaudo) da inviare: .eml *Convocazione* nella root
    del rilascio (non ancora in inviati/)."""
    items = []
    for eml in sorted(LAVORI.glob("ADM*/*Convocazione*.eml")):
        if "inviati" in eml.parts:
            continue
        stem = eml.stem
        m = re.search(r"^(\S+) - (\d{8}) Convocazione (\w+)", stem)
        if m:
            g = m.group(2)
            data = f"{g[6:8]}/{g[4:6]}/{g[0:4]}"
            codice, tipo = m.group(1), m.group(3)
        else:
            codice, tipo, data = stem.split(" - ")[0], "?", ""
        items.append({"stem": stem, "codice": codice, "tipo": tipo, "data": data})
    return items


def build() -> None:
    today = date.today()
    bozze = collect_bozze()
    convocazioni = collect_convocazioni()
    definitivi = collect_definitivi()

    lines: list[str] = [
        "---",
        f"aggiornato: {today.isoformat()}",
        "---",
        "",
        "# Bozze da inviare",
        "",
        f"> Aggiornato: {today.strftime('%d/%m/%Y')} · {len(bozze)} bozz{'a' if len(bozze)==1 else 'e'} · {len(convocazioni)} convocazion{'e' if len(convocazioni)==1 else 'i'} · {len(definitivi)} definitiv{'o' if len(definitivi)==1 else 'i'}",
        "",
        "---",
        "",
        "## Bozze iniziali",
        "",
        "Spunta per segnare come inviato. Il prossimo sync archivia il file, imposta `data_scadenza_approvazione` e aggiorna la scheda rilascio.",
        "",
    ]

    if bozze:
        for b in bozze:
            docx = ("⚠️ superato (il sync del master lo rigenera)" if b.get("docx_superato") else "✅") if b["has_docx"] else "❌"
            msg = "✅" if b["has_msg"] else "❌"
            lines.append(
                f"- [ ] [[{b['stem']}]] · {b['codice']} · {b['tipo']} · {b['data']} · .docx {docx} · .msg {msg}"
            )
    else:
        lines.append("_Nessuna bozza in attesa._")

    lines += [
        "",
        "---",
        "",
        "## Convocazioni da inviare",
        "",
        "Spunta per segnare come inviata: il prossimo sync sposta la convocazione in `inviati/` e la rimuove da questa lista.",
        "",
    ]

    if convocazioni:
        for c in convocazioni:
            lines.append(
                f"- [ ] [[{c['stem']}]] · {c['codice']} · Convocazione {c['tipo']} · {c['data']}"
            )
    else:
        lines.append("_Nessuna convocazione in attesa._")

    lines += [
        "",
        "---",
        "",
        "## Definitivi",
        "",
        "Spunta per segnare come definitivo inviato. Il prossimo sync imposta `definitivo_inviato: true` e rimuove da questa lista.",
        "",
    ]

    if definitivi:
        for d in definitivi:
            msg = "✅" if d["has_msg"] else "❌"
            pdf = "✅" if d["has_pdf"] else "❌"
            lines.append(
                f"- [ ] [[{d['stem']}]] · {d['codice']} · {d['tipo']} · {d['data']} · scade {d['scadenza']} · .msg {msg} · .pdf {pdf}"
            )
    else:
        lines.append("_Nessun definitivo in attesa._")

    lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Bozze da inviare.md: {len(bozze)} bozze, {len(convocazioni)} convocazioni, {len(definitivi)} definitivi")


if __name__ == "__main__":
    build()
