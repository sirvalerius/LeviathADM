# SCHEMA — Contratto del formato dati del vault

Il vault markdown **è** il database. Due consumatori: **LeviathADM** (lato umano, via `leviathadm/vault`) e **Claude Code** (lato AI, lettura diretta + script). Questo file è il contratto: chi tocca il formato aggiorna anche questo documento.

**Regola del writer unico:** ogni scrittura di frontmatter passa da `scripts/mail_utils.py → update_frontmatter_keys()` (preserva ordine righe, chiavi non censite e corpo). `leviathadm/vault/writers.py` la importa; nessun altro writer è ammesso. Il corpo dei resoconti e del Verbale di Collaudo viene riscritto da LeviathADM **solo per le sezioni modificate** (`writers.salva_sezioni`); le sezioni in forma non standard restano testo grezzo.

---

## Scheda rilascio — `PO 2026/ADMxxx-xx-xX/ADMxxx-xx-xX.md`

### Frontmatter

| Campo | Formato | Note |
|---|---|---|
| `codice_rilascio` | `ADMxxx-xx-xX` | chiave primaria (= nome cartella e file) |
| `codice_sottoprogetto` | `ADMxxx-xx` | |
| `codice_progetto` | `ADMxxx` | |
| `descrizione_progetto` / `descrizione_sottoprogetto` / `descrizione_rilascio` | testo | mai inventarle: fonte Excel PO |
| `stato` | uno di: `Da Avviare`, `Bozza`, `Startup`, `In corso`, `Analisi`, `In Verifica`, `Collaudo`, `Concluso` | |
| `pm`, `ra`, `rp` | `Nome Cognome` (rp può essere doppio: `X - Y`) | |
| `struttura_business` | sigla direzione (es. `DGIO`) | |
| `referente_business`, `referente_sogei` | `Nome Cognome` | referente_sogei sempre primo nella lista SOGEI dei resoconti |
| `vincoli_normativi` | `Sì` / `No` | |
| `data_fine_analisi`, `data_collaudo_prevista`, `data_collaudo_effettiva`, `data_rilascio_prevista`, `data_rilascio_effettiva`, `data_disponibilita_collaudo` | ISO `AAAA-MM-GG` | `data_disponibilita_collaudo` fa scattare la scadenza tassativa +20gg in `build_scadenze.py`. `data_collaudo_effettiva` è scritto da `build_da_collaudare.py` (colonna compilabile in `Da collaudare.md`), non più solo a mano |
| `protocollo_analisi`, `protocollo_approvazione_analisi`, `protocollo_collaudo`, `protocollo_estensione_esercizio`, `protocollo_disponibilita_collaudo` | `N del GG/MM/AAAA (Registro …)` — opz. `; rif. SOGEI NNNNN/RU del GG/MM/AAAA` | stringa unica; registri: Contratto/ingresso (analisi, disponibilità), Ufficiale/uscita (approvazione). `DA COMPLETARE` marca i dati mancanti |
| `codice_rilascio_precedente` | `ADMxxx-xx-xX` | sulla scheda **nuova**: punta al codice storico da cui si è rinominata (v. procedura sotto) |
| `codice_rilascio_successivo` | `ADMxxx-xx-xX` | sulla scheda **vecchia** (stato `Rinominato`, anche nel senso di "confluenza"): punta al nuovo codice |
| `nota_variazione_date` | testo libero, es. `30/11 → 31/08 (collaudo)` | opzionale: quando le date correnti (`data_collaudo_prevista`/`data_rilascio_prevista`) divergono dal PO originario, annotarlo qui — `build_rilasci.py` lo riporta verbatim in colonna "Var. date"; se vuoto la colonna resta vuota, nessun calcolo automatico (il dato originario non è altrimenti tracciato) |
| `trasmissione_verbale_in_firma`, `trasmissione_verbale_protocollata`, `estensione_esercizio_in_firma`, `estensione_esercizio_protocollata` | `true`/assente | `build_da_firmare` (checkbox in `Da firmare.md`) — **mai a mano**. Tracciano il workflow Arcipelago a due step (vedi `Manuale protocollo/`) per le lettere di fine collaudo; indipendenti da `protocollo_collaudo`/`protocollo_estensione_esercizio`, che restano il numero di protocollo reale da popolare a parte quando arriva |

