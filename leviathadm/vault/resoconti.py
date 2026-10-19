"""Resoconti e Verbali come documenti a sezioni: parse/serialize per sezione, round-trip esatto."""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path

from pydantic import Field

from . import paths as _paths  # noqa: F401  (inserisce scripts/ in sys.path)
from mail_utils import parse_frontmatter  # noqa: E402
from genera_mail_resoconto import format_date_it  # noqa: E402
from update_anagrafica import anagrafica_info  # noqa: E402

from .models import _Base
from .parsers import Blocco, ha_vincoli_normativi, ricomponi, scomponi_body, spezza_sezioni, split_body

TEMPLATE_RIUNIONE_KEYS = ["DATA", "Canale"]
TEMPLATE_RESOCONTO_KEYS = ["COMPILATO DA", "DATA COMPILAZIONE", "Approvato da", "Data approvazione"]
TEMPLATE_OBIETTIVO_KEYS = ["CODICE PROGETTO", "DESCRIZIONE PROGETTO", "CODICE SOTTOPROGETTO",
                           "DESCRIZIONE SOTTOPROGETTO", "CODICE RILASCIO", "DESCRIZIONE RILASCIO",
                           "VINCOLI NORMATIVI", "VARIAZIONE DATE PREVISTE", "VARIAZIONE EFFORT", "PRIVACY"]
SEZIONI_KV = ("RIUNIONE", "RESOCONTO", "OBIETTIVO")
SEZIONI_TESTO = ("OBIETTIVO DELLA RIUNIONE", "ARGOMENTI TRATTATI")
SEZIONI_NOTE = SEZIONI_KV + ("LISTA PARTECIPANTI",) + SEZIONI_TESTO + ("AZIONI CONCORDATE", "ESITO")
_FOOTER_RE = re.compile(r"\n---[ \t]*\n(?:\s*\*[^\n]*\n?)+\s*$")
_KV_ROW_RE = re.compile(r"^\| \*\*(.+?)\*\* \|(?: (.*?))? \|$")
_NOTA_RE = re.compile(r"^\[lista incompleta[^\]]*\]$", re.MULTILINE)
_ORDINE_SIGLE = {"(PM)": 0, "(RA)": 1, "(RP)": 2, "(RB)": 3}


class Partecipante(_Base):
    ruolo: str
    ufficio: str = ""
    nome: str


class Sezione(_Base):
    heading: str
    riga: str
    testa: str
    inner: str
    coda: str
    grezza: bool = False


# ---- tabelle chiave/valore --------------------------------------------------------
def riga_tabella(cells: list[str]) -> str:
    return "|" + "|".join(f" {c} " if c else " " for c in cells) + "|"


def parse_kv(inner: str) -> dict[str, str] | None:
    righe = inner.split("\n")
    if righe[:2] != ["| | |", "|---|---|"]:
        return None
    out: dict[str, str] = {}
    for r in righe[2:]:
        m = _KV_ROW_RE.match(r)
        if m is None:
            return None
        out[m.group(1)] = m.group(2) or ""
    return out


def ser_kv(d: dict[str, str]) -> str:
    return "\n".join(["| | |", "|---|---|"] + [riga_tabella([f"**{k}**", v]) for k, v in d.items()])


def trova(d: dict[str, str], chiave: str) -> str:
    for k, v in d.items():
        if k.upper() == chiave.upper():
            return v
    return ""


# ---- partecipanti -------------------------------------------------------------------
def _celle(riga: str) -> list[str] | None:
    if not (riga.startswith("|") and riga.endswith("|")):
        return None
    return [c.strip() for c in riga[1:-1].split("|")]


