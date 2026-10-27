"""
update_anagrafica.py — aggiorna l'Anagrafica con i partecipanti nuovi di una riunione.

Crea stub .md per chi non ha ancora una scheda, senza sovrascrivere
le schede esistenti. Separa ADM da SOGEI per dominio email.

Uso standalone:
  python update_anagrafica.py <csv_path> [<data_riunione AAAA-MM-GG>]

Uso come modulo:
  from update_anagrafica import update_from_presenze
  update_from_presenze(presenze_dict)   # dict restituito da parse_presenze_csv()
"""
from __future__ import annotations
import sys
from pathlib import Path

VAULT       = Path(__file__).parent.parent
ANAGRAFICA  = VAULT / "Anagrafica"


# ---------------------------------------------------------------------------
# Normalizzazione
# ---------------------------------------------------------------------------

def _slug(nome: str) -> str:
    """Ritorna il nome normalizzato per uso come nome file (identico al display name)."""
    return nome.strip()


def _email_to_nome(email: str) -> str | None:
    """
    Prova a ricavare Nome Cognome dall'email ADM (firstname.lastname@adm.gov.it).
    Restituisce None se il pattern non è riconoscibile.
    """
    local = email.split("@")[0].lower()
    # gestisce anche albertogiacomo.orellana → Venusta Maestrale
    parts = local.replace(".", " ").split()
    if len(parts) >= 2:
        return " ".join(p.title() for p in parts)
    return None


# ---------------------------------------------------------------------------
# Creazione schede
# ---------------------------------------------------------------------------

def _write_adm_stub(nome: str, email: str, direzione: str = "", ufficio: str = "") -> Path:
    path = ANAGRAFICA / f"{nome}.md"
    content = f"""---
organizzazione: ADM
direzione: {direzione}
ufficio: {ufficio}
email: {email}
ruolo_tipico:
---

# {nome}

[[ADM]]
"""
    path.write_text(content, encoding="utf-8")
    return path


def _write_sogei_stub(nome: str, email: str = "") -> Path:
    path = ANAGRAFICA / f"{nome}.md"
    content = f"""---
organizzazione: SOGEI
direzione:
ufficio:
email: {email}
ruolo_tipico:
---

# {nome}

[[SOGEI]]
"""
    path.write_text(content, encoding="utf-8")
    return path


def _write_unknown_stub(nome: str, email: str = "") -> Path:
    path = ANAGRAFICA / f"{nome}.md"
    content = f"""---
organizzazione: [da verificare]
direzione:
ufficio:
email: {email}
ruolo_tipico:
---

# {nome}

"""
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Aggiornamento email su schede esistenti
# ---------------------------------------------------------------------------

