"""build_strutture.py — costruisce/aggiorna Anagrafica/Strutture/ con
l'organigramma ufficiale ADM (fonte: www.adm.gov.it, accesso 2026-06-12).

Genera o aggiorna:
  - ADM.md (nodo radice con tutte le direzioni)
  - un nodo per ogni direzione centrale (sigla se consolidata nel vault)
  - un nodo per ogni ufficio, con dirigente (wikilink se presente in Anagrafica)
  - un nodo per ogni direzione territoriale (prefisso "DT ")
  - DIREZIONE GENERALE con gli uffici di staff

I wikilink presenti nei nodi esistenti ma non previsti dall'organigramma
vengono preservati in coda ("Altri collegamenti"). Idempotente.

Uso:
    python scripts/build_strutture.py
"""

from __future__ import annotations

import re
from pathlib import Path

VAULT = Path(__file__).parent.parent
STRUTTURE = VAULT / "Anagrafica" / "Strutture"
ANAGRAFICA = VAULT / "Anagrafica"

FONTE = "www.adm.gov.it — Organigramma / Articolazione degli uffici (accesso 2026-06-12)"

# ---------------------------------------------------------------------------
# Organigramma ufficiale ADM
# ---------------------------------------------------------------------------

# Ogni direzione centrale ha la propria area di staff (denominazione come nelle
# lettere protocollate, es. ADMUC_926/2026)
AREA_STAFF = "Area di Staff"

# nodo: (nome ufficiale, sigla vault | None, direttore, [(ufficio, dirigente)])
DIREZIONI_CENTRALI = {
    "DGIO": {
        "nome": "Direzione Giochi",
        "direttore": "Mario LOLLOBRIGIDA",
        "uffici": [
            ("Apparecchi da intrattenimento", "Elisabetta POSO"),
            ("Bingo", "Maria Rosaria MEOLA"),
            ("Gioco a distanza e scommesse", "Antonio GIULIANI"),
            ("Giochi numerici e lotterie", "Fulgenzio Brezza"),
            ("Controlli giochi", "Gelsomina Quadrante"),
        ],
    },
    "DDOG": {
        "nome": "Direzione Dogane",
        "direttore": "Claudio OLIVIERO",
        "uffici": [
            ("Disciplina risorse proprie e altri diritti doganali", "Giovanni MUNGIOLI"),
            ("AEO, compliance e grandi imprese", "Loredana SASSO"),
            ("Tariffa e classificazione", "Sabrina FOSCHIA"),
            ("Origine e valore", "Anna MAIELLO"),
            ("Regimi e procedure doganali", "Marlene DIRUPO"),
            ("Controlli dogane", "Antonella BIANCHI"),
            ("Autorizzazioni temporanee e settore agricolo", "Augusto ZUCARO"),
        ],
    },
    "DACC": {
        "nome": "Direzione Accise",
        "direttore": "Luigi LIBERATORE",
        "uffici": [
            ("Disciplina tabacchi, prodotti liquidi da inalazione e altri prodotti soggetti a imposta di consumo", "Roberto GALDI"),
            ("Rete vendita tabacchi, prodotti liquidi da inalazione e altri prodotti soggetti a imposta di consumo", "Andrea BIZZARRI"),
            ("Circolazione tabacchi, prodotti liquidi da inalazione e altri prodotti soggetti a imposta di consumo", "Vincenza IANNELLI"),
            ("Disciplina energie e alcoli", "Enrico PROCENZANO"),
            ("Prodotti energetici e alcolici", "Cosmo Domenico TALLINO"),
            ("Gas naturale - energia elettrica", "Angela POLITO"),
            ("Controlli accise", "Francesca TORRICELLI"),
        ],
    },
    "DOTD": {
        "nome": "Direzione Organizzazione e Trasformazione Digitale",
        "direttore": "Stefano SARACCHI",
        "uffici": [
            ("Governo e transizione digitale", "Stefano BARGIOTTI"),
            ("Analisi e processi", "Antonino SPEZIALE"),
            ("Attuazione progetti e sicurezza informatica", "Marzia Maestrale"),
            ("Dati e gestione sistemi IT", "Luigi VOLPE"),
        ],
    },
    "DIREZIONE ANTIFRODE": {
        "nome": "Direzione Antifrode",
        "direttore": "Sergio GALLO",
        "uffici": [
            ("Intelligence", "Micol BRIGNONE"),
            ("Investigazioni", "Claudia MORI"),
            ("Laboratori", "Alessandro PROPOSITO"),
            ("Rapporti EPPO e DNA-DDA", "Paolo VALERIO"),
        ],
    },
    "DIREZIONE AMMINISTRAZIONE E FINANZA": {
        "nome": "Direzione Amministrazione e Finanza",
        "direttore": "Roberto CHIARA",
        "uffici": [
            ("Contabilità", "Vincenzo FUSCO"),
            ("Tesoreria", "Laura D'AMATO"),
            ("Acquisti e contratti", "Giuliano FOSCHIA"),
            ("Logistica", "Marco LOREFICE"),
            ("Sicurezza sul lavoro", "Francesco CORTESE"),
        ],
    },
    "DIREZIONE LEGALE E CONTENZIOSO": {
        "nome": "Direzione Legale e Contenzioso",
        "direttore": "Lorenzo CLEMENTE",
        "uffici": [
            ("Supporto giuridico", "Stefano FASOLINO"),
            ("Contenzioso tributario", "Daniele STELLA"),
            ("Contenzioso civile, amministrativo, penale", "Carlo LOPEZ"),
            ("Procedure concorsuali e coordinamento dell'accertamento", "Raffaele GRANDONE"),
        ],
    },
    "DIREZIONE PERSONALE": {
        "nome": "Direzione del Personale",
        "direttore": "Salvatore Roberto MICCICHÈ",
        "uffici": [
            ("Affari generali e relazioni sindacali", "Mariarita Simona SARDELLA"),
            ("Deontologia e contenzioso del lavoro", "Michele TIROCCHI"),
            ("Dirigenti", "Carlo SOLETTO"),
            ("Formazione e valutazione del personale", "Emanuele CEGLIE"),
            ("Gestione giuridica del personale", "Stefania PROVINI"),
            ("Mobilità", "Carla BARBATO"),
            ("Reclutamento", "Rosanna LANUZZA"),
            ("Stipendi e previdenza", "Vincenzo LOMBARDI"),
        ],
    },
}