def parse_partecipanti(inner: str) -> tuple[list[Partecipante], list[str], str] | None:
    nota = ""
    m = _NOTA_RE.search(inner)
    if m:
        nota = m.group(0)
        inner = inner[: m.start()].rstrip("\n")
    if "**SOGEI**" not in inner or not inner.startswith("**ADM**"):
        return None
    blocco_adm, blocco_sogei = inner.split("**SOGEI**", 1)
    adm: list[Partecipante] = []
    for r in blocco_adm.split("\n"):
        c = _celle(r.strip())
        if c is None or c[0].lower() == "ruolo" or set("".join(c)) <= set("-: "):
            continue
        if len(c) == 3:
            adm.append(Partecipante(ruolo=c[0], ufficio=c[1], nome=c[2]))
        elif len(c) == 2:
            adm.append(Partecipante(ruolo=c[0], ufficio="", nome=c[1]))
        else:
            return None
    sogei: list[str] = []
    for r in blocco_sogei.split("\n"):
        c = _celle(r.strip())
        if c is None or c[0].lower() == "nome" or set("".join(c)) <= set("-: "):
            continue
        if len(c) != 1:
            return None
        sogei.append(c[0])
    return adm, sogei, nota


def ser_partecipanti(adm: list[Partecipante], sogei: list[str], nota: str = "") -> str:
    righe = ["**ADM**", "", "| Ruolo | Ufficio | Nome |", "|-------|---------|------|"]
    righe += [riga_tabella([p.ruolo, p.ufficio, p.nome]) for p in adm]
    righe += ["", "**SOGEI**", "", "| Nome |", "|------|"]
    righe += [riga_tabella([n]) for n in sogei]
    out = "\n".join(righe)
    return out + ("\n\n" + nota if nota else "")


def ordina_adm(adm: list[Partecipante]) -> list[Partecipante]:
    return sorted(adm, key=lambda p: _ORDINE_SIGLE.get(p.ruolo.split(" ")[0], 9))


# ---- azioni ----------------------------------------------------------------------------
def parse_azioni(inner: str) -> list[str] | None:
    if not inner.strip():
        return []
    out: list[str] = []
    for r in inner.split("\n"):
        if r.startswith("- "):
            out.append(r[2:])
        elif r.startswith("  ") and out:
            out[-1] += "\n" + r
        else:
            return None
    return out


def ser_azioni(azioni: list[str]) -> str:
    return "\n".join("- " + a for a in azioni)


# ---- ESITO del collaudo -------------------------------------------------------------------
INTRO_ESITO = ("La verifica si è svolta in contraddittorio tra i rappresentanti di ADM e quelli di Sogei "
               "indicati nella lista partecipanti.\n\nIl collaudo ha avuto lo scopo di verificare:\n\n"
               "- la rispondenza della documentazione fornita da Sogei rispetto a quanto previsto in fase di analisi;\n"
               "- la rispondenza di quanto realizzato rispetto alle funzionalità descritte nel documento di analisi;\n"
               "- la rispondenza degli output del piano di test precedentemente concordato con Sogei rispetto ai valori attesi.\n\n"
               "Sono stati eseguiti i seguenti casi di test, con il relativo esito:")
CHIUSURE = {
    "firma": "I partecipanti forniscono la propria approvazione firmando il resoconto.",
    "telematica": "I partecipanti forniscono la propria approvazione telematicamente.",
    "telematica_in_riunione": ("Il collaudo si intende approvato dai partecipanti presenti, che hanno fornito la "
                               "propria approvazione telematicamente in sede di riunione."),
}
ESITI = ["POSITIVO", "con riserva", "NEGATIVO"]
_RIGA_ESITO_RE = re.compile(r"^Il collaudo ha avuto esito \*\*(.*?)\*\*\.$", re.MULTILINE)
_CASI_INTRO = "Sono stati eseguiti i seguenti casi di test, con il relativo esito:"


class CasoTest(_Base):
    nome: str
    esito: str = ""


class Esito(_Base):
    intro: str = INTRO_ESITO
    casi: list[CasoTest] = Field(default_factory=list)
    osservazioni: str = ""
    esito: str = ""
    chiusura: str = ""


def parse_esito(inner: str) -> Esito | None:
    i = inner.find(_CASI_INTRO)
    m = _RIGA_ESITO_RE.search(inner)
    if i < 0 or m is None or m.start() < i:
        return None
    intro = inner[: i + len(_CASI_INTRO)]
    mezzo = inner[i + len(_CASI_INTRO): m.start()].strip("\n")
    righe = mezzo.split("\n") if mezzo else []
    casi: list[CasoTest] = []
    k = 0
    while k < len(righe) and righe[k].startswith("- "):
        nome, sep, esito = righe[k][2:].rpartition(":")
        casi.append(CasoTest(nome=nome.strip() if sep else righe[k][2:].strip(), esito=esito.strip() if sep else ""))
        k += 1
    osservazioni = "\n".join(righe[k:]).strip("\n")
    chiusura = inner[m.end():].strip("\n")
    return Esito(intro=intro, casi=casi, osservazioni=osservazioni, esito=m.group(1), chiusura=chiusura)


