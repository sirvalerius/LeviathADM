"""
genera_convocazione.py — genera la convocazione (startup o collaudo) di un punto di
piano come una singola .eml che è essa stessa l'invito: l'invito calendario è
incorporato nel messaggio (parte text/calendar; method=REQUEST + allegato
invite.ics), così basta aprire la bozza e premere Invia — nessun .ics separato da
cliccare. Per il collaudo la .eml porta anche il PDF del piano di test e viene
creata la scheda `{codice} - {AAAAMMGG} Verbale di Collaudo.md` da compilare
(riepilogo verifiche + esiti; non sovrascritta se già presente).

Routine riutilizzabile per tutti i punti di piano. I dati meccanici (destinatari,
data proposta, descrizione) sono ricavati dalla scheda `ADMxxx-xx-xX.md`; i dati
curati a mano (elenco verifiche dal Piano di Test, codice documento di analisi,
PDF da allegare) si passano come argomenti.

Uso da codice:
    from genera_convocazione import genera_convocazione_collaudo
    genera_convocazione_collaudo(
        "ADM953-01-0M",
        verifiche=["Visualizzazione ...", "Selezione ...", ...],
        documento_analisi="MG-28-SC-0F",
        attachment=Path("PO 2026/ADM953-01-0M/SOGEI_..._All1.pdf"),
        # data=date(2026,7,13),   # opzionale: se assente, calcolata dalla scadenza
    )

    from genera_convocazione import genera_convocazione_startup
    genera_convocazione_startup(
        "ADM939-07-0U",
        data=date(2026,7,14), ora="10:00",
        alternative=["mercoledì 15/07/2026, ore 11:30", "venerdì 17/07/2026, ore 10:00"],
    )  # → .eml (bozza) + .ics; nessun allegato, destinatari dai ruoli della scheda

Regola data proposta: preferibilmente 15gg prima della scadenza (per margine),
10gg se 15 è troppo a ridosso di oggi; sempre giorno lavorativo (weekend → venerdì).
Scadenza = data_disponibilita_collaudo (frontmatter) + 20gg.

Selftest della logica data:  python scripts/genera_convocazione.py selftest
"""
from __future__ import annotations

import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mail_utils import (  # noqa: E402
    avvisa_email_mancanti,
    get_email,
    parse_frontmatter,
    plain_to_html,
    read_release,
    team_from_release,
    update_frontmatter_keys,
)

VAULT = Path(__file__).parent.parent
TEMPLATE = VAULT / "Template" / "Template - Mail di convocazione Collaudo.txt"
TEMPLATE_STARTUP = VAULT / "Template" / "Template - Mail di invito startup.txt"

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


# ── regola data proposta ─────────────────────────────────────────────────────

def propose_collaudo_date(deadline: date, today: date, min_gap: int = 3) -> date:
    """Data collaudo proposta: 15gg prima della scadenza se non troppo a ridosso
    di oggi (gap >= min_gap), altrimenti 10gg prima; sempre giorno lavorativo
    (se cade sab/dom torna al venerdì precedente)."""
    cand = None
    for offset in (15, 10):
        c = deadline - timedelta(days=offset)
        if (c - today).days >= min_gap:
            cand = c
            break
    if cand is None:
        cand = deadline - timedelta(days=10)
    while cand.weekday() >= 5:
        cand -= timedelta(days=1)
    return cand


def _check_ora(ora: str) -> None:
    """Le convocazioni non devono mai iniziare nella pausa pranzo (12:30–14:00)."""
    hh, mm = (int(x) for x in ora.split(":"))
    if 12 * 60 + 30 <= hh * 60 + mm < 14 * 60:
        raise ValueError(
            f"Orario {ora} non ammesso: non convocare riunioni tra le 12:30 e le 14:00 "
            "(pausa pranzo). Scegli un orario fuori da questa fascia.")


