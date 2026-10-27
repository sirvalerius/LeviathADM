"""crea_pack_demo.py — pack distribuibile di LeviathADM (versione Python + LeviathADM Web) con un vault
"PO 2026" demo interamente inventato, isolato dai dati reali.

  python scripts/crea_pack_demo.py [--dest DIR] [--senza-python]

- copia solo codice e template (leviathadm/ senza test, scripts/*.py, leviathadm.html, SCHEMA.md,
  requirements.txt senza pytest, Template/ senza video/firma/eml); machines.json senza hostname;
- genera con i generatori veri del progetto (crea_persona, crea_rilascio, crea_scheletro, archivia_bozza,
  genera_convocazione, build_*) un'Anagrafica fittizia e 10 rilasci immaginari in tutti gli stati;
- scarica Python 3.12 embedded in python/ con le dipendenze (--senza-python per saltare);
- produce <dest> (ricreata) e <dest>.zip accanto. Default: cartella sorella del vault, LeviathADM-demo.
Nulla del vault reale viene letto o copiato: nessuna scheda, Anagrafica, _risorse, .obsidian, docs, git.
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
PY_VER = "3.12.10"
PY_URL = f"https://www.python.org/ftp/python/{PY_VER}/python-{PY_VER}-embed-amd64.zip"
GETPIP_URL = "https://bootstrap.pypa.io/get-pip.py"
MARKER = "README-DEMO.md"

PM = "Lunardi Astolfo"
PM_ESTESO = "Astolfo Lunardi"
DIREZIONI = {  # sigla: (nome ufficiale, uffici)
    "DTDR": ("Direzione Tecnologie dei Dirigibili", ["ATTUAZIONE PROGETTI ONIRICI", "ANALISI E ARCHITETTURE AEROSTATICHE",
                                                      "SVILUPPO SISTEMI DI NAVIGAZIONE"]),
    "DGLL": ("Direzione Giochi e Lotterie Lunari", ["LOTTERIE LUNARI"]),
    "DDOC": ("Direzione Dogane dei Cieli", ["DIRIGIBILI E AEROSTATI", "SIGILLI E CONCESSIONI MARITTIME"]),
    "DACV": ("Direzione Accise sul Vapore", ["ACCISE SUL VAPORE", "ALCHIMIA E TABACCHI"]),
}
PERSONE_ADM = [  # nome, direzione, ufficio, ruolo tipico
    (PM, "DTDR", "ATTUAZIONE PROGETTI ONIRICI", "PM"),
    ("Vaporetti Clelia", "DTDR", "ANALISI E ARCHITETTURE AEROSTATICHE", "RA"),
    ("Mongolfieri Ruggero", "DTDR", "ANALISI E ARCHITETTURE AEROSTATICHE", "RA"),
    ("Lanterna Costanza", "DTDR", "ANALISI E ARCHITETTURE AEROSTATICHE", "RA"),
    ("Sestante Ottavia", "DTDR", "SVILUPPO SISTEMI DI NAVIGAZIONE", "RP"),
    ("Zefiro Baldassarre", "DTDR", "SVILUPPO SISTEMI DI NAVIGAZIONE", "RP"),
    ("Alambicco Ildebrando", "DTDR", "SVILUPPO SISTEMI DI NAVIGAZIONE", "RP"),
    ("Bussola Ermenegilda", "DGLL", "LOTTERIE LUNARI", "RB"),
    ("Ancora Teodorico", "DDOC", "DIRIGIBILI E AEROSTATI", "RB"),
    ("Faro Ginevra", "DDOC", "SIGILLI E CONCESSIONI MARITTIME", "RB"),
    ("Dirigibile Anselmo", "DACV", "ACCISE SUL VAPORE", "RB"),
    ("Timone Gualtiero", "DACV", "ALCHIMIA E TABACCHI", "RB"),
]
PERSONE_SOGEI = ["Nebulosa Corrado", "Quasar Ludovica", "Meteora Isidoro", "Cometa Fiorenza", "Pulsar Tancredi",
                 "Aurora Domitilla", "Eclisse Raimondo", "Orbita Serafina", "Stellare Bonifacio", "Galassia Petronilla"]
AREE = {"Giochi Lunari": ["ADM901"], "Dogane dei Cieli": ["ADM902", "ADM905"], "Accise sul Vapore": ["ADM903", "ADM904"]}
PROGETTI = {"ADM901": "LOTTERIE LUNARI", "ADM902": "DOGANE DEI CIELI", "ADM903": "ALCHIMIA E TABACCHI",
            "ADM904": "ACCISE SUL VAPORE", "ADM905": "CONCESSIONI MARITTIME"}
SOTTOPROGETTI = {"ADM901-01": "Portale Lotterie Lunari", "ADM902-01": "Registro Dazi sui Dirigibili",
                 "ADM902-02": "Sportello Telematico Zeppelin", "ADM902-03": "Verifica Automatica Sigilli Doganali",
                 "ADM903-01": "Anagrafe Alchimisti Autorizzati", "ADM903-02": "Tracciabilità Tabacchi di Atlantide",
                 "ADM904-01": "Cruscotto Accise sul Vapore", "ADM904-02": "Monitoraggio Scommesse sulle Regate",
                 "ADM905-01": "Archivio Concessioni Marittime"}
VERIFICHE = ["Lettura automatica del sigillo all'attracco del dirigibile", "Segnalazione dei sigilli manomessi",
             "Registro storico delle verifiche per matricola"]


def email(nome: str, org: str = "adm") -> str:
    cognome, nome_proprio = nome.split(" ", 1)
    return f"{nome_proprio.lower()}.{cognome.lower()}@{org}.demo.invalid"


def lavorativo(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def it(d: date) -> str:
    return f"{d:%d/%m/%Y}"


def mt(p: Path) -> int:
    return p.stat().st_mtime_ns


# ── copia del codice ───────────────────────────────────────────────────────────────────────
def copia_codice(dest: Path) -> None:
    shutil.copytree(REPO / "leviathadm", dest / "leviathadm",
                    ignore=shutil.ignore_patterns("tests", "__pycache__", "*.pyc", "PRODUCT.md"))
    (dest / "scripts").mkdir()
    for p in (REPO / "scripts").glob("*.py"):
        shutil.copy2(p, dest / "scripts" / p.name)
    for nome in STUB:   # la casella Outlook reale non si tocca mai dal pack
        (dest / "scripts" / nome).write_text(
            f'"""{nome}: non disponibile nel pack demo (niente git/Outlook)."""\nimport sys\n'
            f'sys.exit("{nome} non e\' disponibile nel pack demo")\n', encoding="utf-8")
    for nome in ("leviathadm.html", "SCHEMA.md"):
        shutil.copy2(REPO / nome, dest / nome)
    req = [r for r in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines() if not r.startswith("pytest")]
    (dest / "requirements.txt").write_text("\n".join(req) + "\n", encoding="utf-8")
    (dest / "Template").mkdir()
    for p in (REPO / "Template").iterdir():
        if p.suffix in (".docx", ".txt", ".md") and "Tabella profili" not in p.name:
            shutil.copy2(p, dest / "Template" / p.name)
    shutil.copytree(REPO / "Template" / "markdown", dest / "Template" / "markdown")
    shutil.copytree(REPO / "Template" / "copilot", dest / "Template" / "copilot")   # 2.0: prompt e istruzioni dell'agente Copilot
    (dest / "scripts" / "machines.json").write_text(
        json.dumps({"default_role": "slave", "machines": {}}, indent=2) + "\n", encoding="utf-8")
    (dest / "avvia_demo.py").write_text(AVVIA_DEMO, encoding="utf-8")
    (dest / "leviathadm.cmd").write_text(CMD_DEMO, encoding="utf-8", newline="\r\n")
    (dest / MARKER).write_text(README, encoding="utf-8")


AVVIA_DEMO = '''"""Avvio della demo con il Python embedded in python/ (nessun venv). Mai reload=True."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
p = argparse.ArgumentParser()
p.add_argument("--porta", type=int, default=8080)
p.add_argument("--attendi-porta", action="store_true")   # usato da "Riavvia backend" dell'app
a, _ = p.parse_known_args()
if a.attendi_porta:   # il vecchio server si spegne dopo il lancio: aspetto (max 30 s) che liberi la porta
    import socket
    import time
    for _ in range(60):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", a.porta)) != 0:
                break
        time.sleep(0.5)