def ser_esito(e: Esito) -> str:
    blocchi = [e.intro]
    if e.casi:
        blocchi.append("\n".join(f"- {c.nome}: {c.esito}".rstrip() for c in e.casi))
    if e.osservazioni:
        blocchi.append(e.osservazioni)
    blocchi.append(f"Il collaudo ha avuto esito **{e.esito}**.")
    if e.chiusura:
        blocchi.append(e.chiusura)
    return "\n\n".join(blocchi)


# ---- Verbale di Collaudo -------------------------------------------------------------------
_RIEPILOGO_RE = re.compile(r"^- \*\*(\d+)\. (.+?)\*\*\n    - \[([ xX])\] Superato\n    - \[([ xX])\] Non superato",
                           re.MULTILINE)
_DETTAGLIO_RE = re.compile(r"^### (\d+)\. (.+?)\s*$", re.MULTILINE)
_CHECK_RE = re.compile(r"- \[([ xX])\] (Superato con riserva|Superato|Non superato)")
_CAMPO_RE = r"\*\*{label}\*\*[ \t]*(.*?)[ \t]*(?=[ \t]*·|\n|$)"   # il valore finisce al '·', a fine riga o a EOF
ESITI_VERBALE = ["Superato", "Superato con riserva", "Non superato"]
MAPPA_ESITO = {"Superato": ("positivo", "POSITIVO"), "Superato con riserva": ("con riserva", "con riserva"),
               "Non superato": ("negativo", "NEGATIVO")}


class Verifica(_Base):
    n: int
    nome: str
    esito: str = ""           # Superato / Non superato / ""
    data: str = ""
    testato_da: str = ""
    note: str = ""


class VerbaleDoc(_Base):
    path: Path
    mtime_ns: int
    frontmatter: dict[str, str]
    fm_raw: str
    intestazione: str          # dal titolo fino a prima di "## Riepilogo verifiche", verbatim
    verifiche: list[Verifica] = Field(default_factory=list)
    esito_complessivo: str = ""
    data_verbale: str = ""
    presenti: str = ""
    riserve: str = ""
    problemi: list[str] = Field(default_factory=list)


def _campo(testo: str, label: str) -> str:
    m = re.search(_CAMPO_RE.format(label=re.escape(label)), testo)
    return m.group(1).strip() if m else ""


def _esito_check(blocco: str) -> str:
    for segno, nome in _CHECK_RE.findall(blocco):
        if segno.lower() == "x":
            return nome
    return ""


def parse_verbale(path: Path, text: str, mtime_ns: int) -> VerbaleDoc:
    corpo = split_body(text)
    fm_raw = text[: len(text) - len(corpo)]
    pre, blocchi = spezza_sezioni(corpo)
    sez = {b.heading: b.body for b in blocchi}
    doc = VerbaleDoc(path=path, mtime_ns=mtime_ns, frontmatter=parse_frontmatter(text), fm_raw=fm_raw,
                     intestazione=pre)
    riepilogo_m = _RIEPILOGO_RE.findall(sez.get("Riepilogo verifiche", ""))
    riepilogo = {int(n): ("Superato" if s.lower() == "x" else "Non superato" if ns.lower() == "x" else "")
                 for n, _, s, ns in riepilogo_m}
    dett = sez.get("Dettaglio verifiche", "")
    ms = list(_DETTAGLIO_RE.finditer(dett))
    for i, m in enumerate(ms):
        blocco = dett[m.end(): ms[i + 1].start() if i + 1 < len(ms) else len(dett)]
        n = int(m.group(1))
        esito = _esito_check(blocco)
        note = blocco.split("**Note / anomalie:**", 1)[1] if "**Note / anomalie:**" in blocco else ""
        note = re.split(r"\n+---[ \t]*\n", note + "\n")[0].strip()   # l'ultima verifica non assorbe il separatore
        doc.verifiche.append(Verifica(n=n, nome=m.group(2), esito=esito, data=_campo(blocco, "Data:"),
                                      testato_da=_campo(blocco, "Testato da:"), note=note))
        if n in riepilogo and riepilogo[n] != esito:
            doc.problemi.append(f"verifica {n}: riepilogo ({riepilogo[n] or 'vuoto'}) ≠ dettaglio "
                                f"({esito or 'vuoto'}), vince il dettaglio")
    if not ms:
        doc.verifiche = [Verifica(n=int(n), nome=nome, esito=riepilogo[int(n)]) for n, nome, _, _ in riepilogo_m]
    fin = sez.get("Esito complessivo", "")
    doc.esito_complessivo = _esito_check(fin)
    doc.data_verbale = _campo(fin, "Data verbale:")
    doc.presenti = _campo(fin, "Presenti:")
    doc.riserve = _campo(fin, "Riserve / azioni correttive:")
    return doc


