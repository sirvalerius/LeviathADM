"""sync.py — allinea questo PC allo stato corrente del vault.

È il comando unico su qualsiasi macchina (lanciato anche da sync.cmd):

  1. git pull --rebase --autostash   — recepisce tutto quanto fatto altrove
  2. (solo master) archivia_inviati + build_bozze + build_scadenze
  3. sync_bozze_folder               — ricostruisce la cartella locale
                                       "Bozze da inviare/" (hardlink,
                                       gitignorata) e rimuove i file stantii
  4. commit automatico delle modifiche locali (messaggio = argomenti CLI
     oppure "Aggiornamento AAAA-MM-GG HH:MM") e git push
  5. riepilogo                       — ruolo macchina, bozze/definitivi in attesa

La rete è gestita automaticamente: se il proxy ADM configurato nel repo non è
raggiungibile (PC fuori dalla rete ADM), pull e push vengono ritentati in
connessione diretta. Se un comando di rete fallisce per un problema di proxy e
il sync gira in modalità interattiva, viene proposto di riprovare tutto ([R])
o di cambiare la password del proxy ([P], aggiorna http.proxy e riesegue). In
esecuzione automatica (Task Scheduler) nessun prompt: si registra il pending.

File aperti (Word/Outlook) al momento del sync non fanno perdere aggiornamenti:
le operazioni non applicabili vengono registrate in .sync_pending.json
(locale, gitignorato) e completate alla riesecuzione successiva, a file chiusi.
Se il pull si interrompe a metà rebase, lo stato precedente viene ripristinato
automaticamente (git rebase --abort): nessuna modifica locale va persa.

Uso:
    python scripts/sync.py
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent))

# Console Windows in cp1252: evita il crash UnicodeEncodeError quando un
# print (anche di un modulo chiamato: archivia_inviati, build_*, ...) contiene
# frecce/emoji (→ ❌ ✅ 🚨). errors="replace" degrada a "?" invece di crashare.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import machine_config
import sync_bozze_folder
from mail_utils import parse_frontmatter

VAULT = Path(__file__).parent.parent
PENDING_FILE = VAULT / ".sync_pending.json"
LAVORI = VAULT / "PO 2026"


def _conta_progetti_attivi_per_anno() -> list[tuple[int, int]]:
    """Progetti attivi (stato != Rinominato) in PO <anno corrente> e, se
    presente e non vuota, PO <anno precedente>.
    ponytail: solo questo conteggio è anno-aware, le altre ~15 build_*.py
    restano su "PO 2026" fisso — generalizzarle tutte è un refactor più
    grosso, da fare quando si crea davvero PO 2027."""
    risultati = []
    anno_corrente = datetime.now().year
    for anno in (anno_corrente, anno_corrente - 1):
        cartella = VAULT / f"PO {anno}"
        if not cartella.is_dir():
            continue
        n = 0
        for d in cartella.glob("ADM*"):
            if not d.is_dir() or "(" in d.name:
                continue
            scheda = d / f"{d.name}.md"
            if not scheda.exists():
                continue
            fm = parse_frontmatter(scheda)
            if fm.get("stato", "").strip().lower() != "rinominato":
                n += 1
        if n:
            risultati.append((anno, n))
    return risultati


def _count_section_rows(path: Path, heading: str) -> int:
    """Conta le righe dati (tabella '|...|' o checkbox '- [ ]') di una sezione
    '## heading' fino al prossimo '---' o '## '. Ignora intestazione/separatore
    tabella e il placeholder '_Nessuna/Nessuno/Nessuna lettera..._'."""
    if not path.exists():
        return 0
    in_section = False
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("## "):
            if heading in s:
                in_section = True
                continue
            if in_section:
                break
        if not in_section:
            continue
        if s == "---":
            break
        if not s or s.startswith("_") or set(s) <= {"-", "|", " "} or "_Nessun" in s:
            continue
        if s.startswith("|") and ("Rilascio" in s or "Tipo" in s):
            continue
        if s.startswith("- [ ]") or s.startswith("|"):
            count += 1
    return count


def _print_reminder_finale() -> None:
    tassative = _count_section_rows(LAVORI / "Scadenze.md", "Tassative")
    da_collaudare = _count_section_rows(LAVORI / "Da collaudare.md", "Punti da collaudare")
    da_firmare = _count_section_rows(LAVORI / "Da firmare.md", "Da mandare in firma")
    in_firma = _count_section_rows(LAVORI / "Da firmare.md", "In firma")
    righe = []
    if tassative:
        righe.append(f"  🚨 {tassative} scadenza/e TASSATIVA/E di convocazione collaudo — Scadenze.md")
    if da_collaudare:
        righe.append(f"  🧪 {da_collaudare} punt{'o' if da_collaudare==1 else 'i'} in attesa di collaudo — Da collaudare.md")
    if da_firmare:
        righe.append(f"  ✍️  {da_firmare} lettera/e da mandare in firma — Da firmare.md")
    if in_firma:
        righe.append(f"  📮 {in_firma} lettera/e in firma, in attesa di protocollazione — Da firmare.md")
    for anno, n in _conta_progetti_attivi_per_anno():
        righe.append(f"  📁 {n} progett{'o' if n==1 else 'i'} attiv{'o' if n==1 else 'i'} in PO {anno}")
    if righe:
        print("\nPromemoria:")
        print("\n".join(righe))


def _load_pending() -> dict:
    if PENDING_FILE.is_file():
        try:
            return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def _save_pending(pending: dict) -> None:
    if pending:
        pending["aggiornato"] = datetime.now().isoformat(timespec="seconds")
        PENDING_FILE.write_text(
            json.dumps(pending, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    elif PENDING_FILE.exists():
        PENDING_FILE.unlink()


def _recover_interrupted_rebase() -> None:
    """Se il pull ha lasciato un rebase a metà (es. file tracciato aperto in
    Word), ripristina lo stato precedente: i commit e le modifiche locali
    restano intatti e il pull verrà ritentato al prossimo sync."""
    git_dir = VAULT / ".git"
    if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
        print("   Rebase interrotto a metà: ripristino lo stato precedente...")
        r = _git(["rebase", "--abort"])
        if r.returncode == 0:
            print("   Stato ripristinato — nessuna modifica locale persa.")
        else:
            print(f"   ATTENZIONE: ripristino non riuscito, verifica a mano:\n{r.stderr}")


def _git(args: list[str], no_proxy: bool = False) -> subprocess.CompletedProcess:
    # In rete ADM (via proxy) la SSL inspection rompe la verifica dei
    # certificati: sslVerify viene disattivato solo in quella modalità.
    # In connessione diretta la verifica SSL resta attiva.
    extra = ["-c", "http.proxy="] if no_proxy else ["-c", "http.sslVerify=false"]
    return subprocess.run(["git"] + extra + args, cwd=VAULT,
                          capture_output=True, text=True)


_NO_PROXY: bool | None = None  # deciso una volta per esecuzione


def _proxy_irraggiungibile() -> bool:
    """True se il repo ha un http.proxy configurato che ora non risponde
    (PC fuori dalla rete ADM): in quel caso tutti i comandi di rete
    vanno eseguiti in connessione diretta."""
    import re
    r = _git(["config", "--get", "http.proxy"])
    proxy = (r.stdout or "").strip()
    if not proxy:
        return False
    m = re.match(r"(?:https?://)?(?:[^@/]+@)?([^:/]+)(?::(\d+))?", proxy)
    if not m:
        return False
    host, port = m.group(1), int(m.group(2) or 80)
    try:
        socket.create_connection((host, port), timeout=3).close()
        return False
    except OSError:
        print(f"   (proxy {host} non raggiungibile: connessione diretta)")
        return True


def _vault_in_git() -> bool:
    """True solo se la radice del vault è la radice di un repository git: un vault dentro un'altra cartella
    versionata (es. pack scompattato in un repo) non deve far committare quel repo. Brezza git il sync fa
    solo il ricalcolo locale (spec fase 5 §4.3: versione web e pack autonomi)."""
    # Decide la presenza di `.git` nella radice, non l'esito di un comando git: un git rotto o assente dal PATH
    # deve fallire al pull come sempre, non far scattare il ricalcolo locale (che sugli slave è riservato al master).
    return (VAULT / ".git").exists()


def _git_net(args: list[str]) -> subprocess.CompletedProcess:
    """Comando git di rete. Sceglie la modalità (proxy/diretta) testando il
    proxy una volta sola; in caso di errore che sembra di rete/proxy ritenta
    con la modalità opposta, così il sync funziona sia dentro che fuori dalla
    rete ADM. Un errore locale (file bloccato, conflitto, ecc.) non ha nulla
    a che vedere col proxy: ritentarlo con l'altra modalità raddoppierebbe
    l'operazione fallita e travestirebbe la causa reale da problema di rete."""
    global _NO_PROXY
    if _NO_PROXY is None:
        _NO_PROXY = _proxy_irraggiungibile()
    r = _git(args, no_proxy=_NO_PROXY)
    if r.returncode != 0 and _looks_like_proxy_problem(r):
        print(f"   (tentativo {'diretto' if _NO_PROXY else 'via proxy'} fallito, "
              f"riprovo {'via proxy' if _NO_PROXY else 'in connessione diretta'})")
        r2 = _git(args, no_proxy=not _NO_PROXY)
        if r2.returncode == 0:
            _NO_PROXY = not _NO_PROXY
        return r2
    return r


