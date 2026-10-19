"""
Genera PO 2026/Rilasci.md dalla scheda di ciascun rilascio (frontmatter).

Fonte: frontmatter di ogni `PO 2026/ADMxxx-xx-xX/ADMxxx-xx-xX.md`
(descrizione_rilascio, stato, struttura_business, date, nota_variazione_date,
codice_rilascio_successivo per i rinominati/confluiti — v. SCHEMA.md).

Uso:
    python scripts/build_rilasci.py
"""
from __future__ import annotations
import sys
from datetime import date, datetime
from pathlib import Path

VAULT = Path(__file__).parent.parent
LAVORI = VAULT / "PO 2026"
OUT = LAVORI / "Rilasci.md"

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import parse_frontmatter  # noqa: E402


def _releases_in_scope() -> list[Path]:
    out = []
    for d in sorted(LAVORI.glob("ADM*")):
        if not d.is_dir() or "(" in d.name:
            continue
        if (d / f"{d.name}.md").exists():
            out.append(d)
    return out


def _sort_key(fm: dict) -> tuple:
    raw = fm.get("data_collaudo_prevista", "").strip()
    try:
        d = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        d = date.max
    return (d, fm.get("codice_rilascio", ""))


def build() -> None:
    attivi, storici = [], []
    for release_dir in _releases_in_scope():
        fm = parse_frontmatter(release_dir / f"{release_dir.name}.md")
        if fm.get("stato", "").strip().lower() == "rinominato":
            storici.append(fm)
        else:
            attivi.append(fm)
    attivi.sort(key=_sort_key)
    storici.sort(key=lambda fm: fm.get("codice_rilascio", ""))

    lines = [
        "---",
        f"aggiornato: {date.today():%Y-%m-%d}",
        "---",
        "",
        "# Rilasci PO 2026",
        "",
        "> Generata da `build_rilasci.py` — non editare a mano (si rigenera a ogni sync sul master)."
        " Fonte: frontmatter di ogni scheda rilascio.",
        "",
        "## Panoramica",
        "",
        "Ordinati per data collaudo prevista. \"Var. date\" mostra `nota_variazione_date` se"
        " compilata nella scheda (nessun calcolo automatico: il dato PO originario non è"
        " altrimenti tracciato). Collaudo eff. / Rilascio eff. valorizzati solo a evento avvenuto.",
        "",
        "| Codice | Descrizione rilascio | Stato | Struttura | Collaudo prev. | Rilascio prev. "
        "| Fine analisi | Var. date | Collaudo eff. | Rilascio eff. |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for fm in attivi:
        cod = fm.get("codice_rilascio", "")
        lines.append(
            f"| [[{cod}]] | {fm.get('descrizione_rilascio','')} | {fm.get('stato','')} "
            f"| {fm.get('struttura_business','')} | {fm.get('data_collaudo_prevista','')} "
            f"| {fm.get('data_rilascio_prevista','')} | {fm.get('data_fine_analisi','')} "
            f"| {fm.get('nota_variazione_date','')} | {fm.get('data_collaudo_effettiva','')} "
            f"| {fm.get('data_rilascio_effettiva','')} |"
        )

    if storici:
        lines += ["", "## Storico (rinominati / confluiti)", "",
                   "| Codice | Descrizione rilascio | Confluito in | Struttura |",
                   "| --- | --- | --- | --- |"]
        for fm in storici:
            cod = fm.get("codice_rilascio", "")
            succ = fm.get("codice_rilascio_successivo", "")
            succ_link = f"[[{succ}]]" if succ else "—"
            lines.append(
                f"| [[{cod}]] | {fm.get('descrizione_rilascio','')} | {succ_link} "
                f"| {fm.get('struttura_business','')} |"
            )

    lines += ["", "---", "", "## Team per rilascio", "",
               "| Codice | RA | RP | Ref. SOGEI | Ref. Business |",
               "| --- | --- | --- | --- | --- |"]
    for fm in attivi:
        cod = fm.get("codice_rilascio", "")
        business = fm.get("referente_business", "")
        struttura = fm.get("struttura_business", "")
        business_cell = f"{business} ({struttura})" if business else "—"
        lines.append(
            f"| [[{cod}]] | {fm.get('ra','')} | {fm.get('rp','')} "
            f"| {fm.get('referente_sogei','')} | {business_cell} |"
        )

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Rilasci: {len(attivi)} attivi · {len(storici)} storici -> {OUT.name}")


if __name__ == "__main__":
    build()