def _parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def organizer_default() -> str:
    """Mittente e ORGANIZER dell'invito: l'email del `pm` della dashboard `PO 2026.md` (come la versione web).
    ValueError se la dashboard o l'email in Anagrafica mancano: si passa organizer=... esplicito."""
    dash = VAULT / "PO 2026.md"
    pm = parse_frontmatter(dash).get("pm", "").strip() if dash.exists() else ""
    em = get_email(pm) if pm else ""
    if not em or "[" in em:
        raise ValueError("organizzatore non risolvibile: manca `pm` in PO 2026.md o la sua email in Anagrafica — indica l'organizzatore")
    return em


def _data_nel_nome(p: Path, codice: str) -> date | None:
    m = re.search(r"(\d{4})(\d{2})(\d{2})", p.name[len(codice):])
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    except ValueError:
        return None


def riallinea_cambio_data(out_dir: Path, codice: str, fm: dict, data: date, oggi: date | None = None) -> dict:
    """Cambio di data del collaudo (regola della web 1.2.0): la bozza `<codice> - <AAAAMMGG> Convocazione Collaudo.eml`
    con un'altra data ancora nella root viene eliminata e il Verbale con un'altra data viene rinominato alla nuova
    (data_collaudo, aggiornato, riga "Data collaudo" dell'intestazione; esiti spuntati conservati) — salvo collaudo
    già svolto: esito_collaudo compilato, data precedente a oggi, o data_collaudo_effettiva nella scheda.
    Ritorna {"bozza_eliminata": nome | None, "verbale_rinominato": nome | None}."""
    oggi = oggi or date.today()
    effettiva = _parse_date(fm.get("data_collaudo_effettiva", ""))
    svolto = lambda d: effettiva is not None or (d is not None and d < oggi)   # noqa: E731
    out = {"bozza_eliminata": None, "verbale_rinominato": None}
    nuovo_eml = f"{codice} - {data:%Y%m%d} Convocazione Collaudo.eml"
    for p in sorted(out_dir.glob(f"{codice} - ???????? Convocazione Collaudo.eml")):
        d = _data_nel_nome(p, codice)
        if p.name == nuovo_eml or d is None or svolto(d):
            continue
        p.unlink()
        out["bozza_eliminata"] = p.name
    nuovo_v = out_dir / f"{codice} - {data:%Y%m%d} Verbale di Collaudo.md"
    if nuovo_v.exists():
        return out
    candidati = []
    for p in sorted(out_dir.glob(f"{codice} - ???????? Verbale di Collaudo.md")):
        vfm = parse_frontmatter(p)
        if (vfm.get("esito_collaudo", "") or "").strip():
            continue
        d = _parse_date(vfm.get("data_collaudo", "")) or _data_nel_nome(p, codice)
        if d is None or svolto(d):
            continue
        candidati.append(p)
    if candidati:
        vecchio = candidati[-1]
        testo = vecchio.read_text(encoding="utf-8")
        testo = re.sub(r"^(> Documento di analisi: .*Data collaudo: \*\*)\d{2}/\d{2}/\d{4}(\*\*)", lambda m: f"{m.group(1)}{data:%d/%m/%Y}{m.group(2)}", testo, flags=re.M)
        nuovo_v.write_text(testo, encoding="utf-8")
        update_frontmatter_keys(nuovo_v, {"data_collaudo": data.isoformat(), "aggiornato": oggi.isoformat()})
        vecchio.unlink()
        out["verbale_rinominato"] = vecchio.name
    return out


def _fmt_giorno(d: date) -> str:
    return f"{GIORNI[d.weekday()]} {d.day:02d}/{d.month:02d}/{d.year}"


# ── destinatari dalla scheda ─────────────────────────────────────────────────