def _looks_like_proxy_problem(r: subprocess.CompletedProcess) -> bool:
    s = ((r.stderr or "") + (r.stdout or "")).lower()
    return any(k in s for k in (
        "proxy", "407", "could not resolve", "failed to connect",
        "authentication", "authenticat",
    ))


def _diag(r: subprocess.CompletedProcess) -> str:
    """Dettaglio diagnosticabile di un comando git fallito: tutte le righe
    error:/fatal: (la causa reale è spesso una di quelle, non l'ultima riga),
    o l'ultima riga di stderr se nessuna corrisponde."""
    lines = (r.stderr or "").strip().splitlines()
    relevant = [l for l in lines if l.strip().lower().startswith(("error:", "fatal:"))]
    if relevant:
        return "\n".join(relevant)
    return lines[-1] if lines else "?"


def _set_proxy_password(new_pwd: str) -> bool:
    """Aggiorna la password nell'URL di http.proxy (scope locale), preservando
    utente/host/porta. La password viene percent-encoded automaticamente."""
    proxy = (_git(["config", "--get", "http.proxy"]).stdout or "").strip()
    if not proxy:
        print("   Nessun http.proxy configurato: niente da aggiornare.")
        return False
    m = re.match(r"^(?P<scheme>https?://)?(?P<user>[^:@/]+)(?::[^@/]*)?@(?P<rest>.+)$", proxy)
    if not m:
        print("   Formato proxy senza utente/@: aggiorna a mano con `git config http.proxy ...`.")
        return False
    scheme = m.group("scheme") or "http://"
    new_url = f"{scheme}{m.group('user')}:{quote(new_pwd, safe='')}@{m.group('rest')}"
    w = _git(["config", "http.proxy", new_url])
    if w.returncode == 0:
        print(f"   Password proxy aggiornata per {m.group('user')}@{m.group('rest')}.")
        return True
    print(f"   Aggiornamento non riuscito: {(w.stderr or w.stdout).strip()}")
    return False


