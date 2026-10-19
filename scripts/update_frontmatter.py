"""
update_frontmatter.py — aggiorna il frontmatter dei file di rilascio esistenti
con i dati aggiornati dall'Excel, preservando il corpo del documento
(tabella Riunioni, Azioni aperte, Decisioni chiave, Prossima riunione).

Campi aggiornati dall'Excel:
  descrizione_progetto, descrizione_sottoprogetto, descrizione_rilascio,
  pm, ra, rp, referente_business, struttura_business, referente_sogei,
  vincoli_normativi, data_collaudo_prevista, data_rilascio_prevista

Campi preservati (aggiornati manualmente):
  stato, data_collaudo_effettiva, data_rilascio_effettiva
"""
from __future__ import annotations
import re
from pathlib import Path
from build_project_pages import load_releases, LAVORI


def _parse_fm_and_body(text: str) -> tuple[dict, str, str]:
    """Restituisce (fm_dict, raw_fm_block, body_after_fm)."""
    m = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if not m:
        return {}, "", text
    raw_block = m.group(1)
    body = m.group(2)
    fm: dict[str, str] = {}
    for line in raw_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, raw_block, body


def _build_fm_block(fm: dict) -> str:
    """Ricostruisce il blocco frontmatter mantenendo l'ordine canonico."""
    ordered_keys = [
        "codice_rilascio",
        "codice_sottoprogetto",
        "codice_progetto",
        "descrizione_progetto",
        "descrizione_sottoprogetto",
        "descrizione_rilascio",
        "stato",
        "pm",
        "ra",
        "rp",
        "struttura_business",
        "referente_business",
        "referente_sogei",
        "vincoli_normativi",
        "data_collaudo_prevista",
        "data_collaudo_effettiva",
        "data_rilascio_prevista",
        "data_rilascio_effettiva",
    ]
    lines = []
    seen = set()
    for k in ordered_keys:
        if k in fm:
            lines.append(f"{k}: {fm[k]}")
            seen.add(k)
    # Append any extra keys not in the canonical list
    for k, v in fm.items():
        if k not in seen:
            lines.append(f"{k}: {v}")
    return "\n".join(lines)


def update_release_frontmatter(rel: dict, rel_dir: Path) -> bool:
    cod = rel["cod_rilascio"]
    md_path = rel_dir / f"{cod}.md"
    if not md_path.exists():
        print(f"  MISSING {cod} — file non trovato")
        return False

    text = md_path.read_text(encoding="utf-8")
    fm, _, body = _parse_fm_and_body(text)

    if not fm:
        print(f"  SKIP    {cod} — frontmatter non trovato")
        return False

    # Aggiorna i campi derivati dall'Excel
    fm["descrizione_progetto"]    = rel["desc_progetto"]
    fm["descrizione_sottoprogetto"] = rel["desc_sub"]
    fm["descrizione_rilascio"]    = rel["desc_rilascio"]
    fm["pm"]                      = rel["pm"]
    fm["ra"]                      = rel["ra"]
    fm["rp"]                      = rel["rp"]
    fm["struttura_business"]      = rel["struttura_business"]
    fm["referente_business"]      = rel["referente_business"]
    fm["referente_sogei"]         = rel["referente_sogei"]
    fm["vincoli_normativi"]       = rel["vincoli_normativi"]
    fm["data_collaudo_prevista"]  = rel["data_collaudo_prevista"]
    fm["data_rilascio_prevista"]  = rel["data_rilascio_prevista"]

    # Aggiorna date effettive solo se presenti nell'Excel (non sovrascrivere valori manuali)
    if rel.get("data_collaudo_effettiva"):
        fm["data_collaudo_effettiva"] = rel["data_collaudo_effettiva"]
    if rel.get("data_rilascio_effettiva"):
        fm["data_rilascio_effettiva"] = rel["data_rilascio_effettiva"]

    # Assicura che i campi con valori vuoti esistano
    fm.setdefault("stato", "Bozza")
    fm.setdefault("data_collaudo_effettiva", "")
    fm.setdefault("data_rilascio_effettiva", "")

    new_fm_block = _build_fm_block(fm)
    new_text = f"---\n{new_fm_block}\n---\n{body}"

    if new_text == text:
        print(f"  UNCHANGED {cod}")
        return False

    md_path.write_text(new_text, encoding="utf-8")
    print(f"  UPDATED   {cod}")
    return True


def run():
    releases = load_releases()
    updated = 0
    for r in releases:
        rel_dir = LAVORI / r["cod_rilascio"]
        if rel_dir.is_dir():
            if update_release_frontmatter(r, rel_dir):
                updated += 1
        else:
            print(f"  MISSING DIR {r['cod_rilascio']}")
    print(f"\nAggiornati: {updated} / {len(releases)}")


if __name__ == "__main__":
    run()