def _recipients(codice: str) -> tuple[str, list[str]]:
    """(To, Cc) dai ruoli della scheda: To = RA (o referente business), Cc = resto.
    Esclude il PM (mittente)."""
    _, text = read_release(codice)
    team = team_from_release(text)
    avvisa_email_mancanti(team)
    pm_emails = {get_email(n) for n in team.get("PM", [])}

    def emails(role: str) -> list[str]:
        return [get_email(n) for n in team.get(role, [])]

    to_pool = emails("RA") or emails("RB")
    to = next((e for e in to_pool if "[" not in e and e not in pm_emails), "")

    cc: list[str] = []
    for role in ("RA", "RP", "RB", "SOGEI"):
        for e in emails(role):
            if "[" in e or e in pm_emails or e == to or e in cc:
                continue
            cc.append(e)
    return to, cc


# ── corpo dal template ───────────────────────────────────────────────────────

def _build_body(codice: str, descrizione: str, d: date, ora: str,
                documento_analisi: str, verifiche: list[str]) -> str:
    t = TEMPLATE.read_text(encoding="utf-8").rstrip("\n")
    t = t.replace("ADMXXX-XX-XX", codice)
    t = re.sub(r'"x+"', f'"{descrizione}"', t)
    t = re.sub(r"il giorno .+? alle ore [\d:]+",
               f"il giorno {_fmt_giorno(d)} alle ore {ora}", t)
    t = t.replace("[XX-XX-XX-XX]", documento_analisi)
    t = re.sub(r"\[Sommario.*?\]",
               "\n".join(f"- {v.rstrip(';.')};" for v in verifiche).rstrip(";") + ".",
               t)
    return t


# ── .ics ─────────────────────────────────────────────────────────────────────

def _ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_fold(line: str) -> str:
    """RFC 5545: righe > 75 ottetti vanno spezzate; le continuazioni iniziano
    con uno spazio. Si spezza su confine di carattere (mai a metà di un UTF-8)."""
    out, cur, cur_len = [], "", 0
    for ch in line:
        b = len(ch.encode("utf-8"))
        if cur_len + b > 73:                 # margine sotto i 75 ottetti
            out.append(cur)
            cur, cur_len = " " + ch, 1 + b   # continuazione: spazio iniziale
        else:
            cur += ch
            cur_len += b
    out.append(cur)
    return "\r\n".join(out)


def _build_ics(codice: str, descrizione: str, d: date, ora: str,
               body: str, organizer: str, to: str, cc: list[str],
               tipo: str = "collaudo", durata_min: int = 60) -> bytes:
    hh, mm = (int(x) for x in ora.split(":"))
    start_dt = datetime(d.year, d.month, d.day, hh, mm)
    end_dt = start_dt + timedelta(minutes=durata_min)
    start = start_dt.strftime("%Y%m%dT%H%M%S")
    end = end_dt.strftime("%Y%m%dT%H%M%S")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "PRODID:-//PO 2026//Convocazione//IT",
        "VERSION:2.0", "METHOD:REQUEST", "CALSCALE:GREGORIAN",
        "BEGIN:VTIMEZONE", "TZID:Europe/Rome",
        "BEGIN:DAYLIGHT", "TZOFFSETFROM:+0100", "TZOFFSETTO:+0200", "TZNAME:CEST",
        "DTSTART:19700329T020000", "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU", "END:DAYLIGHT",
        "BEGIN:STANDARD", "TZOFFSETFROM:+0200", "TZOFFSETTO:+0100", "TZNAME:CET",
        "DTSTART:19701025T030000", "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU", "END:STANDARD",
        "END:VTIMEZONE",
        "BEGIN:VEVENT", f"UID:{uuid.uuid4()}@adm.gov.it", f"DTSTAMP:{stamp}",
        f"DTSTART;TZID=Europe/Rome:{start}", f"DTEND;TZID=Europe/Rome:{end}",
        f"SUMMARY:{_ics_escape(f'[{codice}] Riunione di {tipo} - {descrizione}')}",
        "LOCATION:Microsoft Teams", f"DESCRIPTION:{_ics_escape(body)}",
        f"ORGANIZER:mailto:{organizer}",
    ]
    for em in ([to] + cc):
        if em and "[" not in em:
            lines.append(f"ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{em}")
    lines += ["STATUS:CONFIRMED", "SEQUENCE:0", "TRANSP:OPAQUE", "END:VEVENT", "END:VCALENDAR"]
    return ("\r\n".join(_ics_fold(ln) for ln in lines) + "\r\n").encode("utf-8")