def _box(cond: bool) -> str:
    return "[x]" if cond else "[ ]"


def sezioni_verbale(doc: VerbaleDoc) -> dict[str, str]:
    """I tre body (dopo la riga heading) riscritti dallo stesso elenco di verifiche."""
    rie: list[str] = []
    for v in doc.verifiche:
        rie += [f"- **{v.n}. {v.nome}**", f"    - {_box(v.esito == 'Superato')} Superato",
                f"    - {_box(v.esito == 'Non superato')} Non superato"]
    det: list[str] = []
    for v in doc.verifiche:
        det += [f"### {v.n}. {v.nome}", "", "**Esito:**", f"- {_box(v.esito == 'Superato')} Superato",
                f"- {_box(v.esito == 'Non superato')} Non superato", "",
                f"**Data:** {v.data}".rstrip() + "  ·  " + f"**Testato da:** {v.testato_da}".rstrip(),
                f"**Note / anomalie:** {v.note}".rstrip(), ""]
    fin = [f"- {_box(doc.esito_complessivo == e)} {e}" for e in ESITI_VERBALE]
    fin += ["", f"**Data verbale:** {doc.data_verbale}".rstrip(), f"**Presenti:** {doc.presenti}".rstrip(),
            f"**Riserve / azioni correttive:** {doc.riserve}".rstrip()]
    return {"Riepilogo verifiche": "\n" + "\n".join(rie) + "\n\n---\n\n",
            "Dettaglio verifiche": "\n" + "\n".join(det).rstrip("\n") + "\n\n---\n\n",
            "Esito complessivo": "\n" + "\n".join(fin) + "\n"}


def ser_verbale(doc: VerbaleDoc) -> str:
    fm = dict(doc.frontmatter)
    fm["esito_collaudo"] = MAPPA_ESITO.get(doc.esito_complessivo, ("", ""))[0]
    fm["aggiornato"] = date.today().isoformat()
    fm_raw = "---\n" + "\n".join(f"{k}: {v}".rstrip() for k, v in fm.items()) + "\n---\n"
    sez = sezioni_verbale(doc)
    return fm_raw + doc.intestazione + "".join(f"## {h}\n{body}" for h, body in sez.items())


def esito_da_verbale(doc: VerbaleDoc) -> str:
    return MAPPA_ESITO.get(doc.esito_complessivo, ("", ""))[1]


def riallinea_esito_da_verbale(esito: Esito, verbale: VerbaleDoc) -> Esito:
    casi = [CasoTest(nome=v.nome, esito=v.esito) for v in verbale.verifiche]
    return esito.model_copy(update={"casi": casi, "esito": esito_da_verbale(verbale) or esito.esito})


# ---- CSV presenze ----------------------------------------------------------------------------
def csv_presenze_per_data(cartella: Path, data_iso: str) -> Path | None:
    """Il CSV presenze Teams di QUELLA data (root e _fonti/, giorno con o senza zero): stessa regola
    degli script. Con data nota find_presenze_csv non ripiega mai su un altro CSV."""
    from parse_presenze import find_presenze_csv
    return find_presenze_csv(cartella, data_iso) if data_iso else None