def _handle_proxy_failure(context: str) -> bool:
    """In modalità interattiva, su un problema di rete via proxy offre di
    riprovare tutto [R] o cambiare la password del proxy [P].
    Ritorna True se il sync va rieseguito da capo (il chiamante fa il restart)."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False  # esecuzione automatica (Task Scheduler): nessun prompt
    print(f"\n   ATTENZIONE: problema di connessione tramite proxy ({context}).")
    while True:
        scelta = input("   [R] riprova tutto · [P] cambia password proxy · [Invio] continua: ").strip().lower()
        if scelta == "p":
            nuova = getpass("   Nuova password proxy: ")
            if not nuova:
                print("   Password vuota, annullato.")
                continue
            if _set_proxy_password(nuova):
                return True
            continue
        if scelta == "r":
            return True
        return False


def _restart() -> None:
    """Riesegue interamente il sync (stessi argomenti), ripartendo dal pull."""
    print("\n   Riavvio del sync...\n")
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve())] + sys.argv[1:])


def _rigenera_docx_superati(pending: dict) -> None:
    """(master) Bozze il cui .md è più recente del .docx — tipicamente modificate dalla versione web, che non può
    rigenerare Word — vengono rigenerate qui (DATA COMPILAZIONE = oggi, .msg rimosso e poi rigenerato dal sync)."""
    try:
        import build_bozze
        import rigenera_resoconto
        superate = [b for b in build_bozze.collect_bozze() if b.get("docx_superato")]
    except Exception as e:
        print(f"   ERRORE rigenera_docx (ricerca): {e} — proseguo")
        pending.setdefault("step_falliti", []).append({"step": "rigenera_docx", "errore": str(e)})
        return
    for b in superate:
        md = build_bozze.LAVORI / b["codice"] / f"{b['stem']}.md"
        try:
            rigenera_resoconto.rigenera(md)
            print(f"   .docx rigenerato (md più recente): {b['stem']}")
        except Exception as e:
            print(f"   ERRORE rigenera_docx {b['stem']}: {e} — proseguo")
            pending.setdefault("step_falliti", []).append({"step": "rigenera_docx", "errore": f"{b['stem']}: {e}"})


def _chiudi_approvazioni_app(pending: dict) -> None:
    """Completa (PDF + .msg definitivo) le approvazioni tacite segnate da LeviathADM, una per una:
    un errore (Word/Outlook) non blocca le altre e finisce in step_falliti."""
    try:
        import chiudi_approvazione
        incompleti = chiudi_approvazione.find_approvati_incompleti()
    except Exception as e:
        print(f"   ERRORE chiudi_approvazione: {e} — proseguo")
        pending.setdefault("step_falliti", []).append({"step": "chiudi_approvazione", "errore": str(e)})
        return
    for md in incompleti:
        print(f"   Chiusura approvazione: {md.name}")
        try:
            chiudi_approvazione.chiudi(md)
        except Exception as e:
            print(f"   ERRORE chiudi_approvazione {md.name}: {e} — proseguo")
            pending.setdefault("step_falliti", []).append({"step": "chiudi_approvazione", "errore": f"{md.name}: {e}"})


def main() -> None:
    args = sys.argv[1:]

    if "--change-proxy-password" in args:
        nuova = getpass("Nuova password proxy: ")
        sys.exit(0 if (nuova and _set_proxy_password(nuova)) else 1)

    pull_only = "--pull-only" in args
    push_only = "--push-only" in args
    msg_args = [a for a in args if not a.startswith("--")]

    modo = "pull" if pull_only else "push" if push_only else "completo"
    print(f"=== Sync vault — {socket.gethostname()} "
          f"(ruolo: {machine_config.get_role()} · modo: {modo}) ===\n")

    senza_git = not _vault_in_git()
    if senza_git:
        print("Vault senza git: solo ricalcolo locale (niente pull/push); pagine e derivati rigenerati qui.\n")

    prev = _load_pending()
    if prev:
        n = len(prev.get("file_bloccati", [])) or "alcune"
        print(f"Dal sync precedente ({prev.get('aggiornato', '?')}) erano rimaste "
              f"{n} operazioni in sospeso — le riprovo ora.\n")
    pending: dict = {}

    pull_fallito = False
    if not push_only and not senza_git:
        print("1. git pull --rebase --autostash...")
        r = _git_net(["pull", "--rebase", "--autostash"])
        if r.returncode != 0:
            pull_fallito = True
            _recover_interrupted_rebase()
            if _looks_like_proxy_problem(r) and _handle_proxy_failure("pull"):
                _restart()
            pending["pull_fallito"] = _diag(r)
            print("   Pull non riuscito — verrà ritentato al prossimo sync. "
                  "Se l'errore cita file in uso, chiudi Word/Outlook e rilancia.")
            print(f"   Dettaglio: {pending['pull_fallito']}")
        else:
            out = (r.stdout or "").strip()
            print(f"   {out.splitlines()[-1] if out else 'OK'}")

    if not pull_only and not push_only:
        print("\n2. Archiviazione...")
        import archivia_inviati
        try:
            archivia_inviati.main()
        except Exception as e:
            print(f"   ERRORE archivia_inviati: {e} — proseguo")
            pending.setdefault("step_falliti", []).append({"step": "archivia_inviati", "errore": str(e)})

        if machine_config.is_master() or senza_git:   # senza git non c'è un master: il ricalcolo è tutto locale
            _chiudi_approvazioni_app(pending)
            _rigenera_docx_superati(pending)
            print("   Rigenerazione pagine (master)..." if not senza_git else "   Rigenerazione pagine (ricalcolo locale)...")
            import build_bozze
            import build_scadenze
            import build_stato_invii
            import build_rilasci
            import build_riunioni
            import build_da_collaudare
            import build_da_firmare
            for nome, fn in (("build_bozze", build_bozze.build),
                             ("build_scadenze", build_scadenze.build),
                             ("build_stato_invii", build_stato_invii.build),
                             ("build_rilasci", build_rilasci.build),
                             ("build_riunioni", build_riunioni.build),
                             ("build_da_collaudare", build_da_collaudare.build),
                             ("build_da_firmare", build_da_firmare.build)):
                try:
                    fn()
                except Exception as e:
                    print(f"   ERRORE {nome}: {e} — proseguo")
                    pending.setdefault("step_falliti", []).append({"step": nome, "errore": str(e)})

    if not push_only:
        print("\n3. Ricostruisco Bozze da inviare/ ...")
        blocked = sync_bozze_folder.sync()
        if blocked:
            pending["file_bloccati"] = blocked

    if not pull_only and not senza_git:
        print("\n4. Commit e push delle modifiche locali...")
        if _git(["status", "--porcelain"]).stdout.strip():
            msg = " ".join(msg_args).strip()
            if not msg:
                from datetime import datetime as _dt
                msg = f"Aggiornamento {_dt.now():%Y-%m-%d %H:%M}"
            _git(["add", "-A"])
            r = _git(["commit", "-m", msg])
            if r.returncode == 0:
                print(f"   Commit: \"{msg}\"")
            else:
                print(f"   Commit non riuscito: {(r.stderr or r.stdout).strip()}")
        else:
            print("   Nessuna modifica locale da committare.")

        ahead = _git(["rev-list", "--count", "@{u}..HEAD"]).stdout.strip()
        if pull_fallito and ahead and ahead != "0":
            print("   Push saltato: il pull precedente non è riuscito, quindi il "
                  "remoto ha commit che manca ancora in locale — il push non "
                  "potrebbe comunque avanzare veloce. Verrà ritentato al prossimo sync.")
        elif ahead and ahead != "0":
            r = _git_net(["push"])
            if r.returncode != 0:
                if _looks_like_proxy_problem(r) and _handle_proxy_failure("push"):
                    _restart()
                pending["push_fallito"] = _diag(r)
                print("   Push non riuscito — i commit restano locali e verranno "
                      "pubblicati al prossimo sync.")
                print(f"   Dettaglio: {pending['push_fallito']}")
            else:
                print(f"   Push OK ({ahead} commit pubblicati).")
        else:
            print("   Nessun commit da pubblicare.")

    n_bozze = len(list(sync_bozze_folder.DIR_BOZZE.glob("*.*")))
    n_def = len(list(sync_bozze_folder.DIR_DEFINITIVI.glob("*.*")))
    print(f"\n5. Riepilogo: Bozze da inviare/ → {n_bozze} file in Bozze iniziali/ "
          f"· {n_def} in Definitivi/.")

    _print_reminder_finale()

    _save_pending(pending)
    if pending:
        print(f"\n=== Sync completato CON RISERVE — dettagli in {PENDING_FILE.name}: "
              "chiudi i file aperti e rilancia `python scripts/sync.py` ===")
        sys.exit(1)
    if prev:
        print("\nLe operazioni rimaste in sospeso sono state completate.")
    print("\n=== Sync completato ===")


if __name__ == "__main__":
    main()
