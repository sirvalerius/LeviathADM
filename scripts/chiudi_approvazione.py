"""
chiudi_approvazione.py — Chiude le approvazioni tacite dei resoconti scaduti.

Per ogni resoconto in PO 2026/*/inviati/ con:
  - inviato: true
  - data_scadenza_approvazione: YYYY-MM-DD (≤ oggi)
  - data_approvazione: (vuota o assente)
  - salta_definitivo: non "true" (flag per escludere un resoconto dalla generazione
    del definitivo, es. rilasci Conclusi per cui non ha senso un ulteriore invio)

Esegue:
  1. Aggiorna frontmatter md: data_approvazione = oggi
  2. Aggiorna .docx: compila il campo "Data approvazione"
  3. Converte .docx → .pdf (tramite Microsoft Word via docx2pdf)
  4. Genera mail "versione definitiva" con PDF allegato (.msg)

Uso:
  python scripts/chiudi_approvazione.py           # processa tutti i candidati
  python scripts/chiudi_approvazione.py --dry-run # elenca senza modificare
"""
from __future__ import annotations
import sys
from datetime import date
from pathlib import Path

from docx2pdf import convert as docx2pdf_convert

sys.path.insert(0, str(Path(__file__).parent))
from fill_template import set_data_approvazione
from mail_utils import (
    format_tipo_riunione,
    parse_frontmatter,
    resolve_recipients,
    save_msg,
    update_frontmatter_keys,
)

VAULT = Path(__file__).parent.parent
TEMPLATE_DEFINITIVA = VAULT / "Template" / "Template - Mail versione definitiva.txt"
BOZZE = VAULT / "Bozze da inviare" / "Definitivi"


def _copia_in_bozze(eml_path: Path, pdf_path: Path) -> None:
    BOZZE.mkdir(parents=True, exist_ok=True)
    import shutil
    for src in (eml_path, pdf_path):
        if src and src.exists():
            dst = BOZZE / src.name
            try:
                if dst.exists():
                    dst.unlink()
                shutil.copy2(str(src), str(dst))
            except OSError as e:
                print(f"    WARN Bozze: {src.name}: {e}")
    print(f"    Copiato in Bozze da inviare/Definitivi/")


def _format_date_it(d: date) -> str:
    mesi = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
            "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    return f"{d.day} {mesi[d.month]} {d.year}"


def find_pending() -> list[Path]:
    """Trova resoconti inviati con scadenza approvazione scaduta e non ancora approvati."""
    today = date.today()
    results = []
    for md_path in VAULT.glob("PO 2026/*/inviati/*.md"):
        if "_archivio" in md_path.parts:
            continue
        fm = parse_frontmatter(md_path)
        if fm.get("inviato", "").lower() != "true":
            continue
        if fm.get("salta_definitivo", "").lower() == "true":
            continue
        scadenza_str = fm.get("data_scadenza_approvazione", "").strip()
        data_appr = fm.get("data_approvazione", "").strip()
        if not scadenza_str or data_appr:
            continue
        try:
            if date.fromisoformat(scadenza_str) <= today:
                results.append(md_path)
        except ValueError:
            pass
    return results