# ---- scheletro ------------------------------------------------------------------------------
FASI = ["Startup", "Prima Analisi", "SAL", "Collaudo"]
_TITOLI = {"Startup": "STARTUP", "Prima Analisi": "PRIMA ANALISI", "Collaudo": "COLLAUDO"}
_PROT_RE = re.compile(r"^(\S+)\s+del\s+(\d{2}/\d{2}/\d{4})")
NOTA_INCOMPLETA = "[lista incompleta — integrare con report presenze Teams]"
ARGOMENTI_COLLAUDO = (
    "Relativamente al progetto in questione è stato verificato che:\n\n"
    "- Il documento di analisi è stato protocollato in data {da}, sul Registro Contratto Sogei, in ingresso, con n. {na};\n"
    "- L'analisi è stata approvata in data {dp}, sul Registro Ufficiale, in uscita, con nota prot. n. {np};\n"
    "- La disponibilità al collaudo (fine avviamento) è stata protocollata in data {dd}, sul Registro Contratto Sogei, "
    "in ingresso, con n. {nd}.\n\n"
    "Pertanto, il team di progetto procede con l'esecuzione dei test previsti nel documento di analisi.")


def rango_fase(fase: str) -> int | None:
    """Posizione nel ciclo di vita di una fase della tabella Riunioni ("SAL #2", "Analisi", …); None se libera."""
    f = fase.strip().lower()
    if f.startswith("startup"):
        return 0
    if "analisi" in f:
        return 1
    if f.startswith("sal"):
        return 2
    if f.startswith("collaudo"):
        return 3
    return None


def fasi_ammesse(fasi_fatte: list[str]) -> list[str]:
    """Fasi proponibili per la prossima riunione: uguali o successive all'ultima già fatta
    (una fase libera non vincola). Tutte, se non c'è ancora nulla."""
    ranghi = [r for r in map(rango_fase, fasi_fatte) if r is not None]
    return FASI[max(ranghi):] if ranghi else list(FASI)


def etichetta_fase(fase: str, n: int | None = None) -> str:
    return f"SAL {n}" if fase == "SAL" else fase.strip()


def fase_tabella(etichetta: str) -> str:
    return etichetta.replace("SAL ", "SAL #") if etichetta.startswith("SAL ") else etichetta


def _tipo_titolo(etichetta: str) -> str:
    if etichetta.startswith("SAL "):
        return f"STATO AVANZAMENTO LAVORI N.{etichetta[4:]}"
    return _TITOLI.get(etichetta, etichetta.upper())   # fase libera: titolo = etichetta


def titolo_resoconto(codice: str, etichetta: str, data: date) -> str:
    return f"{codice} - RESOCONTO RIUNIONE DI {_tipo_titolo(etichetta)} DEL {data:%d/%m/%Y}"


def nome_file(codice: str, etichetta: str, data: date) -> str:
    return f"{codice} - {data:%Y%m%d} Resoconto {etichetta}.md"


def formula_obiettivo(etichetta: str, data: date, fm: dict) -> str:
    g, sp, ril = format_date_it(data), fm.get("descrizione_sottoprogetto", ""), fm.get("descrizione_rilascio", "")
    if etichetta == "Startup":
        return (f'In data {g} si è svolta la riunione di startup, tenutasi a distanza, tra ADM e Sogei sul tema '
                f'riguardante "{sp}", per verificare la fattibilità di quanto previsto nell\'obiettivo "{ril}".')
    if etichetta == "Prima Analisi":
        return (f'In data {g} si è svolta la prima riunione di analisi, tenutasi a distanza, tra ADM e Sogei sul tema '
                f'riguardante "{sp}", con l\'obiettivo di avviare l\'analisi dei requisiti per il rilascio "{ril}".')
    if etichetta.startswith("SAL "):
        return (f'In data {g} si è svolta la riunione di Stato Avanzamento Lavori n.{etichetta[4:]}, tenutasi a '
                f'distanza, tra ADM e Sogei per verificare l\'avanzamento delle attività relative al rilascio "{ril}".')
    if etichetta == "Collaudo":
        return (f'In data {g} si è svolta la riunione di collaudo, tenutasi a distanza, tra ADM e Sogei sul tema '
                f'riguardante "{sp}", per eseguire la verifica di conformità del rilascio "{ril}".')
    return (f'In data {g} si è svolta la riunione "{etichetta}", tenutasi a distanza, tra ADM e Sogei sul tema '
            f'riguardante "{sp}", relativa al rilascio "{ril}".')


