"""Catalogo dichiarativo delle azioni: cosa si lancia, con quali input, con quali vincoli."""
from __future__ import annotations
import sys
from dataclasses import dataclass
from typing import Literal

from leviathadm.vault.paths import SCRIPTS_DIR

S = SCRIPTS_DIR
FASI_RILASCIO = ("Startup", "Analisi", "SAL", "Collaudo")
LETTERE = {"trasmissione": "Trasmissione copia verbale di collaudo", "estensione": "Richiesta estensione in esercizio"}
_MOTIVI = {"outlook": "richiede Outlook", "word": "richiede Word", "pandoc": "richiede pandoc nel PATH"}


@dataclass(frozen=True)
class Campo:
    nome: str
    etichetta: str
    tipo: Literal["testo", "data", "scelta", "file_rilascio", "testo_lungo"] = "testo"
    default: str = ""
    opzioni: tuple[str, ...] = ()
    pattern_file: str = "*"
    obbligatorio: bool = True


@dataclass(frozen=True)
class Azione:
    id: str
    titolo: str
    descrizione: str
    ambito: Literal["globale", "Startup", "Analisi", "SAL", "Collaudo", "rilascio"]
    argomenti: tuple[str, ...]                 # dopo [python, -X, utf8]; "{nome}" da ctx; "{+nome:--flag}" = lista (flag ripetuto)
    richiede_master: bool = False
    richiede: frozenset[str] = frozenset()
    richiede_sul_master: frozenset[str] = frozenset()   # dipendenze necessarie solo quando si è master (lo slave fa meno)
    conferma: str | None = None
    campi: tuple[Campo, ...] = ()
    ricarica: tuple[str, ...] = ()
    anteprima: tuple[str, ...] = ()            # azioni in due passi: argomenti del PRIMO passo (solo lettura, es. --dry-run)
    applica: tuple[str, ...] = ()              # … e del secondo (es. --confirm); due passi = almeno uno dei due non vuoto

    @property
    def due_passi(self) -> bool:
        return bool(self.anteprima or self.applica)


def _az(**kw) -> Azione:
    return Azione(**kw)


_BUILD = ("bozze", "scadenze", "stato_invii", "rilasci", "riunioni", "da_collaudare", "da_firmare")

