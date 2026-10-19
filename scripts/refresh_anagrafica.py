"""
refresh_anagrafica.py — aggiorna l'anagrafica con i dati reali dai CSV presenze.

- Inietta le email reali (con priorità sui CSV rispetto alla derivazione automatica)
- Corregge schede vuote o incomplete
- Rimuove duplicati noti
- Usa la stessa logica di update_anagrafica.py per scrivere il frontmatter

Uso: python scripts/refresh_anagrafica.py [--dry-run]
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from parse_presenze import parse_presenze_csv
from mail_utils import parse_frontmatter as _parse_fm_str

VAULT = Path(__file__).parent.parent
ANAGRAFICA = VAULT / "Anagrafica"
LAVORI = VAULT / "PO 2026"

DRY_RUN = "--dry-run" in sys.argv
sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# Raccolta email da tutti i CSV presenze
# ---------------------------------------------------------------------------

def collect_emails_from_csvs() -> dict[str, str]:
    """Restituisce {nome_normalizzato: email} da tutti i CSV presenze."""
    email_map: dict[str, str] = {}
    for csv_path in sorted(LAVORI.rglob("*.csv")):
        try:
            presenze = parse_presenze_csv(csv_path)
        except Exception as e:
            print(f"  SKIP CSV {csv_path.name}: {e}")
            continue
        for group in ("adm", "sogei"):
            for entry in presenze.get(group, []):
                nome = entry.get("nome", "").strip()
                email = entry.get("email", "").strip()
                if nome and email and "@" in email:
                    existing = email_map.get(nome)
                    if existing and existing != email:
                        print(f"  CONFLITTO {nome}: {existing!r} vs {email!r} — tengo il primo")
                    else:
                        email_map[nome] = email
    return email_map


# ---------------------------------------------------------------------------
# Parsing / scrittura frontmatter
# ---------------------------------------------------------------------------

def read_frontmatter(text: str) -> dict[str, str]:
    return _parse_fm_str(text)


def set_frontmatter_field(text: str, field: str, value: str) -> str:
    """Sostituisce o aggiunge un campo nel frontmatter."""
    pattern = rf"^{re.escape(field)}:.*$"
    replacement = f"{field}: {value}"
    if re.search(pattern, text, re.MULTILINE):
        return re.sub(pattern, replacement, text, flags=re.MULTILINE)
    # Il campo non esiste — aggiungilo prima del --- di chiusura
    return re.sub(r"\n---", f"\n{replacement}\n---", text, count=1)


def stub_adm(nome: str, email: str) -> str:
    return f"""---
organizzazione: ADM
direzione:
ufficio:
email: {email}
ruolo_tipico:
---

# {nome}

[[ADM]]
"""


def stub_sogei(nome: str, email: str) -> str:
    return f"""---
organizzazione: SOGEI
direzione:
ufficio:
email: {email}
ruolo_tipico:
---

# {nome}

[[SOGEI]]
"""


# ---------------------------------------------------------------------------
# Operazioni sui file
# ---------------------------------------------------------------------------

def update_email(path: Path, email: str, force: bool = False) -> bool:
    """
    Aggiorna il campo email nel frontmatter.
    Se force=True sovrascrive anche un'email già presente.
    """
    text = path.read_text(encoding="utf-8")
    fm = read_frontmatter(text)
    current = fm.get("email", "").strip()
    if current == email:
        return False
    if current and not force:
        return False  # già valorizzata, non sovrascrivere
    new_text = set_frontmatter_field(text, "email", email)
    if not DRY_RUN:
        path.write_text(new_text, encoding="utf-8")
    return True


def fix_empty_file(path: Path, nome: str, email: str, org: str) -> None:
    """Riscrive da zero un file vuoto o senza frontmatter."""
    if org == "SOGEI":
        content = stub_sogei(nome, email)
    else:
        content = stub_adm(nome, email)
    if not DRY_RUN:
        path.write_text(content, encoding="utf-8")
    print(f"  REBUILT  {path.name}")


def delete_file(path: Path, reason: str) -> None:
    print(f"  DELETE   {path.name}  ({reason})")
    if not DRY_RUN:
        path.unlink()


# ---------------------------------------------------------------------------
# Casi speciali noti
# ---------------------------------------------------------------------------

DUPLICATES_TO_REMOVE = {
    # nome_file_da_eliminare: nome_file_canonico_da_tenere
    "Amerigo Ortensia": "Ortensia Amerigo",
}

# File che devono avere un'org specifica (override)
ORG_OVERRIDES = {
    "Tramontana Marzia": "SOGEI",
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if DRY_RUN:
        print("=== DRY RUN — nessuna modifica su disco ===\n")

    print("Raccolta email dai CSV presenze...")
    email_map = collect_emails_from_csvs()
    print(f"  {len(email_map)} email trovate.\n")

    updated, rebuilt, deleted, skipped = 0, 0, 0, 0

    for path in sorted(ANAGRAFICA.glob("*.md")):
        nome = path.stem

        # 1. Elimina duplicati noti
        if nome in DUPLICATES_TO_REMOVE:
            canonical = DUPLICATES_TO_REMOVE[nome]
            delete_file(path, f"duplicato di '{canonical}'")
            deleted += 1
            continue

        # 2. Leggi contenuto
        text = path.read_text(encoding="utf-8").strip()

        # 3. File vuoto o senza frontmatter → ricostruisci
        if not text or not re.search(r"^---", text):
            email = email_map.get(nome, "")
            org = ORG_OVERRIDES.get(nome, "SOGEI" if email.endswith("@sogei.it") else "ADM")
            fix_empty_file(path, nome, email, org)
            rebuilt += 1
            continue

        # 4. Applica override org se necessario
        if nome in ORG_OVERRIDES:
            fm = read_frontmatter(text)
            current_org = fm.get("organizzazione", "").strip()
            target_org = ORG_OVERRIDES[nome]
            if current_org != target_org:
                new_text = set_frontmatter_field(text, "organizzazione", target_org)
                # Aggiungi link [[SOGEI]] se mancante
                if "[[SOGEI]]" not in new_text:
                    new_text = new_text.rstrip() + "\n\n[[SOGEI]]\n"
                if not DRY_RUN:
                    path.write_text(new_text, encoding="utf-8")
                    text = new_text
                print(f"  ORG FIX  {nome}: {current_org!r} → {target_org!r}")

        # 5. Aggiorna email se disponibile dai CSV
        email = email_map.get(nome, "")
        if email:
            changed = update_email(path, email, force=False)
            if changed:
                print(f"  EMAIL    {nome} → {email}")
                updated += 1
            else:
                skipped += 1
        else:
            skipped += 1

    print(f"\nRiepilogo:")
    print(f"  Aggiornati (email): {updated}")
    print(f"  Ricostruiti       : {rebuilt}")
    print(f"  Eliminati         : {deleted}")
    print(f"  Invariati         : {skipped}")


if __name__ == "__main__":
    main()