def prossimo_sal(fasi: list[str]) -> int:
    nn = [int(m.group(1)) for f in fasi for m in [re.search(r"SAL\s*#?\s*(\d+)", f)] if m]
    return (max(nn) + 1) if nn else 1


def _ruolo(sigla: str, nome: str, info) -> str:
    i = info(nome) or {}
    parti = [p for p in (i.get("direzione", "").strip(), i.get("ufficio", "").strip()) if p]
    testo = " – ".join(parti)
    return f"({sigla}) {testo}".strip() if sigla else testo


def _stesso(a: str, b: str) -> bool:
    return set(a.lower().split()) == set(b.lower().split())


def _sogei_ordinati(nomi: list[str], fm: dict) -> list[str]:
    ref = fm.get("referente_sogei", "").strip()
    primi = [n for n in nomi if ref and _stesso(n, ref)]
    return primi + [n for n in nomi if n not in primi]


def partecipanti_da_team(fm: dict, team: dict, info=anagrafica_info) -> tuple[list[Partecipante], list[str]]:
    adm = [Partecipante(ruolo=_ruolo(sigla, nome, info), nome=nome)
           for sigla in ("PM", "RA", "RP", "RB") for nome in team.get(sigla, [])]
    return adm, _sogei_ordinati(list(team.get("SOGEI", [])), fm)


def partecipanti_da_presenze(presenze: dict, team: dict, fm: dict,
                             info=anagrafica_info) -> tuple[list[Partecipante], list[str]]:
    adm: list[Partecipante] = []
    for p in presenze.get("adm", []):
        sigla, nome_anag = "", p["nome"]
        for s in ("PM", "RA", "RP", "RB"):
            t = next((t for t in team.get(s, []) if _stesso(p["nome"], t)), None)
            if t is not None:
                sigla, nome_anag = s, t
                break
        adm.append(Partecipante(ruolo=_ruolo(sigla, nome_anag, info), nome=p["nome"]))
    sogei = [p["nome"] for p in presenze.get("sogei", [])]
    return ordina_adm(adm), _sogei_ordinati(sogei, fm)


def _prot(valore: str) -> tuple[str, str]:
    m = _PROT_RE.match(valore.strip())
    return (m.group(2), m.group(1)) if m else ("DA COMPLETARE", "DA COMPLETARE")


def argomenti_collaudo(fm: dict) -> str:
    da, na = _prot(fm.get("protocollo_analisi", ""))
    dp, np_ = _prot(fm.get("protocollo_approvazione_analisi", ""))
    dd, nd = _prot(fm.get("protocollo_disponibilita_collaudo", ""))
    return ARGOMENTI_COLLAUDO.format(da=da, na=na, dp=dp, np=np_, dd=dd, nd=nd)


def _si_no(valore: str) -> str:
    return "SI" if ha_vincoli_normativi(valore) else "NO"


