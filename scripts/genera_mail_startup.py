"""
Genera il file .eml per la mail di convocazione riunione di Startup.
Doppio clic sul .eml → si apre nel client email predefinito (nuovo Outlook incluso).
Non richiede Python né win32com sul PC di destinazione.

Uso:
    python scripts/genera_mail_startup.py ADM953-01-0L
    python scripts/genera_mail_startup.py ADM953-01-0L --data "giovedì 21 maggio 2026 ore 14:30"

Output: PO 2026/2026 - Lavori/{codice}/{codice} - Riunione di Startup.eml
"""
from __future__ import annotations
import sys
from email.message import EmailMessage
import email.policy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import (
    read_release,
    get_email,
    team_from_release,
)

VAULT = Path(__file__).parent.parent
TEMPLATE_PATH = VAULT / "Template" / "Template - Mail di invito startup.txt"


def build_body(fm: dict, data_riunione: str | None) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    codice_sp = fm.get("codice_sottoprogetto", fm.get("codice_rilascio", "???"))
    desc_sp = fm.get("descrizione_sottoprogetto", "<Descrizione Sottoprogetto>")
    codice_ril = fm.get("codice_rilascio", "???")
    desc_ril = fm.get("descrizione_rilascio", "<Descrizione rilascio>")

    body = template
    body = body.replace("ADMXXX-XX <Descrizione Sottoprogetto>", f"{codice_sp} {desc_sp}")
    body = body.replace("ADMXXX-XX-XX <Descrizione rilascio>", f"{codice_ril} {desc_ril}")

    if data_riunione:
        body = body.replace(
            "In caso di indisponibilità propongo le seguenti date alternative:",
            f"La riunione è programmata per: {data_riunione}\n\n"
            "In caso di indisponibilità propongo le seguenti date alternative:",
        )

    return body


def collect_recipients(fm: dict, release_text: str, pm_email: str) -> list[str]:
    team = team_from_release(release_text)

    to_names: list[str] = []
    for role in ("RA", "RP", "RB"):
        to_names.extend(team[role])
    to_names.extend(team["SOGEI"])

    if not any([team["RA"], team["RP"], team["RB"], team["SOGEI"]]):
        for field in ("ra", "rp", "referente_business"):
            v = fm.get(field, "").strip()
            if v:
                to_names.append(v)
        sogei = fm.get("referente_sogei", "").strip()
        if sogei:
            to_names.append(sogei)

    return [e for name in to_names if (e := get_email(name)) and e != pm_email]


def save_eml(subject: str, body: str, to_emails: list[str], save_path: Path) -> None:
    msg = EmailMessage(policy=email.policy.SMTP)
    msg["Subject"] = subject
    msg["To"] = ", ".join(e for e in to_emails if "[" not in e)
    msg.set_content(body, charset="utf-8")

    missing = [e for e in to_emails if "[" in e]
    if missing:
        print("ATTENZIONE — email non trovate (da completare a mano):")
        for m in missing:
            print(f"  {m}")

    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(msg.as_bytes(policy=email.policy.SMTP))
    print(f"Salvato  : {save_path}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print("Uso: python genera_mail_startup.py <CODICE_RILASCIO> [--data '<data riunione>']")
        sys.exit(1)

    codice = args[0].upper()
    data_riunione: str | None = None
    if "--data" in args:
        idx = args.index("--data")
        if idx + 1 < len(args):
            data_riunione = args[idx + 1]

    fm, release_text = read_release(codice)

    pm_name = fm.get("pm", "").strip()
    pm_email = get_email(pm_name) if pm_name else ""

    desc_ril = fm.get("descrizione_rilascio", "")
    subject = f"[{codice}] Riunione di Startup — {desc_ril}" if desc_ril else f"[{codice}] Riunione di Startup"

    body = build_body(fm, data_riunione)
    to_emails = collect_recipients(fm, release_text, pm_email)

    save_path = VAULT / "PO 2026" / "2026 - Lavori" / codice / f"{codice} - Riunione di Startup.eml"

    print(f"Oggetto : {subject}")
    print(f"A       : {'; '.join(to_emails) or '(nessun destinatario trovato)'}")
    print()

    save_eml(subject, body, to_emails, save_path)


if __name__ == "__main__":
    main()