DIREZIONE_GENERALE_UFFICI = [
    "Ufficio stampa e strategie di comunicazione",
    "Ufficio del Direttore operativo per il coordinamento delle strutture di vertice",
    "Ufficio Relazioni internazionali",
    "Ufficio Affari giuridici e normativi",
    "Ufficio Internal audit",
]

DIREZIONI_TERRITORIALI = [
    "Emilia Romagna e Marche",
    "Calabria",
    "Sicilia",
    "Veneto e Friuli Venezia Giulia",
    "Liguria",
    "Piemonte e Valle d'Aosta",
    "Puglia Molise e Basilicata",
    "Lazio e Abruzzo",
    "Toscana e Umbria",
    "Lombardia",
    "Campania",
    "Trentino-Alto Adige",
    "Sardegna",
]

# ---------------------------------------------------------------------------


def cognome_nome(nome_sito: str) -> str:
    """'Fulgenzio Brezza' -> 'Brezza Fulgenzio' (convenzione Anagrafica)."""
    tokens = nome_sito.split()
    cognome = [t.title() for t in tokens if t.isupper() and len(t) > 1]
    nome = [t for t in tokens if not (t.isupper() and len(t) > 1)]
    if not cognome:  # nessun token maiuscolo: assumo ultimo = cognome
        cognome, nome = [tokens[-1]], tokens[:-1]
    return " ".join(cognome + nome)


def dirigente_ref(nome_sito: str) -> str:
    """Wikilink se la persona è già in Anagrafica, altrimenti testo semplice."""
    cn = cognome_nome(nome_sito)
    if (ANAGRAFICA / f"{cn}.md").exists():
        return f"[[{cn}]]"
    return cn


def existing_extra_links(path: Path, generated: str) -> list[str]:
    """Wikilink presenti nel file esistente ma assenti dal contenuto generato."""
    if not path.exists():
        return []
    old_links = set(re.findall(r"\[\[([^\]|]+)", path.read_text(encoding="utf-8")))
    new_links = set(re.findall(r"\[\[([^\]|]+)", generated))
    return sorted(old_links - new_links)


def write_node(path: Path, content: str) -> None:
    extra = existing_extra_links(path, content)
    if extra:
        content += "\n## Altri collegamenti\n\n"
        content += "\n".join(f"[[{l}]]" for l in extra) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")
    print(f"  {'AGGIORNATO' if path.exists() else 'CREATO':10s} {path.name}")


