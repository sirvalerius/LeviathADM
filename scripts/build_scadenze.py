"""
Genera PO 2026/Scadenze.md con le scadenze imminenti, scadute e future.

Fonti:
  - data_fine_analisi, data_collaudo_prevista, data_rilascio_prevista
    dal frontmatter di ogni scheda ADMxxx-xx-xX.md
  - Azioni aperte con "scadenza: DD/MM/YYYY" o "scadenza: YYYY-MM-DD"

Uso:
    python scripts/build_scadenze.py
"""
from __future__ import annotations
import re
import sys
from datetime import date, timedelta
from pathlib import Path

VAULT = Path(__file__).parent.parent
LAVORI = VAULT / "PO 2026"
OUT = LAVORI / "Scadenze.md"

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import salta_definitivo  # noqa: E402
from mail_utils import parse_frontmatter  # noqa: E402

# ── helpers ──────────────────────────────────────────────────────────────────

def parse_date(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def week_end(today: date) -> date:
    """Domenica della settimana corrente."""
    return today + timedelta(days=6 - today.weekday())


# ── raccolta scadenze ─────────────────────────────────────────────────────────

DATE_RE = re.compile(
    r"scadenza:\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
ACTION_RE = re.compile(r"^- \[ \] (.+)$", re.MULTILINE)


def collect(today: date) -> list[dict]:
    entries: list[dict] = []

    for md in sorted(LAVORI.glob("ADM*/*.md")):
        # solo schede di rilascio (non resoconti, non file in inviati/)
        if " - 20" in md.name:
            continue
        if "inviati" in md.parts:
            continue

        text = md.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        codice = fm.get("codice_rilascio", md.stem)
        descr = fm.get("descrizione_rilascio", "")
        stato = fm.get("stato", "")
        storica = stato in ("Rinominato", "Concluso")   # niente milestone; tassativa e azioni restano

        # milestone da frontmatter
        milestones = [
            ("fine_analisi",  "Fine analisi",   fm.get("data_fine_analisi", ""),    fm.get("data_fine_analisi", "")),
            ("collaudo",      "Collaudo",        fm.get("data_collaudo_prevista", ""), fm.get("data_collaudo_effettiva", "")),
            ("rilascio",      "Rilascio",        fm.get("data_rilascio_prevista", ""), fm.get("data_rilascio_effettiva", "")),
        ]
        for key, label, raw_prev, raw_eff in milestones:
            if raw_eff or storica:          # già avvenuto, o scheda storica
                continue
            d = parse_date(raw_prev)
            if d is None:
                continue
            entries.append({
                "codice": codice,
                "descr": descr,
                "tipo": label,
                "data": d,
                "note": "",
                "stato": stato,
                "tassativo": False,
            })

        # Scadenza tassativa: convocazione collaudo entro 20gg dalla
        # disponibilità a collaudo (obbligo normativo — non silenziabile).
        # Il conteggio reale parte dalla protocollazione ADM; se non è ancora
        # nota si usa la data dichiarata da SOGEI come stima prudenziale
        # (la scadenza reale è uguale o successiva, mai precedente).
        data_disp = parse_date(fm.get("data_disponibilita_collaudo", ""))
        if data_disp and not fm.get("data_collaudo_effettiva", "").strip():
            provvisoria = "DA COMPLETARE" in fm.get("protocollo_disponibilita_collaudo", "").upper()
            scadenza_conv = data_disp + timedelta(days=20)
            nota = f"TASSATIVO — disponibilità a collaudo del {fmt_date(data_disp)}"
            if provvisoria:
                nota += " (PROVVISORIA: data SOGEI, protocollo ADM non ancora noto — la scadenza reale potrebbe essere successiva)"
            entries.append({
                "codice": codice,
                "descr": descr,
                "tipo": "Convocazione collaudo",
                "data": scadenza_conv,
                "note": nota,
                "stato": stato,
                "tassativo": True,
            })

        # azioni aperte con data esplicita
        in_azioni = False
        for line in text.splitlines():
            if line.strip().startswith("## Azioni"):
                in_azioni = True
                continue
            if in_azioni and line.startswith("## "):
                break
            if not in_azioni:
                continue
            if not line.startswith("- [ ]"):
                continue
            m = DATE_RE.search(line)
            if not m:
                continue
            d = parse_date(m.group(1))
            if d is None:
                continue
            # testo breve dell'azione (senza wikilink e scadenza)
            note = re.sub(r"\[\[.*?\]\]", "", line[6:])
            note = re.sub(r"—\s*scadenza:.*", "", note, flags=re.IGNORECASE)
            note = re.sub(r"\s+", " ", note).strip(" —·")
            entries.append({
                "codice": codice,
                "descr": descr,
                "tipo": "Azione",
                "data": d,
                "note": note[:80] + ("…" if len(note) > 80 else ""),
                "stato": stato,
                "tassativo": False,
            })

    # ── scadenze approvazione resoconti ──────────────────────────────────────
    # Legge data_scadenza_approvazione dai resoconti (root rilascio e inviati/)
    for md in sorted(LAVORI.glob("ADM*/**/*.md")):
        if "_archivio" in md.parts or any(p.startswith("_storico") for p in md.parts):
            continue   # copie archiviate/storiche: il resoconto vivo è altrove
        if " - 20" not in md.name:
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        if not fm.get("tipo_riunione", "").strip():
            continue   # Verbale di Collaudo, Demo…: non sono resoconti
        if salta_definitivo(fm):
            continue   # chiudi_approvazione non li chiuderà mai (flag o collaudo): nessuna scadenza da mostrare
        # Il timer di convalida tacita parte solo a invio confermato dall'utente
        if fm.get("inviato", "").lower() != "true":
            continue
        scadenza_str = fm.get("data_scadenza_approvazione", "").strip()
        data_appr = fm.get("data_approvazione", "").strip()
        if not scadenza_str or data_appr:
            continue
        d = parse_date(scadenza_str)
        if d is None:
            continue
        codice = fm.get("codice_rilascio", "")
        tipo_riu = fm.get("tipo_riunione", "riunione")
        entries.append({
            "codice": codice,
            "descr": fm.get("data_riunione", ""),
            "tipo": f"Appr. {tipo_riu}",
            "data": d,
            "note": "scadenza convalida tacita",
            "stato": "",
            "tassativo": False,
        })

    return entries


# ── rendering ─────────────────────────────────────────────────────────────────

def delta_label(d: date, today: date) -> str:
    diff = (d - today).days
    if diff < 0:
        return f"scad. da {-diff}gg"
    if diff == 0:
        return "oggi"
    if diff == 1:
        return "domani"
    return f"tra {diff}gg"


MESI = ["", "gen", "feb", "mar", "apr", "mag", "giu",
        "lug", "ago", "set", "ott", "nov", "dic"]


def fmt_date(d: date) -> str:
    return f"{d.day} {MESI[d.month]} {d.year}"


def render_table(entries: list[dict], today: date) -> str:
    if not entries:
        return "_Nessuna._\n"
    rows = ["| Rilascio | Tipo | Data | Δ | Note |",
            "|---|---|---|---|---|"]
    for e in sorted(entries, key=lambda x: x["data"]):
        link = f"[[{e['codice']}]]"
        rows.append(
            f"| {link} | {e['tipo']} | {fmt_date(e['data'])} "
            f"| {delta_label(e['data'], today)} | {e['note']} |"
        )
    return "\n".join(rows) + "\n"


def build(today: date | None = None) -> None:
    if today is None:
        today = date.today()
    sun = week_end(today)

    entries = collect(today)

    tassative = [e for e in entries if e.get("tassativo")]
    resto     = [e for e in entries if not e.get("tassativo")]

    scadute   = [e for e in resto if e["data"] < today]
    settimana = [e for e in resto if today <= e["data"] <= sun]
    prossime  = [e for e in resto if e["data"] > sun]

    lines = [
        "# Scadenze PO 2026",
        "",
        f"> Aggiornato: {fmt_date(today)} · settimana fino a {fmt_date(sun)}",
        "",
        "---",
        "",
        "## 🚨 Tassative — convocazione collaudo",
        "",
        render_table(tassative, today) if tassative else "_Nessuna._\n",
        "---",
        "",
        "## 🔴 Scadute",
        "",
        render_table(scadute, today),
        "## 🟡 Questa settimana",
        "",
        render_table(settimana, today),
        "## ⚪ Prossime",
        "",
        render_table(prossime, today),
    ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    n_tot = len(entries)
    if tassative:
        print(f"ATTENZIONE: {len(tassative)} scadenza/e TASSATIVA/E convocazione collaudo!")
    print(f"Scadenze: {len(scadute)} scadute · {len(settimana)} questa settimana "
          f"· {len(prossime)} prossime ({n_tot} totali) -> {OUT.name}")


if __name__ == "__main__":
    build()