def chiudi(md_path: Path) -> None:
    today = date.today()
    today_str = today.isoformat()
    today_it = _format_date_it(today)

    fm = parse_frontmatter(md_path)
    codice = fm.get("codice_rilascio", md_path.name.split(" - ")[0])
    tipo_raw = fm.get("tipo_riunione", "riunione")
    tipo_display = format_tipo_riunione(tipo_raw)
    data_riu_str = fm.get("data_riunione", "")
    scadenza_str = fm.get("data_scadenza_approvazione", "")

    try:
        data_riu = date.fromisoformat(data_riu_str)
        data_riu_dmy = data_riu.strftime("%d/%m/%Y")
        data_riu_it = _format_date_it(data_riu)
    except Exception:
        data_riu_dmy = data_riu_str
        data_riu_it = data_riu_str

    # La data di approvazione è la scadenza tacita indicata nella mail di invio,
    # non la data odierna in cui viene generato il PDF.
    try:
        scadenza_d = date.fromisoformat(scadenza_str)
        scadenza_it = _format_date_it(scadenza_d)
        appr_str = scadenza_d.isoformat()
        appr_dmy = scadenza_d.strftime("%d/%m/%Y")
        appr_it = scadenza_it
    except Exception:
        scadenza_it = scadenza_str
        appr_str = today_str
        appr_dmy = today.strftime("%d/%m/%Y")
        appr_it = today_it

    # 1. Aggiorna frontmatter
    update_frontmatter_keys(md_path, {"data_approvazione": appr_str})
    print(f"    Frontmatter aggiornato: data_approvazione = {appr_str}")

    # 2. Aggiorna Data approvazione nel .docx
    docx_path = md_path.with_suffix(".docx")
    if not docx_path.exists():
        print(f"    WARN: .docx non trovato ({docx_path.name}) — salto PDF e mail")
        return
    set_data_approvazione(docx_path, appr_dmy)
    print(f"    .docx aggiornato")

    # 3. Converti a PDF
    pdf_path = docx_path.with_suffix(".pdf")
    docx2pdf_convert(str(docx_path), str(pdf_path))
    print(f"    PDF generato: {pdf_path.name}")

    # 4. Mail versione definitiva
    template = TEMPLATE_DEFINITIVA.read_text(encoding="utf-8")
    body = (template
            .replace("{{TIPO}}", tipo_display)
            .replace("{{DATA_RIUNIONE}}", data_riu_it)
            .replace("{{DATA_APPROVAZIONE}}", appr_it)
            .replace("{{DATA_SCADENZA}}", scadenza_it))
    # Mantiene "Saluti" ma scarta la firma testuale: la aggiunge Outlook
    if "\nSaluti" in body:
        body = body[:body.index("\nSaluti") + len("\nSaluti")] + "\n"

    subject = f"[{codice}] Resoconto {tipo_display} del {data_riu_dmy} — versione definitiva"

    to_emails = resolve_recipients(md_path, codice)
    for m in [e for e in to_emails if "[" in e]:
        print(f"    WARN: {m} — destinatario da completare a mano in Outlook")
    eml_path = md_path.with_name(md_path.stem + " - definitivo.msg")
    save_msg(subject, body, to_emails, eml_path, attachment_path=pdf_path)
    print(f"    MSG definitivo: {eml_path.name}")

    # 5. Copia in Bozze da inviare/ in attesa di invio
    _copia_in_bozze(eml_path, pdf_path)


def find_approved_not_sent() -> list[Path]:
    """Resoconti con data_approvazione impostata ma definitivo_inviato != true."""
    results = []
    for md_path in VAULT.glob("PO 2026/*/inviati/*.md"):
        if "_archivio" in md_path.parts:
            continue
        fm = parse_frontmatter(md_path)
        if not fm.get("data_approvazione", "").strip():
            continue
        if fm.get("definitivo_inviato", "").lower() == "true":
            continue
        if fm.get("salta_definitivo", "").lower() == "true":
            continue
        results.append(md_path)
    return results


def find_approvati_incompleti() -> list[Path]:
    """Approvazioni TACITE registrate da LeviathADM (solo data_approvazione, = scadenza già passata)
    a cui manca il PDF o il .msg definitivo: chiudi() le completa senza cambiare la data.
    Esclusi: data_approvazione manuale (≠ scadenza, chiudi() la sovrascriverebbe), scadenza futura,
    file senza .docx (niente PDF possibile) o senza tipo_riunione (non è un resoconto)."""
    today = date.today()
    out = []
    for md in find_approved_not_sent():
        fm = parse_frontmatter(md)
        scadenza = fm.get("data_scadenza_approvazione", "").strip()
        if not fm.get("tipo_riunione", "").strip() or not md.with_suffix(".docx").exists():
            continue
        if fm.get("data_approvazione", "").strip() != scadenza:
            continue
        try:
            if date.fromisoformat(scadenza) > today:
                continue
        except ValueError:
            continue
        if not md.with_suffix(".pdf").exists() or not md.with_name(md.stem + " - definitivo.msg").exists():
            out.append(md)
    return out


