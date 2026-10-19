"""
build_da_firmare.py — rigenera PO 2026/Da firmare.md

Promemoria per le lettere di fine collaudo (Trasmissione copia verbale di
collaudo, Richiesta estensione in esercizio) che devono passare dal workflow
Arcipelago (vedi Manuale protocollo/): due step, tracciati su flag nella
scheda rilascio ADMxxx-xx-xX.md:

  trasmissione_verbale_in_firma / trasmissione_verbale_protocollata
  estensione_esercizio_in_firma / estensione_esercizio_protocollata

Sezioni generate:
  ## Da mandare in firma              — lettera presente, *_in_firma non true
  ## In firma — attesa firma e protocollazione — *_in_firma true, *_protocollata non true

Una lettera protocollata (*_protocollata: true) esce dalla lista, così come
una già protocollata prima di questo tracking (protocollo_collaudo /
protocollo_estensione_esercizio già popolato). Una lettera non compare
nemmeno se `data_collaudo_effettiva` è vuota o futura (collaudo non ancora
davvero svolto) — vedi build_da_collaudare.py / Da collaudare.md.

Appena una lettera entra in "Da mandare in firma", popola anche
"<rilascio>/da mandare in firma/<Lettera>/" con tutti i PDF da caricare su
Arcipelago (vedi prepara_firma.py).

Uso:
    python scripts/build_da_firmare.py
Consuma i checkbox del file precedente PRIMA di rigenerare (stesso pattern
di archivia_inviati.py + build_bozze.py, qui in un unico script perché non
ci sono file da spostare, solo due flag per lettera).
"""
from __future__ import annotations
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import parse_frontmatter, update_frontmatter_keys
import prepara_firma

VAULT = Path(__file__).parent.parent
LAVORI = VAULT / "PO 2026"


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None
OUT = LAVORI / "Da firmare.md"

LETTERE = [
    ("Trasmissione copia verbale di collaudo", "trasmissione_verbale", "protocollo_collaudo"),
    ("Richiesta estensione in esercizio", "estensione_esercizio", "protocollo_estensione_esercizio"),
]

LINE_RE = re.compile(r"^- \[(x|X| )\] \[\[([^\]]+)\]\] · (.+)$")


def _consume_checkbox_state() -> None:
    """Legge Da firmare.md esistente e applica i flag per le righe spuntate."""
    if not OUT.exists():
        return
    text = OUT.read_text(encoding="utf-8")
    section = None
    for line in text.splitlines():
        if line.startswith("## Da mandare in firma"):
            section = "in_firma"
            continue
        if line.startswith("## In firma"):
            section = "protocollata"
            continue
        if line.startswith("## "):
            section = None
            continue
        m = LINE_RE.match(line.strip())
        if not m or m.group(1).strip() == "":
            continue
        codice, label = m.group(2), m.group(3)
        field_base = next((fb for lbl, fb, _ in LETTERE if lbl in label), None)
        if not field_base or section is None:
            continue
        scheda = LAVORI / codice / f"{codice}.md"
        if not scheda.exists():
            continue
        campo = f"{field_base}_{'in_firma' if section == 'in_firma' else 'protocollata'}"
        update_frontmatter_keys(scheda, {campo: "true"})
        print(f"  {codice}: {campo} = true")


def _collect(prepara: bool = True) -> tuple[list[dict], list[dict]]:
    """prepara=False: solo lettura (LeviathADM); la cartella per Arcipelago la prepara il sync."""
    da_mandare: list[dict] = []
    in_firma: list[dict] = []

    for label, field_base, protocollo_field in LETTERE:
        pattern = f"ADM*/*{label}.docx"
        for docx in sorted(LAVORI.glob(pattern)):
            if "inviati" in docx.parts:
                continue
            codice = docx.parent.name
            scheda = LAVORI / codice / f"{codice}.md"
            fm = parse_frontmatter(scheda) if scheda.exists() else {}
            if fm.get(f"{field_base}_protocollata", "").lower() == "true":
                continue
            protocollo_val = fm.get(protocollo_field, "").strip()
            if protocollo_val and "DA COMPLETARE" not in protocollo_val.upper():
                continue  # già protocollato in passato, prima di questo tracking
            effettiva = _parse_date(fm.get("data_collaudo_effettiva", ""))
            if effettiva is None or effettiva > date.today():
                continue  # collaudo non ancora davvero svolto — vedi Da collaudare.md
            item = {"codice": codice, "label": label}
            if fm.get(f"{field_base}_in_firma", "").lower() == "true":
                in_firma.append(item)
            else:
                if prepara:
                    prepara_firma.prepara_cartella(codice, label)
                da_mandare.append(item)

    return da_mandare, in_firma


def build() -> None:
    print("Da firmare: consumo checkbox precedenti...")
    _consume_checkbox_state()

    da_mandare, in_firma = _collect()

    today = date.today()
    lines: list[str] = [
        "---",
        f"aggiornato: {today.isoformat()}",
        "---",
        "",
        "# Da firmare",
        "",
        f"> Aggiornato: {today.strftime('%d/%m/%Y')} · {len(da_mandare)} da mandare in firma · {len(in_firma)} in attesa di firma/protocollazione",
        "",
        "---",
        "",
        "## Da mandare in firma",
        "",
        "Spunta quando la lettera è stata inviata alla firma del Dirigente su Arcipelago (vedi `Manuale protocollo/`). Il prossimo sync la sposta nella sezione sotto.",
        "",
    ]
    if da_mandare:
        for it in da_mandare:
            lines.append(f"- [ ] [[{it['codice']}]] · {it['label']}")
    else:
        lines.append("_Nessuna lettera in attesa._")

    lines += [
        "",
        "---",
        "",
        "## In firma — attesa firma e protocollazione",
        "",
        "Spunta quando la lettera è tornata firmata ed è stata protocollata/inviata a Sogei. Il prossimo sync la rimuove da questa lista (ricorda comunque di popolare `protocollo_collaudo`/`protocollo_estensione_esercizio` e la tabella `## Allegati protocolli` sulla scheda con il numero reale).",
        "",
    ]
    if in_firma:
        for it in in_firma:
            lines.append(f"- [ ] [[{it['codice']}]] · {it['label']}")
    else:
        lines.append("_Nessuna lettera in attesa._")

    lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Da firmare.md: {len(da_mandare)} da mandare in firma, {len(in_firma)} in attesa di protocollazione")


if __name__ == "__main__":
    build()
