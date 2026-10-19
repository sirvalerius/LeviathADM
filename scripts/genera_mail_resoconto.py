"""
Genera il file .msg per la mail di comunicazione del resoconto di riunione.
Doppio clic sul .msg → si apre in Outlook, già pronto da inviare. Genera via
COM (richiede Outlook installato e avviabile sulla macchina): vedi il
docstring di `mail_utils.save_msg` per il perché (firma istituzionale nel
posto giusto, mai duplicata).

Uso:
    python scripts/genera_mail_resoconto.py <percorso_resoconto.md>
    python scripts/genera_mail_resoconto.py ADM953-01-0L 20260512

Output: stesso nome del .md, estensione .msg (stessa cartella del resoconto)
"""
from __future__ import annotations
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import (
    parse_frontmatter,
    business_days_after,
    format_tipo_riunione,
    resolve_recipients,
    save_msg,
)
from parse_presenze import find_presenze_csv, parse_presenze_csv
from update_anagrafica import update_from_presenze

VAULT = Path(__file__).parent.parent
TEMPLATE_PATH = VAULT / "Template" / "Template - Mail di comunicazione report .txt"
TEMPLATE_PATH_TELEMATICO = VAULT / "Template" / "Template - Mail di comunicazione report (approvazione telematica).txt"


def find_resoconto_md(arg1: str, arg2: str | None = None) -> Path:
    p = Path(arg1)
    if p.exists() and p.suffix == ".md":
        return p

    codice = arg1.upper()
    rel_dir = VAULT / "PO 2026" / codice
    if not rel_dir.exists():
        raise FileNotFoundError(f"Cartella rilascio non trovata: {rel_dir}")

    # I resoconti sono nella root del rilascio (nome contiene " - 20" es. "ADMxxx - 20260512 Resoconto ...")
    candidates = [f for f in rel_dir.glob("*.md") if " - 20" in f.name]
    if not candidates:
        raise FileNotFoundError(f"Nessun resoconto .md in {rel_dir}")

    if arg2:
        for c in candidates:
            if arg2 in c.name:
                return c
        raise FileNotFoundError(f"Nessun resoconto con data {arg2} in {rel_dir}")

    return sorted(candidates, key=lambda f: f.stat().st_mtime)[-1]


def parse_data_riunione(fm: dict) -> date | None:
    raw = fm.get("data_riunione", "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def format_date_it(d: date) -> str:
    mesi = [
        "", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
    ]
    return f"{d.day} {mesi[d.month]} {d.year}"


def build_body(tipo_display: str, data_riunione: date, scadenza: date,
               approvazione_telematica: bool = False) -> str:
    template_path = TEMPLATE_PATH_TELEMATICO if approvazione_telematica else TEMPLATE_PATH
    template = template_path.read_text(encoding="utf-8")
    body = template
    body = body.replace("di Startup", f"di {tipo_display}", 1)
    body = body.replace(" XX", f" {format_date_it(data_riunione)}", 1)
    body = body.replace("entro il XX", f"entro il {format_date_it(scadenza)}", 1)
    # Mantiene la chiusura "Saluti" ma rimuove la firma testuale del template:
    # nome/ufficio/telefono li aggiunge la firma di Outlook in composizione
    if "\nSaluti" in body:
        body = body[:body.index("\nSaluti") + len("\nSaluti")] + "\n"
    return body


def genera_eml(md_path: Path, extra_attachments: list[Path] | None = None) -> Path | None:
    """Genera (o rigenera) il .msg per il resoconto md_path.
    Ritorna il percorso del .msg salvato, o None in caso di errore.
    Non copia in Bozze da inviare/ né rigenera Scadenze.md (lo fa il chiamante)."""
    fm = parse_frontmatter(md_path)
    codice = fm.get("codice_rilascio", md_path.name.split(" - ")[0].upper())
    tipo_display = format_tipo_riunione(fm.get("tipo_riunione", "riunione"))

    data_riu = parse_data_riunione(fm)
    if data_riu is None:
        print(f"  ERRORE: data_riunione mancante in {md_path.name}")
        return None

    scadenza = business_days_after(date.today(), 5)
    subject = f"[{codice}] Resoconto {tipo_display} del {data_riu.strftime('%d/%m/%Y')}"
    # "approvazione telematicamente" nel testo (vedi Template/markdown/resoconto_collaudo_telematico.md)
    # → niente sezione FIRME nel resoconto, quindi la mail chiede esplicitamente
    # una risposta di approvazione invece del consueto silenzio-assenso.
    approvazione_telematica = "approvazione telematicamente" in md_path.read_text(encoding="utf-8")
    body = build_body(tipo_display, data_riu, scadenza, approvazione_telematica)

    rel_dir = VAULT / "PO 2026" / codice
    csv_path = find_presenze_csv(rel_dir, fm.get("data_riunione", ""))
    if csv_path:
        presenze = parse_presenze_csv(csv_path)
        update_from_presenze(presenze)

    to_emails = resolve_recipients(md_path, codice)

    docx_path = md_path.with_suffix(".docx")
    if not docx_path.exists():
        candidates = list(md_path.parent.glob(f"{md_path.stem}*.docx"))
        docx_path = candidates[0] if candidates else None

    save_path = md_path.with_suffix(".msg")
    attachments = ([docx_path] if docx_path else []) + (extra_attachments or [])
    save_msg(subject, body, to_emails, save_path, attachment_path=attachments)
    return save_path


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Uso: python genera_mail_resoconto.py <resoconto.md> [allegato1 allegato2 ...]")
        print("     python genera_mail_resoconto.py ADM953-01-0L [AAAAMMGG]")
        sys.exit(1)

    extra_attachments = [Path(a) for a in args[1:] if Path(a).is_file()]
    if extra_attachments:
        args = args[:1]

    md_path = find_resoconto_md(args[0], args[1] if len(args) > 1 else None)
    fm = parse_frontmatter(md_path)
    codice = fm.get("codice_rilascio", md_path.name.split(" - ")[0].upper())

    save_path = genera_eml(md_path, extra_attachments)
    if save_path is None:
        sys.exit(1)

    fm = parse_frontmatter(md_path)
    to_emails = resolve_recipients(md_path, codice)
    scadenza = business_days_after(date.today(), 5)

    print(f"Oggetto : [{codice}] Resoconto {format_tipo_riunione(fm.get('tipo_riunione',''))} del ...")
    print(f"A       : {'; '.join(to_emails) or '(nessun partecipante trovato)'}")
    print(f"Scadenza: {format_date_it(scadenza)}")
    missing = [e for e in to_emails if "[" in e]
    if missing:
        print("ATTENZIONE — email non trovate (da completare a mano):")
        for m in missing:
            print(f"  {m}")
    for extra in extra_attachments:
        print(f"Allegato extra: {extra.name}")
    # NOTA: la data_scadenza_approvazione NON viene scritta qui. La scadenza
    # indicata sopra è solo indicativa per il corpo della mail: quella
    # autoritativa la imposta archivia_inviati alla conferma dell'invio.
    print(f"Salvato  : {save_path}")
    print("Fai un sync per aggiornare Bozze da inviare/.")


if __name__ == "__main__":
    main()