### Rinumerazione di un punto di piano (SOGEI/ADM cambia il codice)

Capita che SOGEI o ADM rinumerino un punto di piano già avviato (es. `ADM953-01-0N` → `ADM998-01-0N`), tipicamente comunicato via email con la vecchia numerazione tra parentesi nell'oggetto. **La cartella vecchia non si sposta né si rinomina** — resta al suo posto come archivio storico; si crea una cartella nuova per il seguito. Procedura:

1. **Cartella vecchia** (`PO 2026/<vecchio>/`): resta ferma, con tutto il suo contenuto storico (`inviati/`, `_fonti/`, trascritti) intatto — sono documenti realmente scambiati con quel codice, non si toccano. Nella sua scheda: `stato: Rinominato`, aggiungere `codice_rilascio_successivo: <nuovo>`, nota `>` in testa che segnala la rinumerazione con data e wikilink al nuovo codice, e marcare le sezioni Riunioni/Azioni come storiche (chiuse).
2. **Cartella nuova** (`PO 2026/<nuovo>/`, da creare): scheda fresca con `codice_rilascio_precedente: <vecchio>`, gli stessi dati di Team/date correnti (ereditati dalla vecchia scheda), tabella Riunioni che riparte dalla prossima fase (non duplicare le riunioni storiche in tabella — restano sulla vecchia scheda, richiamate con nota e wikilink), e le sole azioni/decisioni **correnti** (es. un documento appena arrivato già col nuovo codice va salvato qui, non nella cartella vecchia). **Duplicare anche i file**: copiare (non spostare) tutto il contenuto non-scheda della cartella vecchia in una sottocartella `_storico <vecchio>/` dentro quella nuova, così la storia documentale completa è consultabile insieme ai documenti correnti senza saltare tra cartelle — la vecchia cartella resta comunque la fonte storica ufficiale, invariata.
3. **Verificare se cambiano anche le descrizioni** di progetto/sottoprogetto (una rinumerazione può accompagnare uno scorporo/riorganizzazione, non solo un cambio di sigla) — chiedere a RA/business, non inventare; nel frattempo la scheda nuova eredita le descrizioni della vecchia con una nota di verifica.
4. **Pagine manuali da correggere a mano**: `Riunioni.md`, `Rilasci.md` — riga vecchia con "Rinominato → [[nuovo]]", riga nuova per il seguito. Le pagine **generate** (`Bozze da inviare.md`, `Scadenze.md`) si autocorreggono al prossimo `build_bozze.py`/`build_scadenze.py` (via sync) — non editarle.
5. Se esistono nodi `Progetti/<vecchio progetto>.md` o `Sottoprogetti/<vecchio sottoprogetto>.md`, valutare se creare gli equivalenti nuovi (dipende dall'esito del punto 3).
6. `stato: Rinominato` è un valore aggiuntivo rispetto agli stati standard (`Da Avviare` … `Concluso`) — riservato esclusivamente a questo caso; riconosciuto da `LeviathADM/markdown_db.py` (`stati_validi`).

### Sezioni body (heading `##` stabili — i parser le cercano per nome esatto)

| Sezione | Formato | Parser |
|---|---|---|
| `## Team` | tabella `Ruolo | Nome` + riga `**SOGEI:** …` | solo lettura umana (duplica il frontmatter) |
| `## Riunioni` | tabella `Data | Fase | Trascritto | Resoconto | Inviato` — Data ISO, Resoconto `[[wikilink]]` (o `—` se la riunione non ha ancora un resoconto), Inviato `✅`/`❌`. LeviathADM ("Carica fonti") completa la colonna Trascritto solo se vuota, o aggiunge la riga | `markdown_db._parse_table`, script archiviazione, `leviathadm.vault.writers` |
| `## Azioni aperte` | checkbox `- [ ]` / `- [x]`, testo libero con `[[wikilink]]` | `markdown_db._parse_azioni` |
| `## Documenti di analisi` | tabella + note libere | solo lettura |
| `## Decisioni chiave` | bullet `- AAAA-MM-GG — testo` | `markdown_db._parse_decisioni` |
| `## Prossima riunione` | testo libero (una riga) | `markdown_db` |
| `## Allegati protocolli` | tabella `Tipo | Documento | Prot. ADM n. | Data prot. ADM | Rif. SOGEI | Registro`, una riga per tipo | `markdown_db._parse_table`; generata da `build_project_pages.py` |

Convenzione tabelle: riga heading + riga separatore `---` + righe dati; i parser saltano le prime due.

---

## Resoconto — `ADMxxx-xx-xX - AAAAMMGG Resoconto <Tipo>.md`

Posizione: root del rilascio finché non inviato, poi `inviati/`.

| Campo frontmatter | Formato | Scritto da |
|---|---|---|
| `codice_rilascio` | `ADMxxx-xx-xX` | compilazione |
| `tipo_riunione` | `Startup` / `Prima Analisi` / `SAL n` / `Collaudo` | compilazione |
| `data_riunione`, `data_compilazione` | ISO | compilazione / `rigenera_resoconto.py` |
| `compilato_da`, `approvato_da` | testo | compilazione |
| `inviato` | `true`/assente | `archivia_inviati` (checkbox in Bozze da inviare.md, o "Segna inviato" in LeviathADM) |
| `data_scadenza_approvazione` | ISO (+5gg lavorativi dall'invio) | `archivia_inviati` — **mai a mano** |
| `data_approvazione` | ISO | `chiudi_approvazione` (o LeviathADM "Chiudi approvazione": solo questa chiave, PDF e `.msg` al sync del master) |
| `definitivo_inviato` | `true`/assente | `archivia_inviati` |
| `salta_definitivo` | `true`/assente | manuale — esclude il resoconto dalla generazione automatica del definitivo (`chiudi_approvazione`), es. per rilasci con `stato: Concluso` per cui non ha senso un ulteriore invio di validazione |

Sezioni body: `OBIETTIVO`, `LISTA PARTECIPANTI`, `OBIETTIVO DELLA RIUNIONE`, `ARGOMENTI TRATTATI`, `AZIONI CONCORDATE` (o `ESITO` per il collaudo — è ciò da cui `rigenera_resoconto.py` riconosce il tipo).

## Verbale di collaudo — `ADMxxx-xx-xX - AAAAMMGG Verbale di Collaudo.md`

Generato da `genera_convocazione_collaudo`; campo chiave `esito_collaudo` (`POSITIVO` / `con riserva` / `NEGATIVO`) + sezione Esito complessivo.

---

## Chi legge / chi scrive

| Consumatore | Lettura | Scrittura |
|---|---|---|
| Script vault (`scripts/*.py`) | `mail_utils.parse_frontmatter` | `mail_utils.update_frontmatter_keys` |
| LeviathADM (`leviathadm/vault/loader.py`, `resoconti.py`, `writers.py`) | `mail_utils.parse_frontmatter` + `leviathadm.vault.parsers` + `leviathadm.vault.resoconti` (resoconti e Verbale a sezioni) | `leviathadm.vault.writers` → `mail_utils.update_frontmatter_keys` (frontmatter) e `salva_sezioni` (solo le sezioni cambiate), sempre con guardia sull'mtime del file; `rigenera_docx` riusa `rigenera_resoconto`/`fill_template` |
| Claude Code | lettura diretta dei file | modifiche manuali conformi a questo schema, o via script |

Pagine **generate** (mai editare a mano, tranne la colonna "Data collaudo effettiva" di `Da collaudare.md`, pensata apposta per la compilazione manuale): `PO 2026/Bozze da inviare.md` (`build_bozze.py`), `PO 2026/Scadenze.md` (`build_scadenze.py`), `PO 2026/Da firmare.md` (`build_da_firmare.py`), `PO 2026/Da collaudare.md` (`build_da_collaudare.py`). LeviathADM le rende come viste native (`leviathadm/vault/cruscotto.py`) riusando i `collect_*` di quegli script, e scrive le stesse chiavi di frontmatter tramite `leviathadm.vault.writers`.

`build_da_firmare.py` popola anche, per ogni lettera appena pronta, `PO 2026/<rilascio>/da mandare in firma/<Lettera>/` con i PDF da caricare su Arcipelago (documento principale + resoconto di collaudo + documento di analisi protocollato con i suoi allegati, per la Trasmissione; solo il documento principale per la Richiesta estensione) — vedi `prepara_firma.py`. Cartella **generata**, idempotente (non la ricrea se già popolata).