from leviathadm.ui import app  # noqa: E402

app.RUN_KWARGS["port"] = a.porta
print(f"LeviathADM demo su http://127.0.0.1:{a.porta} (Ctrl+C per fermare)")
app.main()
'''

CMD_DEMO = """@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM LeviathADM demo: python\\python.exe (embedded) senza venv.  leviathadm.cmd [--porta N]
REM -s: ignora i pacchetti utente (%APPDATA%\\Python) di un altro Python 3.12 presente sul PC
if exist python\\python.exe (
    python\\python.exe -s avvia_demo.py %*
) else (
    echo python\\ assente: serve un Python 3.12 con i pacchetti di requirements.txt
    python avvia_demo.py %*
)
if errorlevel 1 pause
"""
STUB = ("audit_invii.py", "organizza_cartelle_progetti.py")   # sync.py resta: senza git fa il ricalcolo locale

README = """# LeviathADM — pack demo

Pacchetto dimostrativo di **LeviathADM** con un vault "PO 2026" interamente **inventato**: persone, uffici,
progetti e rilasci sono fittizi (lotterie lunari, dazi sui dirigibili, accise sul vapore…). Nessun dato reale.

## Versione Python (dashboard locale)

1. doppio clic su `leviathadm.cmd` (usa il Python embedded in `python/`, nessuna installazione);
2. apri http://127.0.0.1:8080 nel browser (`leviathadm.cmd --porta 8090` per un'altra porta).

Il PC è configurato come **slave** (`scripts/machines.json`): le viste e le scritture funzionano tutte;
le azioni che richiedono Word (PDF) o pandoc restano disabilitate se i programmi mancano. Il pack non è un
repository git: il pulsante **Sync** fa solo il ricalcolo locale (pagine, Bozze da inviare, archiviazione,
`.msg` mancanti se c'è Outlook) senza pull né push. **Audit invii e organizzazione delle cartelle Outlook
sono sostituiti da segnaposto** che escono subito: il pack non deve mai toccare una casella di posta reale.

## Versione Web (nessuna dipendenza)

Doppio clic su `leviathadm.html` (Edge o Chrome), poi "Apri cartella" e scegli **questa cartella**
(quella che contiene `PO 2026/` e `Anagrafica/`). Il browser chiede il permesso a ogni apertura e non memorizza nulla.

## Il vault demo

`PO 2026/` contiene 10 rilasci in tutti gli stati del ciclo di vita (Da Avviare → Concluso, più un
Rinominato), con resoconti in bozza e inviati, un Verbale di Collaudo, una convocazione di startup
(`.eml`), una lettera da mandare in firma, scadenze tassative e azioni aperte: il cruscotto
(Scadenze, Bozze da inviare, Da collaudare, Da firmare, Stato invii) è popolato in ogni sezione.
Le date sono relative al giorno in cui il pack è stato generato. La cartella è anche un vault Obsidian.

Formato dei dati: `SCHEMA.md`. Template Word e markdown in `Template/`. Il **manuale utente** è dentro
l'applicazione: voce "Manuale" nel menu di entrambe le versioni (nella Web anche dalla schermata iniziale).
"""


# ── vault demo ─────────────────────────────────────────────────────────────────────────────
def genera_vault(root: Path, oggi: date) -> None:
    from leviathadm.vault import cruscotto, resoconti, writers
    cruscotto.allinea_root(root)
    import build_bozze, build_da_collaudare, build_da_firmare, build_project_pages, build_rilasci, build_riunioni  # noqa: E401
    import build_scadenze, build_stato_invii, genera_convocazione, prepara_firma, rigenera_resoconto  # noqa: E401
    from mail_utils import read_release, team_from_release, update_frontmatter_keys

    def g(n: int) -> date:
        return oggi + timedelta(days=n)

    po = root / "PO 2026"
    po.mkdir()
    # Anagrafica e Strutture
    for nome, dir_, uff, ruolo in PERSONE_ADM:
        writers.crea_persona(root, nome, organizzazione="ADM", direzione=dir_, ufficio=uff, email=email(nome), ruolo_tipico=ruolo)
    for nome in PERSONE_SOGEI:
        writers.crea_persona(root, nome, organizzazione="SOGEI", email=email(nome, "sogei"), ruolo_tipico="referente")
    strutture = root / "Anagrafica" / "Strutture"
    strutture.mkdir()
    _w(strutture / "ADM.md", "---\ntipo: organizzazione\nfonte: demo\n---\n\n# ADM – Agenzia delle Dogane e dei Monopoli (demo)\n\n"
       "## Direzioni centrali\n\n" + "".join(f"[[{s}]]\n" for s in DIREZIONI))
    _w(strutture / "SOGEI.md", "---\ntipo: organizzazione\nfonte: demo\n---\n\n# SOGEI (demo)\n")
    for sigla, (nome, uffici) in DIREZIONI.items():
        _w(strutture / f"{sigla}.md", f"---\ntipo: direzione\nambito: centrale\norganizzazione: ADM\nnome_ufficiale: {nome}\n"
           f"fonte: demo\n---\n\n# {sigla}\n\n**{nome}**\n\n[[ADM]]\n\n" + "".join(f"[[{u}]]\n" for u in uffici))
        for u in uffici:
            _w(strutture / f"{u}.md", f"---\ntipo: ufficio\norganizzazione: ADM\ndirezione: {sigla}\nfonte: demo\n---\n\n# {u}\n\n[[{sigla}]]\n")
    # Aree, progetti, sottoprogetti
    for area, progetti in AREE.items():
        _w(root / "Aree" / f"{area}.md", f"---\ntipo: area_po2026\n---\n\n# {area}\n\n[[PO 2026]]\n")
        for cod in progetti:
            build_project_pages.write_project(cod, area, PROGETTI[cod])
    for cod_sub, desc in SOTTOPROGETTI.items():
        build_project_pages.write_subproject(cod_sub, cod_sub.split("-")[0], desc)

    def scheda(cod: str, desc: str, ra: str, rp: str, rb: str, struttura: str, sogei: str, stato: str,
               collaudo: date | None, rilascio: date | None, **fm) -> Path:
        sub = cod.rsplit("-", 1)[0]
        collaudo = lavorativo(collaudo) if collaudo else None
        rel = {"cod_rilascio": cod, "cod_sub": sub, "desc_progetto": PROGETTI[sub.split("-")[0]],
               "desc_sub": SOTTOPROGETTI[sub], "desc_rilascio": desc, "pm": PM, "ra": ra, "rp": rp,
               "referente_business": rb, "struttura_business": struttura, "referente_sogei": sogei,
               "vincoli_normativi": fm.pop("vincoli_normativi", "NO"),
               "data_collaudo_prevista": collaudo.isoformat() if collaudo else "",
               "data_rilascio_prevista": rilascio.isoformat() if rilascio else ""}
        path = writers.crea_rilascio(rel, po)
        update_frontmatter_keys(path, {"stato": stato, **fm})
        path.write_text(path.read_text(encoding="utf-8").replace("Stato: **Bozza**", f"Stato: **{stato}**"), encoding="utf-8")
        return path

    def sezione(path: Path, heading: str, righe: list[str]) -> None:
        writers.replace_section(path, heading, "\n" + "\n".join(righe) + "\n\n", mt(path))

    def resoconto(cod: str, etichetta: str, data: date, *, argomenti: str = "", azioni: list[str] | None = None,
                  scadenza: date | None = None, approvato: bool = False, definitivo: bool = False,
                  variante: str | None = None, verbale=None) -> Path:
        """Scheletro reale + ARGOMENTI/AZIONI demo + .docx; con `scadenza` è un resoconto inviato (in inviati/)."""
        fm, text = read_release(cod)
        team = team_from_release(text)
        presenze = {"adm": [{"nome": n} for r in ("PM", "RA", "RP", "RB") for n in team[r]],
                    "sogei": [{"nome": n} for n in team["SOGEI"]]}
        testo = resoconti.crea_scheletro(fm, etichetta, data, team=team, variante=variante, presenze=presenze,
                                         verbale=verbale, oggi=data + timedelta(days=1)).replace("Astolfo Lunardi", PM_ESTESO)
        if argomenti:
            testo = testo.replace("## ARGOMENTI TRATTATI\n\n\n---", f"## ARGOMENTI TRATTATI\n\n{argomenti}\n\n---")
        if azioni:
            testo = testo.replace("## AZIONI CONCORDATE\n\n\n---", "## AZIONI CONCORDATE\n\n" + "\n".join(f"- {a}" for a in azioni) + "\n\n---")
        md = po / cod / resoconti.nome_file(cod, etichetta, data)
        writers.crea_file(md, testo)
        sk = po / cod / f"{cod}.md"
        writers.aggiungi_riunione(sk, data.isoformat(), resoconti.fase_tabella(etichetta), "", md.stem, mt(sk))
        rigenera_resoconto.rigenera(md)
        if scadenza is None:
            return md
        out = writers.archivia_bozza(md, mt(md))
        upd = {"data_scadenza_approvazione": scadenza.isoformat()}
        if approvato:   # chiudi_approvazione (master) produce il PDF: qui un PDF minimo al suo posto
            upd["data_approvazione"] = scadenza.isoformat()
            _pdf_minimo(out.with_suffix(".pdf"), f"{out.stem} - versione definitiva (demo)")
        if definitivo:
            upd["definitivo_inviato"] = "true"
        update_frontmatter_keys(out, upd)
        return out

    def verbale_positivo(cod: str, verifiche: list[str], documento: str, data: date):
        """Verbale di Collaudo reale (genera_pagina_collaudo) con tutte le verifiche superate e data compilata."""
        vpath = genera_convocazione.genera_pagina_collaudo(cod, verifiche, documento, data, po / cod)
        vtesto = re.sub(r"- \[ \] Superato$", "- [x] Superato", vpath.read_text(encoding="utf-8"), flags=re.M)
        vtesto = vtesto.replace("**Data verbale:**", f"**Data verbale:** {it(data)}").replace("esito_collaudo:", "esito_collaudo: POSITIVO")
        vpath.write_text(vtesto, encoding="utf-8")
        return resoconti.parse_verbale(vpath, vtesto, mt(vpath))

    def storico(cod: str, desc: str, startup: date, analisi: date, sal: date | None = None) -> None:
        """Startup, Prima Analisi ed eventuale SAL 1: inviati, approvati, definitivo inviato."""
        for etichetta, d in (("Startup", startup), ("Prima Analisi", analisi), ("SAL 1", sal)):
            if d is None:
                continue
            resoconto(cod, etichetta, d, argomenti=ARGOMENTI[etichetta].format(desc=desc),
                      azioni=[f"SOGEI — trasmettere la documentazione aggiornata di \"{desc}\" — entro il {it(d + timedelta(days=14))}"],
                      scadenza=lavorativo(d + timedelta(days=7)), approvato=True, definitivo=True)

    # 1. Da Avviare
    s = scheda("ADM901-01-0A", "Portale per la vendita di biglietti delle lotterie lunari", "Vaporetti Clelia",
               "Sestante Ottavia", "Bussola Ermenegilda", "DGLL", "Nebulosa Corrado", "Da Avviare", g(120), g(150))
    sezione(s, "Prossima riunione", ["Startup — da convocare (referente SOGEI da confermare)"])
    # 2. Bozza + convocazione startup
    s = scheda("ADM902-01-0A", "Registro telematico dei dazi sui dirigibili in transito", "Mongolfieri Ruggero",
               "Zefiro Baldassarre", "Ancora Teodorico", "DDOC", "Quasar Ludovica", "Bozza", g(100), g(130))
    d_startup = lavorativo(g(7))
    alt = [lavorativo(d_startup + timedelta(days=1)), lavorativo(d_startup + timedelta(days=2))]
    genera_convocazione.genera_convocazione_startup("ADM902-01-0A", d_startup, organizer=email(PM),
                                                    alternative=[genera_convocazione._fmt_giorno(a) + " ore 10:00" for a in alt])
    sezione(s, "Prossima riunione", [f"Startup — {it(d_startup)} ore 10:00 (convocazione da inviare)"])
    # 3. Startup: resoconto in bozza
    s = scheda("ADM903-01-0A", "Anagrafe nazionale degli alchimisti autorizzati alla distillazione", "Lanterna Costanza",
               "Alambicco Ildebrando", "Timone Gualtiero", "DACV", "Meteora Isidoro", "Startup", g(110), g(140),
               vincoli_normativi="SI")
    resoconto("ADM903-01-0A", "Startup", lavorativo(g(-3)), argomenti=ARGOMENTI["Startup"].format(desc="Anagrafe Alchimisti Autorizzati"),
              azioni=[f"SOGEI — predisporre il documento di analisi — entro il {it(g(30))}",
                      f"RB — fornire l'elenco delle categorie di alchimisti — entro il {it(g(10))}"])
    sezione(s, "Azioni aperte", [f"- [ ] [[Timone Gualtiero]] — fornire l'elenco delle categorie di alchimisti — scadenza: {it(g(10))}"])
    sezione(s, "Prossima riunione", [f"Prima Analisi — {it(lavorativo(g(14)))} ore 11:00"])
    # 4. Analisi: startup inviato con approvazione tacita scaduta
    s = scheda("ADM903-02-0B", "Tracciabilità delle partite di tabacco provenienti da Atlantide", "Vaporetti Clelia",
               "Sestante Ottavia", "Timone Gualtiero", "DACV", "Cometa Fiorenza", "Analisi", g(90), g(120),
               data_fine_analisi=g(30).isoformat())
    resoconto("ADM903-02-0B", "Startup", lavorativo(g(-20)), argomenti=ARGOMENTI["Startup"].format(desc="Tracciabilità Tabacchi di Atlantide"),
              azioni=[f"SOGEI — avviare l'analisi dei requisiti — entro il {it(g(-5))}"], scadenza=lavorativo(g(-10)))
    sezione(s, "Decisioni chiave", [f"- {g(-20).isoformat()} — Data fine analisi concordata: {it(g(30))}"])
    sezione(s, "Prossima riunione", [f"Prima Analisi — {it(lavorativo(g(5)))} ore 10:00"])
    # 5. In corso: SAL 1 definitivo, SAL 2 in bozza, azioni con scadenza
    s = scheda("ADM904-01-0A", "Cruscotto di monitoraggio delle accise sulle caldaie a vapore", "Mongolfieri Ruggero",
               "Zefiro Baldassarre", "Dirigibile Anselmo", "DACV", "Pulsar Tancredi", "In corso", g(60), g(90),
               data_fine_analisi=g(-40).isoformat(),
               protocollo_analisi=f"310 del {it(g(-38))} (Registro Contratto ADM — Protocollo in Ingresso; rif. SOGEI 90310/RU)",
               protocollo_approvazione_analisi=f"325/2026 del {it(g(-33))} (Registro Ufficiale — Protocollo in Uscita)")
    storico("ADM904-01-0A", "Cruscotto Accise sul Vapore", lavorativo(g(-70)), lavorativo(g(-50)), lavorativo(g(-25)))
    resoconto("ADM904-01-0A", "SAL 2", lavorativo(g(-2)), argomenti=ARGOMENTI["SAL"].format(desc="Cruscotto Accise sul Vapore"),
              azioni=[f"SOGEI — rilasciare in ambiente di validazione il cruscotto — entro il {it(g(12))}",
                      f"RA — verificare le anagrafiche delle caldaie — entro il {it(g(-2))}"])
    sezione(s, "Azioni aperte", [f"- [ ] [[Mongolfieri Ruggero]] — verificare le anagrafiche delle caldaie — scadenza: {it(g(-2))}",
                                 f"- [ ] [[Pulsar Tancredi]] — confermare il perimetro dei dati storici — scadenza: {it(oggi)}",
                                 "- [x] [[Dirigibile Anselmo]] — fornire i profili utente"])
    sezione(s, "Prossima riunione", [f"SAL #3 — {it(lavorativo(g(20)))} ore 15:00"])
    # 2.0: proposta dell'agente Copilot per il prossimo SAL (Nuova riunione con quella data → "Importa da Copilot")
    import proposta_copilot
    d3 = lavorativo(g(20))
    pp = proposta_copilot.percorso_proposta(po / "ADM904-01-0A", d3.isoformat(), "SAL #3")
    pp.parent.mkdir(parents=True, exist_ok=True)
    _w(pp, f"---\ntipo: proposta_copilot\ncodice_rilascio: ADM904-01-0A\ndata_riunione: {d3.isoformat()}\nfase: SAL #3\nfonte: Recap Teams\n"
           f"generato: {oggi.isoformat()}\nagente: Resoconti PO 2026\n---\n\n## PARTECIPANTI\n**ADM**: Mongolfieri Ruggero; Zefiro Baldassarre\n**SOGEI**: Pulsar Tancredi\n\n"
           "## ARGOMENTI TRATTATI\n\nSOGEI ha presentato il cruscotto rilasciato in ambiente di validazione e ha illustrato le anagrafiche delle caldaie caricate; "
           "ADM ha verificato la coerenza dei totali con i dati storici.\n\nIl business ha chiesto di aggiungere il filtro per provincia; SOGEI ha stimato l'attività "
           "senza impatto sulla data di messa in esercizio.\n\n## AZIONI CONCORDATE\n- SOGEI — aggiungere il filtro per provincia — scadenza: "
           f"{it(lavorativo(g(34)))}\n- RA — confermare il perimetro dei dati storici — scadenza: non indicata\n\n## NOTE PER IL PM\n"
           "- Non è chiaro se il filtro per provincia rientri nell'effort approvato: da confermare con l'RA.\n")
    # 6. In corso, confluito: Prima Analisi approvata, definitivo da inviare
    s = scheda("ADM904-02-0B", "Monitoraggio delle scommesse sulle regate di dirigibili", "Lanterna Costanza",
               "Alambicco Ildebrando", "Bussola Ermenegilda", "DGLL", "Aurora Domitilla", "In corso", g(80), g(110),
               codice_rilascio_precedente="ADM904-02-0A")
    resoconto("ADM904-02-0B", "Prima Analisi", lavorativo(g(-15)), argomenti=ARGOMENTI["Prima Analisi"].format(desc="Monitoraggio Scommesse sulle Regate"),
              azioni=[f"SOGEI — consolidare i requisiti del monitoraggio — entro il {it(g(20))}"],
              scadenza=lavorativo(g(-8)), approvato=True)
    sezione(s, "Decisioni chiave", [f"- {g(-30).isoformat()} — Il rilascio assorbe le attività del vecchio codice [[ADM904-02-0A]] (confluenza)"])
    # 10. Rinominato (vecchio codice del 6)
    s = scheda("ADM904-02-0A", "Monitoraggio delle scommesse sulle regate (codice precedente)", "Lanterna Costanza",
               "Alambicco Ildebrando", "Bussola Ermenegilda", "DGLL", "Aurora Domitilla", "Rinominato", None, None,
               codice_rilascio_successivo="ADM904-02-0B")
    s.write_text(s.read_text(encoding="utf-8").replace("\n\n[[ADM904-02]]\n", f"\n\n> ⚠️ Rinumerato il {it(g(-30))}: le attività "
                 "proseguono con il nuovo codice [[ADM904-02-0B]]. Riunioni e azioni qui sotto sono storiche.\n\n[[ADM904-02]]\n", 1), encoding="utf-8")
    sezione(s, "Decisioni chiave", [f"- {g(-30).isoformat()} — Rinumerato in [[ADM904-02-0B]]: le attività proseguono con il nuovo codice"])
    # 7. In Verifica: disponibilità al collaudo ricevuta → scadenza tassativa, Da collaudare
    s = scheda("ADM902-02-0B", "Sportello telematico per le dichiarazioni doganali degli zeppelin", "Vaporetti Clelia",
               "Sestante Ottavia", "Ancora Teodorico", "DDOC", "Eclisse Raimondo", "In Verifica", g(10), g(40),
               data_fine_analisi=g(-40).isoformat(),
               protocollo_analisi=f"402 del {it(g(-38))} (Registro Contratto ADM — Protocollo in Ingresso; rif. SOGEI 90402/RU)",
               protocollo_approvazione_analisi=f"418/2026 del {it(g(-33))} (Registro Ufficiale — Protocollo in Uscita)",
               protocollo_disponibilita_collaudo=f"rif. SOGEI 90477/RU del {it(g(-5))} (non protocollo ADM — DA COMPLETARE)",
               data_disponibilita_collaudo=g(-5).isoformat())
    storico("ADM902-02-0B", "Sportello Telematico Zeppelin", lavorativo(g(-60)), lavorativo(g(-45)), lavorativo(g(-30)))
    sezione(s, "Azioni aperte", [f"- [ ] [[{PM}]] — convocare il collaudo — scadenza: {it(g(15))}"])
    sezione(s, "Prossima riunione", [f"Collaudo — {it(lavorativo(g(10)))} ore 10:00 (da convocare)"])
    # 8. Collaudo svolto: Verbale, resoconto di collaudo in bozza, lettera da mandare in firma
    d_coll = lavorativo(g(-7))
    s = scheda("ADM902-03-0C", "Verifica automatica dell'integrità dei sigilli doganali sui dirigibili", "Mongolfieri Ruggero",
               "Zefiro Baldassarre", "Faro Ginevra", "DDOC", "Orbita Serafina", "Collaudo", d_coll, g(20),
               data_fine_analisi=g(-60).isoformat(),
               protocollo_analisi=f"501 del {it(g(-58))} (Registro Contratto ADM — Protocollo in Ingresso; rif. SOGEI 90501/RU)",
               protocollo_approvazione_analisi=f"520/2026 del {it(g(-52))} (Registro Ufficiale — Protocollo in Uscita)",
               protocollo_disponibilita_collaudo=f"588 del {it(g(-30))} (Registro Contratto ADM — Protocollo in Ingresso; rif. SOGEI 90588/RU)",
               data_disponibilita_collaudo=g(-30).isoformat(), data_collaudo_effettiva=d_coll.isoformat())
    storico("ADM902-03-0C", "Verifica Automatica Sigilli Doganali", lavorativo(g(-90)), lavorativo(g(-75)), lavorativo(g(-50)))
    resoconto("ADM902-03-0C", "Collaudo", d_coll, variante="telematica",
              verbale=verbale_positivo("ADM902-03-0C", VERIFICHE, "Documento di analisi SIG-DEMO-01 v1.0", d_coll))
    shutil.copy2(REPO / "Template" / "Template - ADMXXX-XX-XX Trasmissione copia verbale di collaudo.docx",
                 po / "ADM902-03-0C" / "ADM902-03-0C Trasmissione copia verbale di collaudo.docx")
    sezione(s, "Azioni aperte", [f"- [ ] [[{PM}]] — mandare in firma la trasmissione del verbale — scadenza: {it(g(5))}"])
    # 9. Concluso: lettere protocollate
    d_coll9 = lavorativo(g(-60))
    s = scheda("ADM905-01-0A", "Archivio digitale delle concessioni marittime e aerostatiche", "Lanterna Costanza",
               "Alambicco Ildebrando", "Faro Ginevra", "DDOC", "Stellare Bonifacio", "Concluso", d_coll9, g(-45),
               data_fine_analisi=g(-120).isoformat(), data_collaudo_effettiva=d_coll9.isoformat(), data_rilascio_effettiva=g(-45).isoformat(),
               protocollo_analisi=f"120 del {it(g(-118))} (Registro Contratto ADM — Protocollo in Ingresso; rif. SOGEI 90120/RU)",
               protocollo_approvazione_analisi=f"131/2026 del {it(g(-110))} (Registro Ufficiale — Protocollo in Uscita)",
               protocollo_disponibilita_collaudo=f"170 del {it(g(-80))} (Registro Contratto ADM — Protocollo in Ingresso; rif. SOGEI 90170/RU)",
               data_disponibilita_collaudo=g(-80).isoformat(),
               protocollo_collaudo=f"190/2026 del {it(g(-55))} (Registro Ufficiale — Protocollo in Uscita)",
               protocollo_estensione_esercizio=f"191/2026 del {it(g(-55))} (Registro Ufficiale — Protocollo in Uscita)",
               trasmissione_verbale_protocollata="true", estensione_esercizio_protocollata="true")
    storico("ADM905-01-0A", "Archivio Concessioni Marittime", lavorativo(g(-150)), lavorativo(g(-130)))
    resoconto("ADM905-01-0A", "Collaudo", d_coll9, variante="telematica_in_riunione", scadenza=lavorativo(g(-53)), approvato=True, definitivo=True,
              verbale=verbale_positivo("ADM905-01-0A", ["Caricamento di una concessione marittima", "Ricerca per codice concessione",
                                                        "Estratto conto delle concessioni aerostatiche"], "Documento di analisi ARC-DEMO-03 v2.1", d_coll9))

    # dashboard e pagine
    _w(root / "PO 2026.md", DASHBOARD.format(oggi=oggi.isoformat(), pm=PM_ESTESO))
    _w(po / "Punti aperti.md", f"---\naggiornato: {oggi.isoformat()}\n---\n\n# Punti aperti / da sbloccare\n\n"
       f"- **[[ADM902-02-0B]]** — disponibilità a collaudo ricevuta il {it(g(-5))}: protocollo ADM da chiedere, collaudo da convocare entro il {it(g(15))}\n"
       f"- **[[ADM903-02-0B]]** — resoconto di startup inviato il {it(g(-20))} senza riscontro: approvazione tacita da chiudere\n"
       f"- **[[ADM901-01-0A]]** — referente SOGEI da confermare prima di convocare lo startup\n")
    prepara_firma.prepara_cartella = lambda codice, label: False   # niente Word/PDF nel pack: la cartella firma la prepara il sync
    for m in (build_rilasci, build_riunioni, build_scadenze, build_bozze, build_stato_invii, build_da_collaudare, build_da_firmare):
        m.build()


ARGOMENTI = {
    "Startup": ("Nel corso della riunione ADM ha illustrato l'obiettivo del rilascio \"{desc}\" e il contesto normativo di "
                "riferimento. SOGEI ha confermato la fattibilità di quanto previsto e ha proposto di avviare l'analisi dei "
                "requisiti con un primo incontro dedicato. Il business ha evidenziato la necessità di coinvolgere gli uffici "
                "territoriali nella fase di raccolta dei requisiti."),
    "Prima Analisi": ("SOGEI ha presentato la bozza del documento di analisi di \"{desc}\", illustrando l'architettura "
                      "proposta e i flussi informativi coinvolti. ADM ha condiviso l'impostazione generale e ha richiesto "
                      "alcune integrazioni sui controlli di coerenza dei dati. Le parti hanno concordato il calendario "
                      "delle successive riunioni di avanzamento."),
    "SAL": ("SOGEI ha illustrato lo stato di avanzamento delle attività di sviluppo di \"{desc}\", confermando il rispetto "
            "della pianificazione concordata. ADM ha verificato le funzionalità già disponibili in ambiente di test e ha "
            "segnalato alcune osservazioni di dettaglio, prese in carico da SOGEI. È stata confermata la data prevista per "
            "la disponibilità al collaudo."),
}
ARGOMENTI["SAL 1"] = ARGOMENTI["SAL"]

DASHBOARD = """---
programma: PO 2026 (demo)
pm: {pm}
---

# PO 2026 — Dashboard Programma (demo)

> Aggiornato: {oggi} · PM: {pm} · **Dati interamente fittizi**

---

## Navigazione rapida

| Pagina | Contenuto |
|--------|-----------|
| [[Rilasci]] | Panoramica rilasci, stati, date, team |
| [[Riunioni]] | Stato avanzamento riunioni per rilascio |
| [[Bozze da inviare]] | Resoconti da inviare e definitivi in attesa |
| [[Stato invii]] | Matrice punti di piano × fase: provvisorio/definitivo inviati |
| [[Scadenze]] | Scadenze imminenti, azioni, approvazioni |
| [[Da collaudare]] | Punti di piano in attesa di collaudo — compila qui la data effettiva |
| [[Da firmare]] | Lettere di fine collaudo da mandare in firma / in attesa di protocollazione |
| [[Punti aperti]] | Blocchi aperti e documenti di riferimento |

---

## Riepilogo programma

- **PM:** {pm}
- **Rilasci:** 10 (9 attivi/storici + 1 rinominato)
- **Strutture coinvolte:** DTDR · DGLL · DDOC · DACV
"""


def _pdf_minimo(path: Path, testo: str) -> None:
    """PDF di una pagina con una riga di testo (nessuna dipendenza): segnaposto del PDF che genera il master."""
    stream = f"BT /F1 12 Tf 40 780 Td ({testo}) Tj ET".encode("latin-1", "replace")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    path.write_bytes(bytes(out))


def _w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ── pulizia dei nomi reali ─────────────────────────────────────────────────────────────────
# Codice, template Word/mail e docstring citano persone reali (esempi, default del PM, metadati dei .docx).
# I nomi reali si leggono solo dai NOMI FILE dell'Anagrafica e dal campo pm della dashboard, per sostituirli:
# ogni persona reale diventa una persona inventata (il PM reale diventa il PM demo), nei due ordini
# Cognome Nome / Nome Cognome, in MAIUSCOLO, da solo (cognomi >= 5 lettere) e come email nome.cognome@.
_COGNOMI = ["Aquilone", "Brezza", "Ciclone", "Dirupo", "Estuario", "Foschia", "Grecale", "Isolotto", "Libeccio", "Maestrale",
            "Nevischio", "Ortensia", "Pennacchio", "Quadrante", "Rugiada", "Scirocco", "Tramontana", "Uragano", "Vortice",
            "Zenit", "Alveare", "Burrasca", "Cumulo"]
_NOMI = ["Amerigo", "Brunilde", "Cassiopea", "Demetrio", "Ersilia", "Fulgenzio", "Gelsomina", "Ipazia", "Leopoldo", "Marzia",
         "Nicodemo", "Ortensio", "Prudenzia", "Romualdo", "Sigismonda", "Tiberio", "Urbano", "Venusta", "Zaccaria"]


def mappa_nomi() -> dict[str, str]:
    """{variante reale (minuscola): sostituto} — stessa forma (Cognome Nome / Nome Cognome / cognome / email)."""
    pm_reale = re.search(r"^pm: (.+)$", (REPO / "PO 2026.md").read_text(encoding="utf-8"), re.M).group(1).strip()
    cognome_pm = pm_reale.split()[-1]
    reali = sorted(p.stem for p in (REPO / "Anagrafica").glob("*.md"))
    if not any(s.split()[0] == cognome_pm for s in reali):
        reali.append(f"{cognome_pm} {' '.join(pm_reale.split()[:-1])}")
    usati, mappa = set(), {}
    for i, stem in enumerate(reali):
        parti = stem.split()
        cognome, nome = parti[0], " ".join(parti[1:])
        if cognome == cognome_pm:
            fc, fn = PM.split(" ", 1)
        else:
            fc, fn = _COGNOMI[i % len(_COGNOMI)], _NOMI[i % len(_NOMI)]
            while (fc, fn) in usati:
                fn = _NOMI[(_NOMI.index(fn) + 1) % len(_NOMI)]
        usati.add((fc, fn))
        mappa[f"{cognome} {nome}".lower()] = f"{fc} {fn}"
        mappa[f"{nome} {cognome}".lower()] = f"{fn} {fc}"
        if len(cognome) >= 5:
            mappa[cognome.lower()] = fc
        if nome and "'" not in nome:
            mappa[f"{nome.replace(' ', '.')}.{cognome}".lower()] = f"{fn.replace(' ', '.')}.{fc}".lower()
    for host in json.loads((REPO / "scripts" / "machines.json").read_text(encoding="utf-8"))["machines"]:
        mappa[host.lower()] = "PC-DEMO"   # es. il tooltip "solo sul master (<hostname>)" in azioni.py
    return mappa


def _sostitutore(mappa: dict[str, str]):
    chiavi = sorted(mappa, key=len, reverse=True)
    rx = re.compile(r"(?<![\w.])(" + "|".join(re.escape(k) for k in chiavi) + r")(?![\w.])", re.I)
    isolati = {k for k in mappa if " " not in k and "." not in k}   # cognomi da soli: solo Capitalizzati o MAIUSCOLI

    def sost(m: re.Match) -> str:
        s = m.group(0)
        k = s.lower()
        if k in isolati and not (s[0].isupper()):
            return s
        nuovo = mappa[k]
        return nuovo.upper() if s.isupper() and len(s) > 1 else nuovo
    return lambda testo: rx.sub(sost, testo)


def pulisci_testi(dest: Path, mappa: dict[str, str]) -> None:
    sost = _sostitutore(mappa)
    for p in dest.rglob("*"):
        if p.is_file() and p.suffix in (".py", ".md", ".txt", ".json", ".cmd", ".html", ".js", ".css") and "python" not in p.relative_to(dest).parts:
            t = p.read_text(encoding="utf-8")
            n = re.sub(r"\bADM[01](\d{2})\b", r"ADM9\1", sost(t))   # codici reali negli esempi (ADM953-01-0L → ADM953-01-0L)
            if n != t:
                p.write_text(n, encoding="utf-8", newline="")


def pulisci_docx(dest: Path, mappa: dict[str, str]) -> None:
    """Testo e metadati (creator/lastModifiedBy) di ogni .docx del pack: template Word e resoconti generati."""
    sost = _sostitutore(mappa)
    for p in dest.rglob("*.docx"):
        with zipfile.ZipFile(p) as z:
            voci = [(i, z.read(i.filename)) for i in z.infolist()]
        nuove = []
        for info, dati in voci:
            if info.filename.endswith(".xml"):
                t = re.sub(r"\bADM[01](\d{2})\b", r"ADM9\1", sost(dati.decode("utf-8")))
                t = re.sub(r"(<dc:creator>)[^<]*(</dc:creator>)", r"\1LeviathADM demo\2", t)
                t = re.sub(r"(<cp:lastModifiedBy>)[^<]*(</cp:lastModifiedBy>)", r"\1LeviathADM demo\2", t)
                dati = t.encode("utf-8")
            nuove.append((info.filename, dati))
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            for nome, dati in nuove:
                z.writestr(nome, dati)


# ── Python embedded ────────────────────────────────────────────────────────────────────────
def installa_python(dest: Path) -> None:
    cache = Path(tempfile.gettempdir()) / "leviathadm-demo-cache"
    cache.mkdir(exist_ok=True)
    zip_py, getpip = cache / PY_URL.rsplit("/", 1)[1], cache / "get-pip.py"
    for url, out in ((PY_URL, zip_py), (GETPIP_URL, getpip)):
        if not out.exists():
            print(f"Scarico {url} …")
            urllib.request.urlretrieve(url, out)
    py = dest / "python"
    with zipfile.ZipFile(zip_py) as z:
        z.extractall(py)
    pth = next(py.glob("python3*._pth"))
    pth.write_text(f"{pth.stem.replace('._pth', '')}.zip\n.\n..\nimport site\n", encoding="utf-8")   # .. = radice del pack
    exe = py / "python.exe"
    # -s: mai il site-packages utente di un altro Python 3.12 (altrimenti pip salterebbe pacchetti "già installati"
    # sulla macchina che costruisce, e sul PC di destinazione quelli dell'utente prevarrebbero su quelli del pack)
    run = lambda *a: subprocess.run([str(exe), "-s", *a], check=True)  # noqa: E731
    run(str(getpip), "-q", "--no-warn-script-location")
    run("-m", "pip", "install", "-q", "--no-warn-script-location", "--disable-pip-version-check", "-r", str(dest / "requirements.txt"))
    # niente pywin32_postinstall: registrerebbe COM/DLL sul PC che costruisce; pywin32 funziona già con pywin32.pth
    for launcher in (py / "Scripts").glob("*.exe"):   # incorporano il percorso assoluto di questo PC: inutili altrove (python -m pip)
        launcher.unlink()
    run("-c", "import nicegui, docx, openpyxl, win32com; print('Python embedded ok')")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dest", type=Path, default=REPO.parent / "LeviathADM-demo")
    p.add_argument("--senza-python", action="store_true", help="non scaricare il Python embedded")
    a = p.parse_args()
    dest = a.dest.resolve()
    if dest.is_relative_to(REPO) or REPO.is_relative_to(dest):
        sys.exit(f"destinazione dentro il vault reale: {dest}")
    if dest.exists():
        if any(dest.iterdir()) and not (dest / MARKER).exists():
            sys.exit(f"{dest} esiste e non è un pack demo (manca {MARKER}): non la cancello")
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    print(f"Pack in {dest}")
    copia_codice(dest)
    mappa = mappa_nomi()
    pulisci_testi(dest, mappa)        # prima del vault: i template .txt/.md puliti producono .eml e resoconti puliti
    genera_vault(dest, date.today())
    pulisci_docx(dest, mappa)         # dopo: i .docx generati ereditano i metadati dei template Word
    if not a.senza_python:
        installa_python(dest)
    shutil.rmtree(dest / "Bozze da inviare", ignore_errors=True)
    for pc in dest.rglob("__pycache__"):
        shutil.rmtree(pc, ignore_errors=True)
    zip_out = dest.parent / (dest.name + ".zip")   # non with_suffix: "demo-1.0" perderebbe il ".0"
    zip_out.unlink(missing_ok=True)
    shutil.make_archive(str(dest), "zip", root_dir=dest.parent, base_dir=dest.name)
    print(f"Fatto: {dest}\n       {zip_out} ({zip_out.stat().st_size // 1_000_000} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