def crea_scheletro(fm: dict, etichetta: str, data: date, *, team: dict, variante: str | None = None,
                   presenze: dict | None = None, verbale: VerbaleDoc | None = None, trascritto: str = "",
                   info=anagrafica_info, oggi: date | None = None) -> str:
    """Testo completo del nuovo resoconto: sezioni fisse compilate, ARGOMENTI/AZIONI vuoti."""
    oggi = oggi or date.today()
    codice = fm.get("codice_rilascio", "")
    collaudo = etichetta == "Collaudo"
    if collaudo and variante not in CHIUSURE:
        raise ValueError("variante di collaudo obbligatoria: firma | telematica | telematica_in_riunione")
    if presenze and (presenze.get("adm") or presenze.get("sogei")):
        adm, sogei = partecipanti_da_presenze(presenze, team, fm, info)
        nota = ""
    else:
        adm, sogei = partecipanti_da_team(fm, team, info)
        nota = NOTA_INCOMPLETA
    riunione = {"DATA": f"{data:%d/%m/%Y}", "Canale": "MICROSOFT TEAMS"}
    resoconto = {"COMPILATO DA": "Astolfo Lunardi", "DATA COMPILAZIONE": f"{oggi:%d/%m/%Y}",
                 "Approvato da": "Partecipanti", "Data approvazione": ""}
    obiettivo = {"CODICE PROGETTO": fm.get("codice_progetto", ""),
                 "DESCRIZIONE PROGETTO": fm.get("descrizione_progetto", ""),
                 "CODICE SOTTOPROGETTO": fm.get("codice_sottoprogetto", ""),
                 "DESCRIZIONE SOTTOPROGETTO": fm.get("descrizione_sottoprogetto", ""),
                 "CODICE RILASCIO": codice, "DESCRIZIONE RILASCIO": fm.get("descrizione_rilascio", ""),
                 "VINCOLI NORMATIVI": _si_no(fm.get("vincoli_normativi", "")), "VARIAZIONE DATE PREVISTE": "NO",
                 "VARIAZIONE EFFORT": "NO", "PRIVACY": _si_no(fm.get("privacy", ""))}
    sezioni = [("RIUNIONE", ser_kv(riunione)), ("RESOCONTO", ser_kv(resoconto)), ("OBIETTIVO", ser_kv(obiettivo)),
               ("LISTA PARTECIPANTI", ser_partecipanti(adm, sogei, nota)),
               ("OBIETTIVO DELLA RIUNIONE", formula_obiettivo(etichetta, data, fm))]
    if collaudo:
        esito = Esito(chiusura=CHIUSURE[variante])
        if verbale is not None:
            esito = riallinea_esito_da_verbale(esito, verbale)
        sezioni += [("ARGOMENTI TRATTATI", argomenti_collaudo(fm)), ("ESITO", ser_esito(esito))]
    else:
        sezioni += [("ARGOMENTI TRATTATI", ""), ("AZIONI CONCORDATE", "")]
    fm_out = [("codice_rilascio", codice), ("tipo_riunione", etichetta), ("data_riunione", data.isoformat()),
              ("data_compilazione", oggi.isoformat()), ("compilato_da", "Astolfo Lunardi"),
              ("approvato_da", "Partecipanti"), ("data_approvazione", ""), ("inviato", "false")]
    testo = "---\n" + "\n".join(f"{k}: {v}".rstrip() for k, v in fm_out) + "\n---\n\n"
    testo += f"# {titolo_resoconto(codice, etichetta, data)}\n\n[[{codice}]]\n\n---\n\n"
    # sezione vuota: due righe vuote (testa "\n\n", inner "", coda "\n---\n\n"); body_di le dà poi la forma standard
    testo += "".join(f"## {h}\n\n{inner}\n\n---\n\n" if inner else f"## {h}\n\n\n---\n\n" for h, inner in sezioni)
    testo += (f"*Generato da trascritto: `{trascritto}`*\n" if trascritto else "") + "*Stato: BOZZA — non ancora inviato*\n"
    return testo


# ---- documento ----------------------------------------------------------------------------
class ResocontoDoc(_Base):
    path: Path
    mtime_ns: int
    frontmatter: dict[str, str]
    fm_raw: str
    pre: str                      # titolo, [[link]], separatore iniziale: verbatim
    sezioni: list[Sezione]
    footer: str = ""              # "\n---\n\n*Generato…*\n*Stato…*\n" (verbatim) o ""
    riunione: dict[str, str] = Field(default_factory=dict)
    resoconto: dict[str, str] = Field(default_factory=dict)
    obiettivo: dict[str, str] = Field(default_factory=dict)
    adm: list[Partecipante] = Field(default_factory=list)
    sogei: list[str] = Field(default_factory=list)
    nota_partecipanti: str = ""
    obiettivo_riunione: str = ""
    argomenti: str = ""
    azioni: list[str] = Field(default_factory=list)
    esito: object | None = None   # Esito (Task 4)
    problemi: list[str] = Field(default_factory=list)

    @property
    def titolo(self) -> str:
        m = re.search(r"^# +(.+?)\s*$", self.pre, re.MULTILINE)
        return m.group(1) if m else self.path.stem

    @property
    def ha_sezioni(self) -> bool:
        return bool(self.sezioni)

    @property
    def is_collaudo(self) -> bool:
        headings = {s.heading for s in self.sezioni}
        return "ESITO" in headings and "AZIONI CONCORDATE" not in headings

    def sezione(self, heading: str) -> Sezione | None:
        return next((s for s in self.sezioni if s.heading == heading), None)

    def body_di(self, heading: str, inner: str) -> str:
        s = self.sezione(heading)
        if s is None:
            return "\n" + inner + "\n"
        ultima = s is self.sezioni[-1]
        testa, coda = s.testa, s.coda
        if s.inner == "":
            # sezione vuota: forma standard "\n{inner}\n\n---\n\n" (o "\n{inner}\n" + footer se è l'ultima)
            testa = "\n"
            if not coda.lstrip("\n").startswith("---"):
                coda = "\n" if (ultima and self.footer) else coda
        return testa + inner + coda + (self.footer if ultima else "")

    def testo(self) -> str:
        blocchi = [Blocco(riga=s.riga, heading=s.heading, body=s.testa + s.inner + s.coda) for s in self.sezioni]
        if blocchi:
            blocchi[-1].body += self.footer
            return self.fm_raw + ricomponi(self.pre, blocchi)
        return self.fm_raw + self.pre + self.footer


