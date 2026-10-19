"""
build_project_pages.py — costruisce la gerarchia Progetto > Sottoprogetto > Rilascio
leggendo i dati dall'Excel ufficiale.

Crea:
  PO 2026/Progetti/ADMxxx.md
  PO 2026/Sottoprogetti/ADMxxx-xx.md
  PO 2026/2026 - Lavori/ADMxxx-xx-xX/ADMxxx-xx-xX.md   (rinomina progetto.md)
  ed elimina eventuali vecchi progetto.md
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
import openpyxl

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import parse_frontmatter  # noqa: E402

VAULT       = Path(__file__).parent.parent
EXCEL       = VAULT / "PO 2026" / "_risorse" / "PM_PO2026 Aggiornato 20260408 working copy.xlsx"
LAVORI      = VAULT / "PO 2026"
PROJ_DIR    = VAULT / "PO 2026" / "Progetti"
SUB_DIR     = VAULT / "PO 2026" / "Sottoprogetti"


# ---------------------------------------------------------------------------
# Lettura Excel
# ---------------------------------------------------------------------------

def clean(v) -> str:
    return str(v or "").strip()

def strip_prefix(s: str) -> str:
    """Rimuove il prefisso 'F - ' dalle descrizioni rilascio."""
    return re.sub(r"^[A-Z] - ", "", s).strip()

def load_releases() -> list[dict]:
    wb = openpyxl.load_workbook(str(EXCEL), data_only=True)
    ws = wb["Working Copy"]
    releases = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        pm = clean(row[21]).upper()
        if "LUNARDI" not in pm:
            continue
        cod_rel = clean(row[5])
        if not cod_rel or len(cod_rel) < 9:
            continue
        # Ricava codici progetto e sottoprogetto dal codice rilascio
        # es. ADM953-01-0L → progetto=ADM953, sottoprogetto=ADM953-01
        parts = cod_rel.split("-")
        cod_prog = parts[0]                          # ADM953
        cod_sub  = "-".join(parts[:2])               # ADM953-01

        # Referente SOGEI: col 36 in UPPER CASE → Title Case
        ref_sogei_raw = clean(row[36])
        ref_sogei = " ".join(w.capitalize() for w in ref_sogei_raw.split()) if ref_sogei_raw else ""

        def _date(v) -> str:
            return str(v).split(" ")[0] if v and str(v) not in ("None", "") else ""

        releases.append({
            "cod_rilascio":          cod_rel,
            "cod_progetto":          cod_prog,
            "cod_sub":               cod_sub,
            "area":                  clean(row[0]),
            "desc_progetto":         clean(row[2]),
            "desc_sub":              clean(row[3]),
            "desc_rilascio":         strip_prefix(clean(row[8])),
            "pm":                    clean(row[21]).title(),
            "ra":                    clean(row[20]),
            "rp":                    clean(row[22]),
            "referente_business":    clean(row[26]),
            "struttura_business":    clean(row[25]),
            "referente_sogei":       ref_sogei,
            "vincoli_normativi":       clean(str(row[38] or "NO")),
            "data_collaudo_prevista":  _date(row[12]),
            "data_collaudo_effettiva": _date(row[13]),
            "data_rilascio_prevista":  _date(row[14]),
            "data_rilascio_effettiva": _date(row[15]),
        })
    return releases


# ---------------------------------------------------------------------------
# Lettura _index.md esistente (tracker di fase + stato)
# ---------------------------------------------------------------------------

def parse_tracker(text: str) -> list[dict]:
    rows = []
    in_table = False
    for line in text.splitlines():
        if "| Fase" in line:
            in_table = True
            continue
        if in_table:
            if not line.strip().startswith("|"):
                break
            if line.strip().startswith("|---"):
                continue
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) >= 4:
                # Col: Fase | Data | Trascritto | Resoconto | Inviato
                resoconto_raw = parts[3] if len(parts) > 3 else ""
                rows.append({
                    "fase":      parts[0],
                    "data":      parts[1],
                    "resoconto": resoconto_raw,
                    "inviato":   parts[4] if len(parts) > 4 else parts[-1],
                })
    return rows


def resoconto_link(raw: str) -> str:
    """Converte il path del resoconto in un wikilink se è un .md, altrimenti '—'."""
    raw = raw.strip("`").strip()
    if not raw or raw == "—":
        return "—"
    p = Path(raw)
    if p.suffix == ".md":
        return f"[[{p.stem}]]"
    return "—"

def load_existing_page(rel_dir: Path, cod: str) -> dict:
    """Legge l'eventuale progetto.md o ADMxxx.md già esistente."""
    for name in (f"{cod}.md", "progetto.md"):
        p = rel_dir / name
        if p.exists():
            text = p.read_text(encoding="utf-8")
            return {
                "azioni":    _extract_section(text, "## Azioni aperte"),
                "decisioni": _extract_section(text, "## Decisioni chiave"),
                "prossima":  _extract_section(text, "## Prossima riunione"),
            }
    return {}

