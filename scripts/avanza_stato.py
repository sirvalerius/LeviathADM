"""
Avanzamento dello stato dei punti di piano (`stato` nel frontmatter della scheda ADMxxx-xx-xX.md).

Regola unica, replicata in leviathadm_web/src/26_stato.js (golden `stato`): dai dati già nel vault
(frontmatter + righe `## Riunioni`) si ricava lo stato suggerito; si scrive solo in avanti, mai `Rinominato`,
mai con `stato_manuale: true`. Vedi docs/superpowers/specs/2026-10-27-avanzamento-stato-design.md.

Uso batch (sync del master, daily_check, console):
    python scripts/avanza_stato.py [--dry-run]
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

VAULT = Path(__file__).parent.parent
LAVORI = VAULT / "PO 2026"
sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import parse_frontmatter, update_frontmatter_keys  # noqa: E402

ORDINE = ["Da Avviare", "Bozza", "Startup", "Analisi", "In corso", "In Verifica", "Collaudo", "Concluso"]
RINOMINATO = "Rinominato"
_SEZ_RIUNIONI = re.compile(r"^## Riunioni\s*$(.*?)(?=^## |\Z)", re.M | re.S)


def rango(stato: str) -> int:
    try:
        return ORDINE.index((stato or "").strip())
    except ValueError:
        return -1


def _vero(v: str) -> bool:
    return (v or "").strip().lower() == "true"


def _pieno(v: str) -> bool:
    return bool((v or "").strip())


def _data_passata(v: str, oggi: date) -> bool:
    s = (v or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return False
    try:
        return date.fromisoformat(s) <= oggi
    except ValueError:
        return False


def suggerisci(fm: dict, riunioni: list[dict], oggi: date) -> str | None:
    """Stato suggerito dai fatti della scheda, o None. `riunioni`: dict con `fase` e `inviato` (bool)."""
    fasi = [((r.get("fase") or "").strip().lower(), bool(r.get("inviato"))) for r in riunioni]
    g = lambda k: fm.get(k, "")  # noqa: E731
    if _data_passata(g("data_rilascio_effettiva"), oggi) or _pieno(g("protocollo_estensione_esercizio")) \
            or _vero(g("estensione_esercizio_protocollata")):
        return "Concluso"
    if _data_passata(g("data_collaudo_effettiva"), oggi) or _pieno(g("protocollo_collaudo")) \
            or any(f.startswith("collaudo") and inv for f, inv in fasi) \
            or any(_vero(g(k)) for k in ("trasmissione_verbale_in_firma", "trasmissione_verbale_protocollata",
                                        "estensione_esercizio_in_firma")):
        return "Collaudo"
    if _pieno(g("protocollo_disponibilita_collaudo")) or _pieno(g("data_disponibilita_collaudo")) \
            or any(f.startswith("collaudo") for f, _ in fasi):
        return "In Verifica"
    if any(f.startswith("sal") for f, _ in fasi) or _pieno(g("protocollo_analisi")) \
            or _pieno(g("protocollo_approvazione_analisi")):
        return "In corso"
    if any("analisi" in f for f, _ in fasi):
        return "Analisi"
    if any(f.startswith("startup") for f, _ in fasi):
        return "Startup"
    return None


def avanza(fm: dict, riunioni: list[dict], oggi: date) -> str | None:
    """Nuovo stato da scrivere, o None: solo in avanti, mai Rinominato, mai con stato_manuale."""
    stato = (fm.get("stato") or "").strip()
    if stato == RINOMINATO or _vero(fm.get("stato_manuale", "")):
        return None
    s = suggerisci(fm, riunioni, oggi)
    return s if s and rango(s) > rango(stato) else None


def _parse_table(section: str) -> list[list[str]]:
    """Copia di leviathadm.vault.parsers.parse_table (lo script resta autonomo): righe dopo l'intestazione,
    senza separatore; si ferma alla prima riga non tabella dopo l'inizio."""
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
            continue
        if not header_skipped:
            header_skipped = True
            continue
        rows.append(cells)
    return rows


def riunioni_da_testo(text: str) -> list[dict]:
    """Righe della tabella ## Riunioni come [{fase, inviato}] — stessa lettura di loader._riunioni
    (tabelle a 5 o 4 colonne, riga segnaposto `—` ignorata)."""
    m = _SEZ_RIUNIONI.search(text)
    if not m:
        return []
    out = []
    for row in _parse_table(m.group(1)):
        if len(row) not in (4, 5) or row[0] in ("", "—", "-"):
            continue
        out.append({"fase": row[1], "inviato": "✅" in row[-1]})
    return out


def avanza_scheda(path: Path, oggi: date | None = None) -> tuple[str, str] | None:
    """Applica `avanza` alla scheda e scrive `stato`; ritorna (da, a) o None."""
    text = path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    if not fm:
        return None          # senza frontmatter update_frontmatter_keys non scriverebbe: nessun esito fasullo
    nuovo = avanza(fm, riunioni_da_testo(text), oggi or date.today())
    if not nuovo:
        return None
    update_frontmatter_keys(path, {"stato": nuovo})
    return (fm.get("stato", "") or "").strip(), nuovo


def avanza_tutte(oggi: date | None = None, dry_run: bool = False,
                 errori: list[tuple[str, str]] | None = None) -> list[tuple[str, str, str]]:
    """Tutte le schede PO 2026/ADM*/ADM*.md: [(codice, da, a)] delle schede avanzate (o da avanzare, con dry_run).
    Una scheda illeggibile non ferma il batch: viene stampata e aggiunta a `errori` (codice, messaggio)."""
    oggi = oggi or date.today()
    out = []
    for scheda in sorted(LAVORI.glob("ADM*/*.md")):
        if scheda.stem != scheda.parent.name:
            continue
        try:
            if dry_run:
                text = scheda.read_text(encoding="utf-8")
                fm = parse_frontmatter(text)
                nuovo = avanza(fm, riunioni_da_testo(text), oggi)
                esito = ((fm.get("stato", "") or "").strip(), nuovo) if nuovo else None
            else:
                esito = avanza_scheda(scheda, oggi)
        except Exception as e:  # noqa: BLE001 — una scheda rotta non deve fermare sync e daily check
            print(f"   ERRORE {scheda.stem}: {e} — proseguo")
            if errori is not None:
                errori.append((scheda.stem, str(e)))
            continue
        if esito:
            out.append((scheda.stem, esito[0], esito[1]))
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    dry = "--dry-run" in args
    esiti = avanza_tutte(dry_run=dry)
    if not esiti:
        print("Stati: nessuno stato da avanzare.")
        return 0
    for codice, da, a in esiti:
        print(f"   {codice}: {da or '(vuoto)'} → {a}" + ("  [dry-run]" if dry else ""))
    print(f"Stati: {len(esiti)} schede {'da avanzare' if dry else 'avanzate'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