# ── .eml ─────────────────────────────────────────────────────────────────────

def _build_eml_bytes(subject: str, body: str, organizer: str, to: str,
                     cc: list[str], *, attachment: Path | None = None,
                     attachment_name: str | None = None,
                     calendar: bytes | None = None) -> bytes:
    """Bozza .eml (X-Unsent) con corpo testo+html. Se `calendar` è fornito, la
    mail diventa essa stessa una convocazione: incorpora l'invito come parte
    `text/calendar; method=REQUEST` (ultima alternativa, preferita da Outlook) e
    allega `invite.ics`. Se `attachment` è fornito, allega il PDF."""
    msg = MIMEMultipart("mixed")
    msg["X-Unsent"] = "1"
    msg["Subject"] = subject
    msg["From"] = organizer
    msg["To"] = to
    if cc:
        msg["Cc"] = ", ".join(cc)
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body, "plain", "utf-8"))
    alt.attach(MIMEText("<html><body>" + plain_to_html(body) + "</body></html>", "html", "utf-8"))
    if calendar:
        cal = MIMEText(calendar.decode("utf-8"), "calendar", "utf-8")
        cal.set_param("method", "REQUEST")
        cal.set_param("component", "VEVENT")
        alt.attach(cal)  # ultima alternativa = quella preferita dai client
    msg.attach(alt)
    if attachment and Path(attachment).exists():
        part = MIMEApplication(Path(attachment).read_bytes(), "pdf")
        part.add_header("Content-Disposition", "attachment",
                        filename=attachment_name or Path(attachment).name)
        msg.attach(part)
    elif attachment:
        print(f"  WARN: allegato non trovato — {attachment}")
    if calendar:
        ics_att = MIMEApplication(calendar, "ics")
        ics_att.add_header("Content-Disposition", "attachment", filename="invite.ics")
        msg.attach(ics_att)
    return msg.as_bytes()


# ── pagina di collaudo (da compilare durante il collaudo) ────────────────────

def genera_pagina_collaudo(
    codice: str,
    verifiche: list[str],
    documento_analisi: str,
    data: date,
    out_dir: Path | None = None,
) -> Path:
    """Genera la scheda di collaudo compilabile `{codice} - {AAAAMMGG} Verbale di
    Collaudo.md` a partire dall'elenco verifiche. Non sovrascrive se già presente
    (per non perdere esiti già compilati)."""
    out_dir = out_dir or (VAULT / "PO 2026" / codice)
    fm, _ = read_release(codice)
    descrizione = fm.get("descrizione_rilascio", codice)
    path = out_dir / f"{codice} - {data:%Y%m%d} Verbale di Collaudo.md"
    if path.exists():
        print(f"  Verbale di collaudo già presente, non sovrascritto: {path.name}")
        return path

    L: list[str] = [
        "---",
        f"codice_rilascio: {codice}",
        "tipo: verbale_collaudo",
        f"documento_analisi: {documento_analisi}",
        f"data_collaudo: {data.isoformat()}",
        f"aggiornato: {date.today().isoformat()}",
        "esito_collaudo:",
        "---",
        "",
        f"# {codice} — Verbale di Collaudo",
        "",
        f"[[{codice}]]",
        "",
        f"> Rilascio: **{descrizione}**",
        f"> Documento di analisi: **{documento_analisi}** · Data collaudo: **{data.day:02d}/{data.month:02d}/{data.year}**",
        "> Spunta l'esito di ciascuna verifica: le caselle in elenco sono cliccabili in Obsidian.",
        "",
        "---",
        "",
        "## Riepilogo verifiche",
        "",
    ]
    for i, v in enumerate(verifiche, 1):
        L += [
            f"- **{i}. {v.rstrip(';. ')}**",
            "    - [ ] Superato",
            "    - [ ] Non superato",
        ]
    L += ["", "---", "", "## Dettaglio verifiche", ""]
    for i, v in enumerate(verifiche, 1):
        L += [
            f"### {i}. {v.rstrip(';. ')}",
            "",
            "**Esito:**",
            "- [ ] Superato",
            "- [ ] Non superato",
            "",
            "**Data:**   ·  **Testato da:**",
            "**Note / anomalie:**",
            "",
        ]
    L += [
        "---",
        "",
        "## Esito complessivo",
        "",
        "- [ ] Superato",
        "- [ ] Superato con riserva",
        "- [ ] Non superato",
        "",
        "**Data verbale:**",
        "**Presenti:**",
        "**Riserve / azioni correttive:**",
        "",
    ]
    path.write_text("\n".join(L), encoding="utf-8")
    return path