def _update_email_if_missing(path: Path, email: str) -> bool:
    """Scrive l'email nel frontmatter se il campo è vuoto. Restituisce True se modificato."""
    if not email or "@" not in email:
        return False
    import re
    text = path.read_text(encoding="utf-8")
    if re.search(r"^email:\s*\S", text, re.MULTILINE):
        return False  # già valorizzata, non sovrascrivere
    text = re.sub(r"^email:\s*$", f"email: {email}", text, flags=re.MULTILINE)
    path.write_text(text, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Lookup anagrafica
# ---------------------------------------------------------------------------

def anagrafica_info(nome: str) -> dict:
    """
    Legge il frontmatter di Anagrafica/{nome}.md e restituisce un dict con
    almeno le chiavi: organizzazione, direzione, ufficio, email.
    Restituisce {} se il file non esiste.
    """
    path = ANAGRAFICA / f"{nome}.md"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    import re
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    info = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            info[k.strip()] = v.strip()
    return info


def resolve_rb_ufficio(nome: str) -> tuple[str, str]:
    """
    Restituisce (direzione, ufficio) per l'RB leggendo l'Anagrafica.
    Se il file non esiste o i campi sono vuoti, chiede all'utente da terminale.
    """
    info = anagrafica_info(nome)
    direzione = info.get("direzione", "").strip()
    ufficio   = info.get("ufficio", "").strip()

    if not direzione and not ufficio:
        print(f"\nRB '{nome}' non trovato in Anagrafica o campi direzione/ufficio vuoti.")
        direzione = input(f"  Inserisci Direzione per {nome} (Invio per lasciare vuoto): ").strip()
        ufficio   = input(f"  Inserisci Ufficio per {nome} (Invio per lasciare vuoto): ").strip()
        # Aggiorna la scheda se esiste
        path = ANAGRAFICA / f"{nome}.md"
        if path.exists() and (direzione or ufficio):
            text = path.read_text(encoding="utf-8")
            import re
            if direzione:
                text = re.sub(r"^direzione:.*$", f"direzione: {direzione}", text, flags=re.MULTILINE)
            if ufficio:
                text = re.sub(r"^ufficio:.*$", f"ufficio: {ufficio}", text, flags=re.MULTILINE)
            path.write_text(text, encoding="utf-8")
            print(f"  Anagrafica/{nome}.md aggiornato.")

    return direzione, ufficio


# ---------------------------------------------------------------------------
# Entry point principale
# ---------------------------------------------------------------------------

def update_from_presenze(presenze: dict) -> dict[str, list[str]]:
    """
    Crea stub Anagrafica per i partecipanti non ancora presenti.

    Args:
        presenze: dict restituito da parse_presenze_csv(), con chiavi
                  "adm", "sogei", "altri".

    Returns:
        {"created": [...], "existing": [...]}
    """
    created = []
    existing = []

    # ADM
    for p in presenze.get("adm", []):
        nome  = _slug(p["nome"])
        email = p.get("email", "")
        path  = ANAGRAFICA / f"{nome}.md"
        if path.exists():
            existing.append(nome)
            if _update_email_if_missing(path, email):
                print(f"  UPDATED ADM   {nome} → {email}")
        else:
            _write_adm_stub(nome, email)
            created.append(nome)
            print(f"  CREATED ADM   {nome}")

    # SOGEI — ora ogni entry è {"nome": str, "email": str}
    for p in presenze.get("sogei", []):
        if isinstance(p, dict):
            nome, email = _slug(p["nome"]), p.get("email", "")
        else:
            nome, email = _slug(p), ""  # retrocompatibilità
        path = ANAGRAFICA / f"{nome}.md"
        if path.exists():
            existing.append(nome)
            if _update_email_if_missing(path, email):
                print(f"  UPDATED SOGEI {nome} → {email}")
        else:
            _write_sogei_stub(nome, email)
            created.append(nome)
            print(f"  CREATED SOGEI {nome}")

    # Altri (dominio sconosciuto)
    for p in presenze.get("altri", []):
        nome  = _slug(p["nome"])
        email = p.get("email", "")

        # Controlla se esiste già una scheda con nome invertito (Cognome Nome)
        # Es. "Cassiopea Quadrante" → prova "Quadrante Cassiopea"
        parts = nome.split()
        inverted = " ".join(reversed(parts)) if len(parts) >= 2 else None
        if inverted and (ANAGRAFICA / f"{inverted}.md").exists():
            existing.append(inverted)
            continue  # scheda canonica già presente, non creare duplicato

        path = ANAGRAFICA / f"{nome}.md"
        if path.exists():
            existing.append(nome)
            if _update_email_if_missing(path, email):
                print(f"  UPDATED ???   {nome} → {email}")
        else:
            _write_unknown_stub(nome, email)
            created.append(nome)
            print(f"  CREATED ???   {nome}")

    return {"created": created, "existing": existing}


# ---------------------------------------------------------------------------
# Standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from parse_presenze import find_presenze_csv, parse_presenze_csv

    if len(sys.argv) < 2:
        print("Uso: python update_anagrafica.py <csv_path|cartella_rilascio> [AAAA-MM-GG]")
        sys.exit(1)

    target = Path(sys.argv[1])
    data   = sys.argv[2] if len(sys.argv) > 2 else None

    if target.is_dir():
        csv_path = find_presenze_csv(target, data)
        if not csv_path:
            print(f"Nessun CSV trovato in {target}")
            sys.exit(1)
    else:
        csv_path = target

    print(f"CSV: {csv_path.name}\n")
    presenze = parse_presenze_csv(csv_path)
    result   = update_from_presenze(presenze)

    print(f"\nCreati  : {len(result['created'])}")
    print(f"Esistenti: {len(result['existing'])}")