_SPAZI_RE = re.compile(r"[ \t]+")


def stessa_forma(a: str, b: str) -> bool:
    """Uguali a meno di sequenze di spazi interne alle righe (vedi _stessa_forma)."""
    return _stessa_forma(a, b)


def _stessa_forma(a: str, b: str) -> bool:
    """Round-trip a meno di sequenze di spazi interne alle righe (es. `Nome  |`): la sezione è
    lossless e resta editabile; se salvata viene normalizzata."""
    return a == b or _SPAZI_RE.sub(" ", a) == _SPAZI_RE.sub(" ", b)


def _parse_sezione(doc: ResocontoDoc, s: Sezione) -> None:
    """Riempie i campi tipizzati; marca grezza se ser(parse(inner)) non ha la stessa forma di inner."""
    h, inner = s.heading, s.inner
    if h in SEZIONI_KV:
        d = parse_kv(inner)
        if d is None or not _stessa_forma(ser_kv(d), inner):
            s.grezza = True
            return
        setattr(doc, {"RIUNIONE": "riunione", "RESOCONTO": "resoconto", "OBIETTIVO": "obiettivo"}[h], d)
    elif h == "LISTA PARTECIPANTI":
        r = parse_partecipanti(inner)
        if r is None or not _stessa_forma(ser_partecipanti(*r), inner):
            s.grezza = True
            return
        doc.adm, doc.sogei, doc.nota_partecipanti = r
    elif h == "OBIETTIVO DELLA RIUNIONE":
        doc.obiettivo_riunione = inner
    elif h == "ARGOMENTI TRATTATI":
        doc.argomenti = inner
    elif h == "AZIONI CONCORDATE":
        a = parse_azioni(inner)
        if a is None or not _stessa_forma(ser_azioni(a), inner):
            s.grezza = True
            return
        doc.azioni = a
    elif h == "ESITO":
        e = parse_esito(inner)
        if e is None or not _stessa_forma(ser_esito(e), inner):
            s.grezza = True
            return
        doc.esito = e


def parse_resoconto_doc(path: Path, text: str, mtime_ns: int) -> ResocontoDoc:
    corpo = split_body(text)
    fm_raw = text[: len(text) - len(corpo)]
    pre, blocchi = spezza_sezioni(corpo)
    footer = ""
    if blocchi:
        m = _FOOTER_RE.search(blocchi[-1].body)
        if m:
            footer = m.group(0)
            blocchi[-1].body = blocchi[-1].body[: m.start()]
    sezioni = []
    for b in blocchi:
        testa, inner, coda = scomponi_body(b.body)
        sezioni.append(Sezione(heading=b.heading, riga=b.riga, testa=testa, inner=inner, coda=coda))
    doc = ResocontoDoc(path=path, mtime_ns=mtime_ns, frontmatter=parse_frontmatter(text), fm_raw=fm_raw,
                       pre=pre, sezioni=sezioni, footer=footer)
    for s in sezioni:
        _parse_sezione(doc, s)
        if s.grezza:
            doc.problemi.append(f"sezione {s.heading} in formato non standard: modificabile solo come testo")
    if not sezioni:
        doc.problemi.append("nessuna sezione ## trovata (export docx2md?): solo lettura come nota")
    return doc