def regen_eml_only(md_path: Path) -> None:
    """Rigenera solo il .msg definitivo (PDF già esistente) con la firma corretta."""
    fm = parse_frontmatter(md_path)
    codice = fm.get("codice_rilascio", md_path.name.split(" - ")[0])
    tipo_raw = fm.get("tipo_riunione", "riunione")
    tipo_display = format_tipo_riunione(tipo_raw)
    data_riu_str = fm.get("data_riunione", "")
    scadenza_str = fm.get("data_scadenza_approvazione", "")
    appr_str = fm.get("data_approvazione", "").strip()

    try:
        data_riu = date.fromisoformat(data_riu_str)
        data_riu_dmy = data_riu.strftime("%d/%m/%Y")
        data_riu_it = _format_date_it(data_riu)
    except Exception:
        data_riu_dmy = data_riu_str
        data_riu_it = data_riu_str

    try:
        appr_it = _format_date_it(date.fromisoformat(appr_str))
    except Exception:
        appr_it = appr_str

    try:
        scadenza_it = _format_date_it(date.fromisoformat(scadenza_str))
    except Exception:
        scadenza_it = scadenza_str

    pdf_path = md_path.with_suffix(".pdf")
    if not pdf_path.exists():
        print(f"    SKIP (PDF mancante): {md_path.name}")
        return

    template = TEMPLATE_DEFINITIVA.read_text(encoding="utf-8")
    body = (template
            .replace("{{TIPO}}", tipo_display)
            .replace("{{DATA_RIUNIONE}}", data_riu_it)
            .replace("{{DATA_APPROVAZIONE}}", appr_it)
            .replace("{{DATA_SCADENZA}}", scadenza_it))
    # Mantiene "Saluti" ma scarta la firma testuale: la aggiunge Outlook
    if "\nSaluti" in body:
        body = body[:body.index("\nSaluti") + len("\nSaluti")] + "\n"

    subject = f"[{codice}] Resoconto {tipo_display} del {data_riu_dmy} — versione definitiva"

    to_emails = resolve_recipients(md_path, codice)
    for m in [e for e in to_emails if "[" in e]:
        print(f"    WARN: {m} — destinatario da completare a mano in Outlook")
    eml_path = md_path.with_name(md_path.stem + " - definitivo.msg")
    save_msg(subject, body, to_emails, eml_path, attachment_path=pdf_path)
    print(f"    MSG definitivo: {eml_path.name}")
    _copia_in_bozze(eml_path, pdf_path)


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    if "--regen-eml" in sys.argv:
        targets = find_approved_not_sent()
        if not targets:
            print("Nessun definitivo da rigenerare.")
            return
        print(f"Rigenero {len(targets)} .msg definitiv{'o' if len(targets)==1 else 'i'}:")
        for md_path in targets:
            print(f">> {md_path.name}")
            regen_eml_only(md_path)
        return

    pending = find_pending()
    # approvazioni tacite già segnate da LeviathADM (solo frontmatter): PDF e .msg ancora da produrre
    pending += [md for md in find_approvati_incompleti() if md not in pending]
    if not pending:
        print("Nessun resoconto con scadenza approvazione scaduta.")
        return

    print(f"Trovati {len(pending)} resocont{'o' if len(pending) == 1 else 'i'} da chiudere:")
    for md_path in pending:
        fm = parse_frontmatter(md_path)
        print(f"  {md_path.name}  (scadenza: {fm.get('data_scadenza_approvazione', '?')})")

    if dry_run:
        print("\n[dry-run] Nessuna modifica applicata.")
        return

    print()
    for md_path in pending:
        print(f">> {md_path.name}")
        chiudi(md_path)

    print(f"\nCompletato. {len(pending)} resocont{'o' if len(pending) == 1 else 'i'} chius{'o' if len(pending) == 1 else 'i'}.")

    # Aggiorna il dashboard Scadenze.md
    try:
        import build_scadenze
        build_scadenze.build()
        print("Scadenze.md aggiornato.")
    except Exception as e:
        print(f"(build_scadenze: {e})")


if __name__ == "__main__":
    main()