# ── entry point ──────────────────────────────────────────────────────────────

def genera_convocazione_collaudo(
    codice: str,
    verifiche: list[str],
    documento_analisi: str,
    attachment: Path,
    *,
    data: date | None = None,
    ora: str = "10:00",
    durata_min: int = 60,
    organizer: str | None = None,
    out_dir: Path | None = None,
) -> dict:
    """Genera la convocazione collaudo: una .eml che è essa stessa l'invito
    (invito calendario incorporato come parte text/calendar; method=REQUEST +
    allegato invite.ics), col PDF del piano di test, e la scheda Verbale di
    Collaudo. Basta aprire la .eml e inviarla.
    Ritorna {"eml": Path, "verbale": Path, "data": date, "to": str, "cc": [...]}"""
    _check_ora(ora)
    fm, _ = read_release(codice)
    descrizione = fm.get("descrizione_rilascio", codice)

    if data is None:
        disp = _parse_date(fm.get("data_disponibilita_collaudo", ""))
        if disp is None:
            raise ValueError(
                f"{codice}: data non fornita e 'data_disponibilita_collaudo' assente nella scheda — "
                "passa data=... o popola il frontmatter.")
        data = propose_collaudo_date(disp + timedelta(days=20), date.today())

    organizer = organizer or organizer_default()
    to, cc = _recipients(codice)
    body = _build_body(codice, descrizione, data, ora, documento_analisi, verifiche)
    out_dir = out_dir or (VAULT / "PO 2026" / codice)
    riallineo = riallinea_cambio_data(out_dir, codice, fm, data)
    stem = f"{codice} - {data:%Y%m%d} Convocazione Collaudo"

    # .eml = convocazione stessa (invito calendario incorporato) + PDF allegato
    cal = _build_ics(codice, descrizione, data, ora, body, organizer, to, cc,
                     tipo="collaudo", durata_min=durata_min)
    eml_path = out_dir / f"{stem}.eml"
    eml_path.write_bytes(_build_eml_bytes(
        f"[{codice}] Convocazione riunione di collaudo — {descrizione}",
        body, organizer, to, cc, calendar=cal,
        attachment=attachment, attachment_name=f"{documento_analisi} - Piano di Test.pdf"))

    # scheda di collaudo da compilare durante il collaudo
    verbale_path = genera_pagina_collaudo(codice, verifiche, documento_analisi, data, out_dir)

    return {"eml": eml_path, "verbale": verbale_path,
            "data": data, "to": to, "cc": cc, **riallineo}


