"""Utility condivise per la generazione delle mail di progetto."""
from __future__ import annotations
import re
import sys
from pathlib import Path
from datetime import date, timedelta

VAULT = Path(__file__).parent.parent
ANAGRAFICA = VAULT / "Anagrafica"

sys.path.insert(0, str(Path(__file__).parent))


def parse_frontmatter(source: Path | str) -> dict:
    """Legge il frontmatter YAML di un file .md senza dipendenze esterne.
    Accetta sia un Path al file sia il testo grezzo del file."""
    if isinstance(source, Path):
        text = source.read_text(encoding="utf-8", errors="replace")
    else:
        text = source
    m = re.search(r"^---[ \t]*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def read_release(codice: str) -> tuple[dict, str]:
    """Restituisce (frontmatter, testo completo) della scheda rilascio."""
    md = VAULT / "PO 2026" / codice / f"{codice}.md"
    if not md.exists():
        raise FileNotFoundError(f"Scheda rilascio non trovata: {md}")
    text = md.read_text(encoding="utf-8")
    return parse_frontmatter(md), text


def _anagrafica_by_name(name: str) -> Path | None:
    """Cerca il file Anagrafica per nome esatto o cognome-nome invertito."""
    exact = ANAGRAFICA / f"{name}.md"
    if exact.exists():
        return exact
    parts = name.split()
    if len(parts) >= 2:
        # prova cognome nome → nome cognome
        alt = " ".join(reversed(parts))
        p = ANAGRAFICA / f"{alt}.md"
        if p.exists():
            return p
    return None


def _anagrafica_by_surname(surname: str) -> Path | None:
    """Cerca il primo file Anagrafica il cui nome inizia con il cognome dato."""
    surname_low = surname.lower()
    for f in ANAGRAFICA.glob("*.md"):
        if f.stem.lower().startswith(surname_low):
            return f
    return None


def get_email(name: str) -> str:
    """
    Risolve l'email di una persona.
    Priorità: Anagrafica → derivazione ADM → placeholder.
    """
    # Rimuovi suffissi tra parentesi es. "(referente)", "(ad interim)"
    clean = re.sub(r"\s*\([^)]+\)", "", name).strip()
    if not clean:
        return ""

    # Prova lookup diretto e per cognome
    path = _anagrafica_by_name(clean)
    if path is None:
        # prova con solo il primo token (cognome)
        path = _anagrafica_by_surname(clean.split()[0])

    if path:
        fm = parse_frontmatter(path)
        email = fm.get("email", "").strip()
        if email and "@" in email:
            return email
        org = fm.get("organizzazione", "").upper()
        parts = path.stem.split()
        if len(parts) >= 2:
            # Derivazione ADM: nome.cognome@adm.gov.it
            if org == "ADM":
                # "Vortice Zaccaria" → zaccaria.vortice@adm.gov.it
                # "Isolotto Tiberio" → tiberio.isolotto@adm.gov.it
                cognome = parts[0].lower()
                nomi = [p.lower() for p in parts[1:]]
                return f"{'.'.join(nomi)}.{cognome}@adm.gov.it"
            # Derivazione SOGEI: {iniziale_nome}{cognome}@sogei.it
            if org == "SOGEI":
                # "Foschia Fulgenzio" → fbonifazi@sogei.it
                cognome = parts[0].lower()
                iniziale = parts[1][0].lower()
                return f"{iniziale}{cognome}@sogei.it"

    return f"[email mancante: {clean}]"


def avvisa_email_mancanti(team: dict[str, list[str]]) -> list[str]:
    """Stampa un WARN per ogni persona del team senza email risolvibile (né in Anagrafica né derivabile)
    e ritorna l'elenco "RUOLO Nome". Da chiamare in ogni generatore di mail/convocazioni."""
    mancanti = []
    for ruolo, nomi in team.items():
        for nome in nomi:
            if "[" in get_email(nome):
                mancanti.append(f"{ruolo} {nome}")
                print(f"  WARN: email mancante per {ruolo} {nome} — non sarà tra i destinatari: "
                      "aggiungila in Anagrafica (o a mano in Outlook) e rigenera")
    return mancanti


def team_from_release(text: str) -> dict[str, list[str]]:
    """
    Estrae i nomi dal Team section della scheda rilascio.
    Restituisce {'PM': [...], 'RA': [...], 'RP': [...], 'RB': [...], 'SOGEI': [...]}.
    """
    result: dict[str, list[str]] = {"PM": [], "RA": [], "RP": [], "RB": [], "SOGEI": []}

    # Tabella ADM: | Ruolo | Nome |
    for ruolo_cell, nome_cell in re.findall(
        r"\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|", text
    ):
        ruolo_up = ruolo_cell.upper()
        # Ignora la riga header
        if nome_cell.strip() in ("Nome", "---", ""):
            continue
        for role in ("PM", "RA", "RP", "RB"):
            if f"({role})" in ruolo_up or ruolo_up.startswith(role):
                # RP può essere "Maestrale - Isolotto": cerco i nomi completi
                if " - " in nome_cell or " – " in nome_cell:
                    for cognome in re.split(r"\s*[-–]\s*", nome_cell):
                        cognome = cognome.strip()
                        if cognome:
                            p = _anagrafica_by_surname(cognome)
                            result[role].append(p.stem if p else cognome)
                else:
                    result[role].append(nome_cell.strip())
                break
        # RB: "Referente Business"
        if "REFERENTE BUSINESS" in ruolo_up:
            nome = nome_cell.strip()
            # Potrebbe essere "M. COSTANZO" → cerca per cognome
            parts = nome.split()
            surname = parts[-1].capitalize() if parts else nome
            p = _anagrafica_by_surname(surname)
            result["RB"] = [p.stem if p else nome]

    # Riga SOGEI: **SOGEI:** Quadrante Romualdo (referente), Dirupo Tiberio, ...
    m = re.search(r"\*\*SOGEI:\*\*\s*(.+)", text)
    if m:
        for part in m.group(1).split(","):
            nome = re.sub(r"\s*\([^)]+\)", "", part).strip()
            if nome:
                result["SOGEI"].append(nome)

    # Schede senza tabella Team (generate da build_project_pages / "Nuovo punto di piano"): i ruoli
    # vengono dal frontmatter. La tabella, quando c'è, vince; il frontmatter riempie solo i ruoli vuoti.
    fm = parse_frontmatter(text)
    for role, key in (("PM", "pm"), ("RA", "ra"), ("RP", "rp"), ("RB", "referente_business"), ("SOGEI", "referente_sogei")):
        if not result[role] and fm.get(key, "").strip():
            result[role] = [n.strip() for n in re.split(r"\s*[-–]\s*|\s*,\s*", fm[key]) if n.strip()]

    return result


def participants_from_resoconto(md_path: Path) -> tuple[list[str], list[str]]:
    """
    Legge LISTA PARTECIPANTI da un resoconto .md.
    Restituisce (adm_names, sogei_names).
    """
    text = md_path.read_text(encoding="utf-8")
    adm, sogei = [], []

    # Trova le sezioni ADM e SOGEI
    _SKIP = {"nome", "---", "[da verificare]", ""}

    m_adm = re.search(
        r"\*\*ADM\*\*\s*\n\|.*?\n\|[-| ]+\n((?:\|[^\n]+\n)+)", text, re.DOTALL
    )
    if m_adm:
        for row in re.findall(r"\|([^|\n]+)\|([^|\n]+)\|([^|\n]+)\|", m_adm.group(1)):
            nome = row[2].strip()
            if nome.lower() not in _SKIP and not nome.startswith("["):
                adm.append(nome)

    m_sogei = re.search(
        r"\*\*SOGEI\*\*\s*\n\|.*?\n\|[-| ]+\n((?:\|[^\n]+\n)+)", text, re.DOTALL
    )
    if m_sogei:
        for row in re.findall(r"\|([^|\n]+)\|", m_sogei.group(1)):
            nome = row.strip()
            if nome.lower() not in _SKIP and not nome.startswith("["):
                sogei.append(nome)

    return adm, sogei


def business_days_after(d: date, n: int) -> date:
    """Restituisce la data n giorni lavorativi dopo d (esclude sabato e domenica)."""
    current = d
    added = 0
    while added < n:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def collaudo_resoconto_pronto(md_path: Path) -> bool:
    """Per i resoconti di collaudo: True solo se il collaudo è davvero già
    avvenuto (data_collaudo_effettiva sulla scheda rilascio, non vuota e non
    futura). Evita che un resoconto precompilato in anticipo — per essere
    mostrato e approvato in sede di riunione — finisca tra le bozze da
    inviare prima che il collaudo si sia effettivamente svolto (vedi anche
    build_da_collaudare.py / Da collaudare.md). Per i resoconti non di
    collaudo ritorna sempre True: nessun gate."""
    fm_res = parse_frontmatter(md_path)
    if fm_res.get("tipo_riunione", "").strip().lower() != "collaudo":
        return True
    codice = fm_res.get("codice_rilascio", "").strip() or md_path.parent.name
    scheda = VAULT / "PO 2026" / codice / f"{codice}.md"
    if not scheda.exists():
        return False
    raw = parse_frontmatter(scheda).get("data_collaudo_effettiva", "").strip()
    if not raw:
        return False
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        return False
    return d <= date.today()


def update_frontmatter_keys(md_path: Path, updates: dict) -> None:
    """Aggiorna o aggiunge chiavi nel frontmatter YAML di un .md, preservando il corpo."""
    text = md_path.read_text(encoding="utf-8")
    m = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n?(.*)", text, re.DOTALL)
    if not m:
        return
    raw_block, body = m.group(1), m.group(2)
    lines_out: list[str] = []
    seen: set[str] = set()
    for line in raw_block.splitlines():
        if ":" in line:
            k = line.partition(":")[0].strip()
            if k in updates:
                lines_out.append(f"{k}: {updates[k]}")
                seen.add(k)
            else:
                lines_out.append(line)
        else:
            lines_out.append(line)
    for k, v in updates.items():
        if k not in seen:
            lines_out.append(f"{k}: {v}")
    md_path.write_text(f"---\n{chr(10).join(lines_out)}\n---\n{body}", encoding="utf-8")


def plain_to_html(text: str) -> str:
    """Converte testo plain in HTML con paragrafi Aptos 12pt (stile Outlook ADM)."""
    html_lines = []
    for line in text.splitlines():
        esc = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if esc.strip():
            html_lines.append(
                f'<p style="margin:0;font-family:Aptos,Calibri,sans-serif;'
                f'font-size:12pt;color:rgb(0,0,0);">{esc}</p>'
            )
        else:
            html_lines.append('<p style="margin:0;">&nbsp;</p>')
    return "\n".join(html_lines)


def resolve_recipients(md_path: Path, codice: str) -> list[str]:
    """
    Risolve i destinatari di un resoconto:
    partecipanti dichiarati nel .md + team dalla scheda rilascio (PM/RA/RP/RB/SOGEI).
    Esclude il PM stesso e deduplica.
    """
    fm = parse_frontmatter(md_path)
    pm_name = fm.get("compilato_da", "").strip()
    pm_email = get_email(pm_name) if pm_name else ""

    adm_names, sogei_names = participants_from_resoconto(md_path)
    seen: set[str] = set()
    to_emails: list[str] = []

    def _add(name: str) -> None:
        e = get_email(name)
        if e and e != pm_email and e not in seen:
            seen.add(e)
            to_emails.append(e)

    for name in adm_names + sogei_names:
        _add(name)
    try:
        _, release_text = read_release(codice)
        team = team_from_release(release_text)
        for role in ("PM", "RA", "RP", "RB", "SOGEI"):
            for name in team.get(role, []):
                _add(name)
    except FileNotFoundError:
        pass

    return to_emails


def save_msg(
    subject: str,
    body: str,
    to_emails: list[str],
    save_path: Path,
    *,
    cc_emails: list[str] | None = None,
    attachment_path: Path | list[Path] | None = None,
) -> None:
    """Salva una bozza come .msg (formato nativo Outlook) via COM, con la
    firma istituzionale nel punto giusto: un .eml con X-Unsent, alla riapertura
    nel nuovo Outlook, si vede reinserire la firma automatica/roaming al
    cursore — che di norma finisce a metà messaggio invece che in fondo — ad
    ogni apertura, anche se il corpo la contiene già (doppia firma). Non è
    disattivabile (firma istituzionale imposta centralmente). L'unico modo
    verificato per evitare sia la posizione sbagliata sia il doppione è
    lasciar comporre a Outlook stesso un messaggio vuoto, catturare la SUA
    firma (sempre quella corrente) e anteporle il nostro testo, prima di
    salvare: una volta salvato come .msg e riaperto, Outlook non lo tratta più
    come "nuovo messaggio" e non la reinserisce.
    `attachment_path` può essere un singolo Path o una lista di Path."""
    import time
    import win32com.client

    mail = None
    for attempt in range(3):
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)  # olMailItem
            mail.Display()  # fa comparire (brevemente) la finestra: necessario per far inserire la firma
            signature_html = mail.HTMLBody
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3)  # Outlook occupato (COM "Call was rejected by callee"): riprova

    mail.HTMLBody = (
        "<html><head>"
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
        "</head><body>" + plain_to_html(body) + "</body></html>"
        + signature_html
    )
    mail.Subject = subject
    # Recipients.Add (non .To/.CC come stringa unica): il separatore di elenco
    # di Windows dipende dalla lingua (in italiano è ";", non ","), quindi una
    # stringa con virgole viene letta come UN SOLO destinatario non valido —
    # causa di "destinatario non trovato" all'invio.
    for e in to_emails:
        if "[" not in e:
            mail.Recipients.Add(e).Type = 1  # olTo
    for e in (cc_emails or []):
        if "[" not in e:
            mail.Recipients.Add(e).Type = 2  # olCC
    mail.Recipients.ResolveAll()

    attachments = (attachment_path if isinstance(attachment_path, list)
                   else [attachment_path] if attachment_path else [])
    for att in attachments:
        if not att.exists():
            print(f"    WARN: allegato non trovato — {att.name}")
            continue
        mail.Attachments.Add(str(att.resolve()))

    save_path.parent.mkdir(parents=True, exist_ok=True)
    if save_path.exists():
        save_path.unlink()
    mail.SaveAs(str(save_path.resolve()), 3)  # 3 = olMSG
    mail.Close(1)  # 1 = olDiscard: non lasciarlo come bozza in Drafts


def format_tipo_riunione(tipo: str) -> str:
    """Normalizza il tipo di riunione per il corpo della mail."""
    t = tipo.strip().lower()
    if "startup" in t:
        return "Startup"
    if "prima" in t:
        return "Prima Analisi"
    if "analisi" in t:
        return "Analisi"
    if "sal" in t or "stato avanzamento" in t:
        return "SAL"
    if "collaudo" in t:
        return "Collaudo"
    return tipo.strip()
