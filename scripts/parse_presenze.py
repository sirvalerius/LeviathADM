"""
parse_presenze.py — legge i CSV presenze di Microsoft Teams.

I CSV di Teams sono salvati in UTF-16 LE con BOM, separatore TAB,
con sezioni numerate ("1. Riepilogo", "2. Partecipanti", ecc.).

Funzioni pubbliche:
  find_presenze_csv(rel_dir, data_riunione) -> Path | None
  parse_presenze_csv(csv_path) -> dict con chiavi:
      "adm":   list[dict]  — {nome, email, ruolo_teams}
      "sogei": list[dict]  — {nome, email}
      "altri": list[dict]  — {nome, email} (dominio non riconosciuto)
      "data":  str         — data riunione dal CSV (AAAA-MM-GG)
      "titolo": str        — titolo riunione
"""
from __future__ import annotations
import re
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Ricerca CSV nella cartella del rilascio
# ---------------------------------------------------------------------------

def find_presenze_csv(rel_dir: Path, data_riunione: str | None = None) -> Path | None:
    """
    Cerca un CSV presenze Teams nella cartella rel_dir.

    Se data_riunione è fornita (formato AAAA-MM-GG), preferisce il CSV
    la cui data nel nome file corrisponde. Altrimenti restituisce il più recente.

    Il formato del nome file Teams è:
        "... - Report sulla presenza M-D-YY.csv"
    """
    # Cerca nella root del rilascio e ricorsivamente in _fonti/ (e sottocartelle)
    csvs = list(rel_dir.glob("*.csv")) + list((rel_dir / "_fonti").rglob("*.csv") if (rel_dir / "_fonti").exists() else [])
    if not csvs:
        return None

    if data_riunione:
        try:
            dt = datetime.strptime(data_riunione, "%Y-%m-%d")
        except ValueError:
            return None
        # Teams usa M-D-YY, ma il giorno può avere lo zero (5-07-26): accetta entrambi, a numero intero
        pattern = re.compile(rf"(?<!\d){dt.month}-0?{dt.day}-{str(dt.year)[2:]}(?!\d)")
        for c in sorted(csvs):
            if pattern.search(c.name):
                return c
        return None        # data nota ma nessun CSV: mai il CSV di un'altra riunione

    # Aquilone data: il più recente per data di modifica
    return max(csvs, key=lambda p: p.stat().st_mtime)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _decode_csv(path: Path) -> str:
    """Gestisce UTF-16 LE con BOM (default Teams Windows) e UTF-8 come fallback."""
    raw = path.read_bytes()
    for enc in ("utf-16", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return raw.decode("latin-1")


def _normalize_name(raw: str) -> str:
    """
    Converte COGNOME NOME (Esterno) / (Non verificato) → Nome Cognome.
    Gestisce anche nomi già in Title Case.
    """
    # Rimuove suffissi Teams (IT e EN)
    name = re.sub(r"\s*\((?:Esterno|Non verificato|Estero|Guest|Ospite|External|Unverified)\)\s*", "", raw, flags=re.IGNORECASE).strip()
    # Se tutto maiuscolo → converti in Title Case
    if name == name.upper():
        name = name.title()
    return name


def _parse_date_from_filename(filename: str) -> str | None:
    """Estrae la data dal nome file Teams (M-D-YY) e la converte in AAAA-MM-GG."""
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{2})\.csv$", filename)
    if not m:
        return None
    month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    full_year = 2000 + year
    return f"{full_year:04d}-{month:02d}-{day:02d}"


def _classify(email: str) -> str:
    """Classifica il partecipante in base al dominio email."""
    email = email.lower()
    if "adm.gov.it" in email:
        return "adm"
    if "sogei.it" in email:
        return "sogei"
    return "altro"


def parse_presenze_csv(csv_path: Path) -> dict:
    """
    Legge un CSV presenze Teams e restituisce:
    {
        "titolo": str,
        "data":   str (AAAA-MM-GG, da filename),
        "adm":   [{"nome": str, "email": str, "ruolo_teams": str}, ...],
        "sogei": [{"nome": str, "email": str}, ...],
        "altri": [{"nome": str, "email": str}, ...],
    }
    """
    text = _decode_csv(csv_path)
    lines = text.splitlines()

    result = {
        "titolo": "",
        "data": _parse_date_from_filename(csv_path.name) or "",
        "adm": [],
        "sogei": [],
        "altri": [],
    }

    # Estrae il titolo dalla sezione 1. Riepilogo
    for line in lines:
        if "Titolo" in line or "Titolo riunione" in line:
            parts = line.split("\t")
            if len(parts) >= 2:
                result["titolo"] = parts[1].strip().strip('"')
                break

    # Trova la sezione "2. Partecipanti"
    in_participants = False
    header_seen = False
    seen_names: set[str] = set()

    for line in lines:
        stripped = line.strip()

        # Inizio sezione partecipanti
        if re.match(r"2\.\s*(Partecipanti|Participants)", stripped):
            in_participants = True
            header_seen = False
            continue

        # Fine sezione (inizia sezione 3)
        if in_participants and re.match(r"3\.", stripped):
            break

        if not in_participants:
            continue

        # Salta riga intestazione colonne
        parts = [p.strip() for p in line.split("\t")]
        if not header_seen:
            # La riga intestazione contiene "Nome" o "Name"
            if parts and parts[0].lower() in ("nome", "name"):
                header_seen = True
            continue

        if len(parts) < 2 or not parts[0]:
            continue

        raw_name = parts[0]
        email = parts[4].strip().lower() if len(parts) > 4 else ""
        ruolo_teams = parts[6].strip() if len(parts) > 6 else ""

        nome = _normalize_name(raw_name)

        # Evita duplicati (Teams a volte ripete la stessa persona)
        key = nome.lower()
        if key in seen_names:
            continue
        seen_names.add(key)

        org = _classify(email)
        if org == "adm":
            result["adm"].append({"nome": nome, "email": email, "ruolo_teams": ruolo_teams})
        elif org == "sogei":
            result["sogei"].append({"nome": nome, "email": email})
        else:
            result["altri"].append({"nome": nome, "email": email})

    return result


# ---------------------------------------------------------------------------
# Utility: stampa riepilogo (utile per debug / chiamata diretta)
# ---------------------------------------------------------------------------

def print_summary(csv_path: Path) -> None:
    r = parse_presenze_csv(csv_path)
    print(f"Titolo : {r['titolo']}")
    print(f"Data   : {r['data']}")
    print(f"\nADM ({len(r['adm'])}):")
    for p in r["adm"]:
        print(f"  {p['nome']:<35} {p['email']}")
    print(f"\nSOGEI ({len(r['sogei'])}):")
    for p in r["sogei"]:
        print(f"  {p['nome']:<35} {p['email']}")
    if r["altri"]:
        print(f"\nAltri ({len(r['altri'])}):")
        for p in r["altri"]:
            print(f"  {p['nome']:<35} {p['email']}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python parse_presenze.py <percorso.csv>")
        sys.exit(1)
    print_summary(Path(sys.argv[1]))