def _build_body_startup(codice: str, fm: dict, d: date, ora: str,
                        alternative: list[str]) -> str:
    t = TEMPLATE_STARTUP.read_text(encoding="utf-8").rstrip("\n")
    cod_sotto = fm.get("codice_sottoprogetto", "")
    desc_sotto = fm.get("descrizione_sottoprogetto", "")
    desc_ril = fm.get("descrizione_rilascio", codice)
    t = t.replace("ADMXXX-XX <Descrizione Sottoprogetto>", f"{cod_sotto} {desc_sotto}".strip())
    t = t.replace("ADMXXX-XX-XX <Descrizione rilascio>.",
                  f"{codice} {desc_ril}, proposta per il giorno {_fmt_giorno(d)} alle ore {ora}.", 1)
    t = t.replace("ADMXXX-XX-XX <Descrizione rilascio>", f"{codice} {desc_ril}")
    if alternative:
        out, alt_iter = [], iter(alternative)
        for ln in t.splitlines():
            if ln.strip().startswith("•") and "xxx" in ln:
                nxt = next(alt_iter, None)
                if nxt is not None:
                    out.append(re.sub("xxx", nxt, ln, count=1))
                # bullet in eccesso: rimosso
            else:
                out.append(ln)
        t = "\n".join(out)
    return t


def genera_convocazione_startup(
    codice: str,
    data: date,
    *,
    alternative: list[str] | None = None,
    ora: str = "10:00",
    durata_min: int = 30,
    organizer: str | None = None,
    out_dir: Path | None = None,
) -> dict:
    """Genera la convocazione della riunione di startup come una .eml che è essa
    stessa l'invito: invito calendario incorporato (text/calendar; method=REQUEST
    + allegato invite.ics). Basta aprire la .eml e inviarla. Slot di default 30 min.
    `data`/`ora`: data e ora proposte; `alternative`: date alternative già
    formattate (testo) per il corpo. Destinatari dai ruoli della scheda.
    Ritorna {"eml": Path, "data": date, "to": str, "cc": [...]}"""
    _check_ora(ora)
    organizer = organizer or organizer_default()
    fm, _ = read_release(codice)
    descrizione = fm.get("descrizione_rilascio", codice)
    to, cc = _recipients(codice)
    # Alla startup la riga SOGEI della scheda è spesso ancora "[da completare]":
    # includo il referente SOGEI dal frontmatter, se l'email è nota.
    sogei = fm.get("referente_sogei", "").strip()
    if sogei:
        em = get_email(sogei)
        if "[" not in em and em != to and em not in cc:
            cc.append(em)
    body = _build_body_startup(codice, fm, data, ora, alternative or [])
    out_dir = out_dir or (VAULT / "PO 2026" / codice)
    stem = f"{codice} - {data:%Y%m%d} Convocazione Startup"

    cal = _build_ics(codice, descrizione, data, ora, body, organizer, to, cc,
                     tipo="startup", durata_min=durata_min)
    eml_path = out_dir / f"{stem}.eml"
    eml_path.write_bytes(_build_eml_bytes(
        f"[{codice}] Convocazione riunione di startup — {descrizione}",
        body, organizer, to, cc, calendar=cal))

    return {"eml": eml_path, "data": data, "to": to, "cc": cc}


def _selftest() -> None:
    # 15gg prima non a ridosso di oggi → usa 15gg (giorno lavorativo)
    assert propose_collaudo_date(date(2026, 8, 31), date(2026, 8, 1)) == date(2026, 8, 14), "15gg"
    # 15gg cade oggi (troppo vicino) → ripiega su 10gg = lun 13/07
    assert propose_collaudo_date(date(2026, 7, 23), date(2026, 7, 8)) == date(2026, 7, 13), "10gg fallback"
    # risultato nel weekend → torna al venerdì
    r = propose_collaudo_date(date(2026, 8, 30), date(2026, 8, 1))  # -15 = 15/08 sab → ven 14/08
    assert r.weekday() < 5, "giorno lavorativo"
    print("selftest OK")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        _selftest()
    else:
        print(__doc__)