CATALOGO: dict[str, Azione] = {a.id: a for a in [
    _az(id="sync", titolo="Sync", descrizione="pull/push, archiviazione, pagine, Bozze da inviare/", ambito="globale",
        argomenti=(str(S / "sync.py"),)),
    _az(id="daily_check", titolo="Daily check", descrizione="master: archivia, rigenera, chiude le approvazioni tacite (Word+Outlook); slave: solo sync",
        ambito="globale", argomenti=(str(S / "daily_check.py"),), richiede_sul_master=frozenset({"outlook", "word"}),
        conferma="Esegue il check giornaliero: sul master archiviazione, rigenerazione pagine, chiusura approvazioni (PDF e .msg); sullo slave il solo sync. Procedere?"),
    _az(id="build_pagine", titolo="Rigenera tutte le pagine", descrizione="le sette build_* in sequenza", ambito="globale",
        argomenti=(str(S / "leviathadm_cli.py"), "build-pagine"), richiede_master=True, richiede=frozenset({"word"})),
    *[_az(id=f"build_{n}", titolo=f"build_{n}", descrizione=f"rigenera la pagina di build_{n}", ambito="globale",
          argomenti=(str(S / f"build_{n}.py"),), richiede_master=True,
          richiede=frozenset({"word"}) if n == "da_firmare" else frozenset()) for n in _BUILD],
    _az(id="schede_excel", titolo="Nuove schede dall'Excel", descrizione="crea le schede mancanti dall'Excel PO", ambito="globale",
        argomenti=(str(S / "leviathadm_cli.py"), "schede"), richiede_master=True, anteprima=("--dry-run",)),
    _az(id="strutture", titolo="Strutture Anagrafica", descrizione="ricostruisce Anagrafica/Strutture/ dall'organigramma",
        ambito="globale", argomenti=(str(S / "build_strutture.py"),), richiede_master=True),
    _az(id="refresh_anagrafica", titolo="Aggiorna Anagrafica dai CSV", descrizione="reinserisce le email da tutti i CSV presenze",
        ambito="globale", argomenti=(str(S / "refresh_anagrafica.py"),), richiede_master=True, anteprima=("--dry-run",)),
    _az(id="audit_dump", titolo="Audit: dump Outlook", descrizione="legge la casella (Inbox, Inviata, Progetti PO2026) → _audit/outlook_dump.json",
        ambito="globale", argomenti=(str(S / "audit_invii.py"), "--dump"), richiede=frozenset({"outlook"})),
    _az(id="audit_inventario", titolo="Audit: inventario vault", descrizione="→ _audit/inventory.json", ambito="globale",
        argomenti=(str(S / "audit_invii.py"), "--build-inventory")),
    _az(id="audit_match", titolo="Audit: match", descrizione="incrocio dump × inventario → report_audit_invii.md", ambito="globale",
        argomenti=(str(S / "audit_invii.py"), "--match")),
    _az(id="audit_deepcheck", titolo="Audit: deepcheck", descrizione="verifica approfondita di un rilascio (Outlook)", ambito="globale",
        argomenti=(str(S / "audit_invii.py"), "--deepcheck", "{codice}"), richiede=frozenset({"outlook"}),
        campi=(Campo("codice", "Codice rilascio", "scelta"),)),
    _az(id="audit_apply", titolo="Audit: applica", descrizione="riconcilia i casi certi (prima anteprima, poi conferma)", ambito="globale",
        argomenti=(str(S / "audit_invii.py"), "--apply"), applica=("--confirm",)),
    _az(id="organizza_outlook", titolo="Organizza cartelle Outlook", descrizione="smista la posta in Progetti PO2026/<codice>",
        ambito="globale", argomenti=(str(S / "organizza_cartelle_progetti.py"),), richiede=frozenset({"outlook"}), anteprima=("--dry-run",)),
    _az(id="carica_fonti", titolo="Carica fonti", descrizione="trascritti, CSV presenze, PDF in _fonti/", ambito="rilascio", argomenti=()),
    _az(id="convocazione_startup", titolo="Convocazione startup", descrizione=".eml con invito calendario", ambito="Startup",
        argomenti=(str(S / "leviathadm_cli.py"), "convocazione-startup", "{codice}", "--data", "{data}", "--ora", "{ora}",
                   "--durata", "{durata}", "{+alternative:--alternativa}"), ricarica=("*.eml",)),
    _az(id="convocazione_collaudo", titolo="Convocazione collaudo", descrizione=".eml con invito, PDF piano di test, Verbale", ambito="Collaudo",
        argomenti=(str(S / "leviathadm_cli.py"), "convocazione-collaudo", "{codice}", "--data", "{data}", "--ora", "{ora}",
                   "--durata", "{durata}", "--pdf", "{pdf}", "--documento", "{documento}", "{+verifiche:--verifica}"),
        ricarica=("*.eml", "* - 20* Verbale di Collaudo.md")),
    _az(id="mail_resoconto", titolo="Genera mail resoconto", descrizione="bozza .msg del resoconto (Outlook)", ambito="rilascio",
        argomenti=(str(S / "genera_mail_resoconto.py"), "{resoconto}", "{+allegati:}"), richiede=frozenset({"outlook"}),
        campi=(Campo("resoconto", "Resoconto (bozza)", "file_rilascio", pattern_file="* - 20* Resoconto *.md"),
               Campo("allegati", "Allegati extra", "file_rilascio", pattern_file="*.pdf", obbligatorio=False)),
        ricarica=("*.msg",)),
    _az(id="prepara_firma", titolo="Prepara cartella firma", descrizione="PDF per Arcipelago in 'da mandare in firma/' (Word)",
        ambito="Collaudo", argomenti=(str(S / "leviathadm_cli.py"), "prepara-firma", "{codice}", "--lettera", "{lettera}"),
        richiede=frozenset({"word"}), campi=(Campo("lettera", "Lettera", "scelta", opzioni=tuple(LETTERE)),)),
]}


def per_ambito(ambito: str) -> list[Azione]:
    if ambito == "globale":
        return [a for a in CATALOGO.values() if a.ambito == "globale"]
    return [a for a in CATALOGO.values() if a.ambito != "globale"]


def disponibile(azione: Azione, *, master: bool, deps: set[str]) -> str | None:
    """Motivo dell'indisponibilità, o None se l'azione si può lanciare qui e ora."""
    if azione.richiede_master and not master:
        return "solo sul master (PC-DEMO)"
    richieste = azione.richiede | (azione.richiede_sul_master if master else frozenset())
    mancanti = [_MOTIVI[d] for d in sorted(richieste) if d not in deps]
    return "; ".join(mancanti) or None


def _espandi(argomenti: tuple[str, ...], ctx: dict) -> list[str]:
    """"{nome}" → ctx[nome]; "{+nome:--flag}" → "--flag=v1 --flag=v2" (forma con = : un valore che inizia
    con "-" non viene letto come opzione; flag vuoto = solo i valori). Una stringa vale come lista di uno.
    Segnaposto senza valore: KeyError (bug, non input utente)."""
    out: list[str] = []
    for a in argomenti:
        if a.startswith("{+") and a.endswith("}"):
            nome, _, flag = a[2:-1].partition(":")
            valori = ctx[nome]
            for v in ([valori] if isinstance(valori, str) else valori):
                out.append(f"{flag}={v}" if flag else str(v))
        elif a.startswith("{") and a.endswith("}"):
            out.append(str(ctx[a[1:-1]]))
        else:
            out.append(a)
    return out


def comando(azione: Azione, ctx: dict) -> list[str]:
    """[python, -X, utf8] + argomenti risolti; per le azioni in due passi è il PRIMO passo (anteprima)."""
    return [sys.executable, "-X", "utf8"] + _espandi(azione.argomenti + azione.anteprima, ctx)


def comando_applica(azione: Azione, ctx: dict) -> list[str]:
    """Secondo passo di un'azione in due passi: argomenti + applica (mai l'anteprima)."""
    return [sys.executable, "-X", "utf8"] + _espandi(azione.argomenti + azione.applica, ctx)