def build() -> None:
    STRUTTURE.mkdir(parents=True, exist_ok=True)
    print("=== Strutture ADM da organigramma ufficiale ===")

    # --- Direzioni centrali e uffici -------------------------------------
    for nodo, dati in DIREZIONI_CENTRALI.items():
        sigla = nodo if len(nodo) <= 5 else ""
        fm = ["---", "tipo: direzione", "ambito: centrale", "organizzazione: ADM"]
        if sigla:
            fm.append(f"sigla: {sigla}")
        fm += [f"nome_ufficiale: {dati['nome']}", f"fonte: {FONTE}", "---"]
        body = [f"# {nodo}", "", f"**{dati['nome']}**", "",
                f"Direttore: {dirigente_ref(dati['direttore'])}", "", "[[ADM]]", "",
                "## Uffici", ""]
        for ufficio, _ in dati["uffici"]:
            body.append(f"[[{ufficio.upper()}]]")
        if True:  # tutte le direzioni
            sname = f"{AREA_STAFF.upper()} {nodo}"
            body += ["", "## Area di staff", "", f"[[{sname}]]"]
            write_node(STRUTTURE / f"{sname}.md", "\n".join([
                "---", "tipo: ufficio", "organizzazione: ADM", f"direzione: {nodo}",
                f"nome_ufficiale: {AREA_STAFF}", f"fonte: {FONTE}", "---", "",
                f"# {sname}", "", f"**{AREA_STAFF}** — {dati['nome']}", "", f"[[{nodo}]]",
            ]) + "\n")
        write_node(STRUTTURE / f"{nodo}.md", "\n".join(fm + [""] + body) + "\n")

        for ufficio, dirigente in dati["uffici"]:
            uname = ufficio.upper()
            content = "\n".join([
                "---", "tipo: ufficio", "organizzazione: ADM",
                f"direzione: {nodo}", f"fonte: {FONTE}", "---", "",
                f"# {uname}", "",
                f"Dirigente: {dirigente_ref(dirigente)}", "",
                f"[[{nodo}]]",
            ]) + "\n"
            write_node(STRUTTURE / f"{uname}.md", content)

    # --- Direzione Generale ----------------------------------------------
    body = ["# DIREZIONE GENERALE", "", "[[ADM]]", "", "## Uffici di staff", ""]
    body += [f"[[{u.upper()}]]" for u in DIREZIONE_GENERALE_UFFICI]
    write_node(STRUTTURE / "DIREZIONE GENERALE.md", "\n".join(
        ["---", "tipo: direzione", "ambito: vertice", "organizzazione: ADM",
         f"fonte: {FONTE}", "---", ""] + body) + "\n")
    for u in DIREZIONE_GENERALE_UFFICI:
        uname = u.upper()
        content = "\n".join([
            "---", "tipo: ufficio", "organizzazione: ADM",
            "direzione: DIREZIONE GENERALE", f"fonte: {FONTE}", "---", "",
            f"# {uname}", "", "[[DIREZIONE GENERALE]]",
        ]) + "\n"
        write_node(STRUTTURE / f"{uname}.md", content)

    # --- Direzioni territoriali ------------------------------------------
    for dt in DIREZIONI_TERRITORIALI:
        nodo = f"DT {dt.upper()}"
        content = "\n".join([
            "---", "tipo: direzione", "ambito: territoriale", "organizzazione: ADM",
            f"nome_ufficiale: Direzione territoriale {dt}", f"fonte: {FONTE}", "---", "",
            f"# {nodo}", "", f"**Direzione territoriale {dt}**", "", "[[ADM]]",
        ]) + "\n"
        write_node(STRUTTURE / f"{nodo}.md", content)

    # --- Nodo radice ADM ---------------------------------------------------
    body = ["# ADM – Agenzia delle Dogane e dei Monopoli", "",
            "[[DIREZIONE GENERALE]]", "", "## Direzioni centrali", ""]
    body += [f"[[{n}]]" for n in DIREZIONI_CENTRALI]
    body += ["", "## Direzioni territoriali", ""]
    body += [f"[[DT {dt.upper()}]]" for dt in DIREZIONI_TERRITORIALI]
    write_node(STRUTTURE / "ADM.md", "\n".join(
        ["---", "tipo: organizzazione", f"fonte: {FONTE}", "---", ""] + body) + "\n")

    # --- Alias storico DODT -> DOTD ----------------------------------------
    write_node(STRUTTURE / "DODT.md", "\n".join([
        "---", "tipo: alias", "organizzazione: ADM", "alias_di: DOTD", "---", "",
        "# DODT", "",
        "Sigla storica usata in alcuni resoconti per la "
        "Direzione Organizzazione e Trasformazione Digitale: vedi [[DOTD]].",
    ]) + "\n")

    print("Completato.")


if __name__ == "__main__":
    build()
