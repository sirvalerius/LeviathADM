"""
build_da_collaudare.py — rigenera PO 2026/Da collaudare.md

Elenca i punti di piano per cui è arrivata la disponibilità al collaudo
(`data_disponibilita_collaudo` valorizzata) e il collaudo è previsto
(`data_collaudo_prevista`) ma non ancora effettivamente svolto
(`data_collaudo_effettiva` vuota).
La colonna "Data collaudo effettiva" è compilabile a mano (AAAA-MM-GG o
GG/MM/AAAA): appena il sync la trova valorizzata, scrive
`data_collaudo_effettiva` sulla scheda rilascio e il punto esce dalla lista.

Finché `data_collaudo_effettiva` è vuota o futura, le lettere di chiusura
collaudo (Trasmissione verbale/Richiesta estensione) di quel rilascio NON
compaiono in Da firmare.md, anche se il relativo .docx esiste già — vedi
il gate temporale in build_da_firmare.py.

Uso:
    python scripts/build_da_collaudare.py
Va chiamato PRIMA di build_da_firmare.py (consuma la data appena inserita
in modo che il gate la veda già aggiornata nello stesso sync).
"""
from __future__ import annotations
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import parse_frontmatter, update_frontmatter_keys

VAULT = Path(__file__).parent.parent
LAVORI = VAULT / "PO 2026"
OUT = LAVORI / "Da collaudare.md"

ROW_RE = re.compile(r"^\|\s*\[\[([^\]|]+)[^\]]*\]\]\s*\|([^|]*)\|([^|]*)\|\s*$")


def parse_date(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def _fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _consume_tabella() -> None:
    """Legge Da collaudare.md esistente: se la colonna 'Data collaudo
    effettiva' è stata compilata, scrive data_collaudo_effettiva sulla scheda."""
    if not OUT.exists():
        return
    for line in OUT.read_text(encoding="utf-8").splitlines():
        m = ROW_RE.match(line.strip())
        if not m:
            continue
        codice, _previsto, effettiva_raw = m.groups()
        codice = codice.strip()
        d = parse_date(effettiva_raw)
        if d is None:
            continue
        scheda = LAVORI / codice / f"{codice}.md"
        if not scheda.exists():
            continue
        update_frontmatter_keys(scheda, {"data_collaudo_effettiva": d.isoformat()})
        print(f"  {codice}: data_collaudo_effettiva = {d.isoformat()}")


def _collect() -> list[dict]:
    items = []
    for d in sorted(LAVORI.glob("ADM*")):
        if not d.is_dir() or "(" in d.name:
            continue
        scheda = d / f"{d.name}.md"
        if not scheda.exists():
            continue
        fm = parse_frontmatter(scheda)
        if fm.get("stato", "") in ("Rinominato", "Concluso"):
            continue
        previsto = fm.get("data_collaudo_prevista", "").strip()
        effettiva = fm.get("data_collaudo_effettiva", "").strip()
        disponibilita = fm.get("data_disponibilita_collaudo", "").strip()
        if not previsto or effettiva or not disponibilita:
            continue  # niente da collaudare finché non è arrivata la disponibilità
        d_previsto = parse_date(previsto)
        items.append({
            "codice": fm.get("codice_rilascio", scheda.stem),
            "previsto": _fmt_date(d_previsto) if d_previsto else previsto,
        })
    return items


def build() -> None:
    print("Da collaudare: consumo date compilate...")
    _consume_tabella()

    items = _collect()
    today = date.today()

    lines: list[str] = [
        "---",
        f"aggiornato: {today.isoformat()}",
        "---",
        "",
        "# Da collaudare",
        "",
        f"> Aggiornato: {today.strftime('%d/%m/%Y')} · {len(items)} punt{'o' if len(items)==1 else 'i'} in attesa di collaudo",
        "",
        "Compila la colonna **Data collaudo effettiva** (AAAA-MM-GG o GG/MM/AAAA) appena il collaudo si è davvero svolto. Il prossimo sync scrive `data_collaudo_effettiva` sulla scheda e il punto esce da questa lista. Finché la data è vuota o futura, le lettere di chiusura collaudo di quel rilascio non compaiono in [[Da firmare]].",
        "",
        "---",
        "",
        "## Punti da collaudare",
        "",
        "| Rilascio | Collaudo previsto | Data collaudo effettiva |",
        "|---|---|---|",
    ]

    if items:
        for it in items:
            lines.append(f"| [[{it['codice']}]] | {it['previsto']} | |")
    else:
        lines.append("| _Nessuno._ | | |")

    lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Da collaudare.md: {len(items)} punti in attesa di collaudo")


if __name__ == "__main__":
    build()