def _extract_section(text: str, header: str) -> str:
    m = re.search(re.escape(header) + r"\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


# ---------------------------------------------------------------------------
# Scrittura nodi
# ---------------------------------------------------------------------------

def write_if_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")
        print(f"  CREATED {path.relative_to(VAULT)}")
    else:
        print(f"  EXISTS  {path.relative_to(VAULT)}")

def write_project(cod: str, area: str, desc: str) -> None:
    path = PROJ_DIR / f"{cod}.md"
    write_if_new(path, f"""---
tipo: progetto
codice: {cod}
area: {area}
---

# {cod} — {desc}

[[ADM]]
""")

def write_subproject(cod_sub: str, cod_prog: str, desc: str) -> None:
    path = SUB_DIR / f"{cod_sub}.md"
    write_if_new(path, f"""---
tipo: sottoprogetto
codice: {cod_sub}
---

# {cod_sub} — {desc}

[[{cod_prog}]]
""")

def write_release_page(rel: dict, rel_dir: Path) -> None:
    cod     = rel["cod_rilascio"]
    out     = rel_dir / f"{cod}.md"
    old_idx = rel_dir / "_index.md"

    # Una volta creata, la scheda viene curata manualmente (Team, Documenti,
    # Riunioni con colonna Trascritto, frontmatter `stato`/`data_fine_analisi`,
    # ecc.). Riscriverla farebbe perdere tutte queste informazioni.
    # Se serve aggiornare i dati da Excel, modificare manualmente il frontmatter.
    if out.exists():
        print(f"  SKIP    {out.relative_to(VAULT)} (già presente, non sovrascrivo)")
        return

    # Recupera tracker di fase dall'_index.md
    tracker = []
    stato   = "Bozza"
    collaudo = rel["data_collaudo_prevista"]
    if old_idx.exists():
        t = old_idx.read_text(encoding="utf-8")
        fm = parse_frontmatter(t)
        tracker = parse_tracker(t)
        stato   = fm.get("stato", stato)

    riunioni_rows = "".join(
        f"| {r['data']} | {r['fase']} | {resoconto_link(r.get('resoconto',''))} | {r['inviato'] if r['inviato'] in ('✅','❌') else '❌'} |\n"
        for r in tracker if r["data"] and r["data"] != "—"
    ) or "| — | — | — | — |\n"

    # Recupera contenuto personalizzato dall'eventuale pagina precedente
    prev = load_existing_page(rel_dir, cod)
    azioni    = prev.get("azioni")    or "<!-- Aggiornare dopo ogni riunione -->"
    decisioni = prev.get("decisioni") or "<!-- Data — descrizione decisione -->"
    prossima  = prev.get("prossima")  or "<!-- Data · Tipo -->"

    content = f"""---
codice_rilascio: {cod}
codice_sottoprogetto: {rel['cod_sub']}
codice_progetto: {rel['cod_sub'].split('-')[0]}
descrizione_progetto: {rel['desc_progetto']}
descrizione_sottoprogetto: {rel['desc_sub']}
descrizione_rilascio: {rel['desc_rilascio']}
stato: Bozza
pm: {rel.get('pm', '')}
ra: {rel.get('ra', '')}
rp: {rel.get('rp', '')}
referente_business: {rel.get('referente_business', '')}
struttura_business: {rel.get('struttura_business', '')}
referente_sogei: {rel.get('referente_sogei', '')}
vincoli_normativi: {rel.get('vincoli_normativi', 'NO')}
data_collaudo_prevista: {rel.get('data_collaudo_prevista', '')}
data_collaudo_effettiva: {rel.get('data_collaudo_effettiva', '')}
data_rilascio_prevista: {rel.get('data_rilascio_prevista', '')}
data_rilascio_effettiva: {rel.get('data_rilascio_effettiva', '')}
nota_variazione_date:
protocollo_analisi:
protocollo_approvazione_analisi:
protocollo_collaudo:
protocollo_estensione_esercizio:
protocollo_disponibilita_collaudo:
data_disponibilita_collaudo:
---

# {cod} — {rel['desc_rilascio']}

> Collaudo previsto: **{collaudo}** · Stato: **{stato}**

[[{rel['cod_sub']}]]

## Riunioni

| Data | Fase | Resoconto | Inviato |
|------|------|-----------|---------|
{riunioni_rows}
## Azioni aperte

{azioni}

## Decisioni chiave

{decisioni}

## Prossima riunione

{prossima}

## Allegati protocolli

> Compila le celle. `Prot. ADM n.` / `Data prot. ADM` = numero e data di protocollazione ADM; `Rif. SOGEI` = riferimento del documento SOGEI (≠ protocollo ADM).

| Tipo | Documento | Prot. ADM n. | Data prot. ADM | Rif. SOGEI | Registro |
|------|-----------|:------------:|:--------------:|------------|----------|
| Analisi | | | | | Registro Contratto (ingresso) |
| Approvazione analisi | | | | | Registro Ufficiale (uscita) |
| Disponibilità a collaudo | | | | | Registro Contratto (ingresso) |
| Collaudo | | | | | |
| Estensione esercizio | | | | | |
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"  RELEASE {out.relative_to(VAULT)}")

    # Elimina vecchio progetto.md se diverso dal nuovo
    old_prog = rel_dir / "progetto.md"
    if old_prog.exists() and old_prog != out:
        old_prog.unlink()
        print(f"  REMOVED {old_prog.relative_to(VAULT)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run():
    releases = load_releases()

    # Raccoglie progetti e sottoprogetti unici
    projects = {}
    subprojects = {}
    for r in releases:
        projects[r["cod_progetto"]] = (r["area"], r["desc_progetto"])
        subprojects[r["cod_sub"]] = (r["cod_progetto"], r["desc_sub"])

    print("\n=== Progetti ===")
    for cod, (area, desc) in sorted(projects.items()):
        write_project(cod, area, desc)

    print("\n=== Sottoprogetti ===")
    for cod_sub, (cod_prog, desc) in sorted(subprojects.items()):
        write_subproject(cod_sub, cod_prog, desc)

    print("\n=== Rilasci ===")
    for r in releases:
        rel_dir = LAVORI / r["cod_rilascio"]
        if rel_dir.is_dir():
            write_release_page(r, rel_dir)
        else:
            print(f"  MISSING {r['cod_rilascio']} — cartella non trovata")

if __name__ == "__main__":
    run()
