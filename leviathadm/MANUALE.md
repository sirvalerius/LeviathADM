# Manuale di LeviathADM

LeviathADM è il cruscotto del Piano Operativo (PO): legge e scrive direttamente i file markdown del vault Obsidian ("PO 2026/", "Anagrafica/") e non ha un database. Esiste in due versioni con le stesse regole:

| Versione | Come si avvia | Quando usarla |
|---|---|---|
| **Python** (dashboard locale) | `leviathadm.cmd` nella radice del vault, poi `http://127.0.0.1:8080` | PC con Python: tutte le funzioni, comprese le azioni che lanciano gli script (convocazioni, sync, Word, Outlook) |
| **Web** (`leviathadm.html`) | doppio clic sul file in Edge o Chrome, poi "Apri cartella" | PC senza Python: lettura e scrittura del vault nel browser, nessuna installazione |

Questo manuale è lo stesso nelle due versioni: le differenze sono indicate dove servono e riassunte in fondo.

**Regola che vale sempre:** l'applicazione **non invia mai una mail**. Produce solo bozze (`.msg` per i resoconti, `.eml` per le convocazioni) che si aprono in Outlook e si inviano a mano.

---

## Avvio

**Versione Python.** `leviathadm.cmd` crea l'ambiente virtuale `.venv/` al primo avvio, installa i requisiti, verifica pacchetti, Outlook, Word, pandoc, ruolo del PC e porta, poi apre il server su `http://127.0.0.1:8080`. Opzioni: `--check` (solo verifiche), `--porta N` (altra porta). L'app va avviata da una console propria e fermata con Ctrl+C. Nel pack demo `leviathadm.cmd` usa il Python embedded della cartella `python/`.

**Versione Web.** Aprire `leviathadm.html`, premere **Apri cartella…** e scegliere la cartella del vault (quella che contiene `PO 2026/` e `Anagrafica/`). Il browser chiede il permesso a ogni apertura e non memorizza nulla della cartella scelta. Serve Edge o Chrome (File System Access); se una policy aziendale blocca l'accesso ai file compare un avviso nella schermata iniziale. Il pulsante **⟳** nell'header rilegge tutti i file dal disco.

**Header e menu.** Il menu laterale (☰) elenca le viste; il selettore del **piano** (anno) nell'header sceglie la cartella `PO <anno>/` quando il vault ne contiene più di una; **◐** cambia tema chiaro/scuro. Nella versione Python c'è anche la **ricerca globale** (Ctrl+K) su codici, titoli e testi delle note.

---

## Rilasci

La vista iniziale elenca i punti di piano del piano selezionato: codice, descrizione, stato, PM, RA, RP, collaudo previsto / effettivo, rilascio previsto / effettivo. Le intestazioni ordinano la tabella (per data dove la colonna è una data); i filtri in alto restringono per stato o testo.

Gli **stati** del ciclo di vita, in ordine: Da Avviare, Bozza, Startup, Analisi, In corso, In Verifica, Collaudo, Concluso. Lo stato aggiuntivo **Rinominato** segnala una scheda storica rinumerata o confluita in un altro codice (campo `codice_rilascio_successivo`).

### Dettaglio del rilascio

Un clic sulla riga apre la scheda `ADMxxx-xx-xX.md`:

- **Metadati e team**: codici e descrizioni di progetto, sottoprogetto e rilascio; PM, RA, RP, referente business e struttura, referente SOGEI; vincoli normativi; date; protocolli.
- **Ciclo di vita**: lo stepper delle riunioni (Startup → Prima Analisi → SAL → Collaudo) con, per ogni fase, il resoconto collegato. Lo step **+** crea un nuovo resoconto (vedi "Resoconti").
- **Riunioni, Azioni aperte, Decisioni chiave, Prossima riunione**: le sezioni della scheda. Le azioni con una scadenza (`— scadenza: GG/MM/AAAA`) compaiono anche in Scadenze.
- **Allegati protocolli**: la tabella dei documenti protocollati (analisi, approvazione, disponibilità a collaudo, collaudo, estensione).
- **Modifica scheda**: modulo con i campi del frontmatter. Si salvano **solo le chiavi cambiate**; le date si normalizzano in ISO; `DA COMPLETARE` è ammesso dove un dato non è ancora noto.
- **Azioni** (solo Python): Carica fonti, Convocazione startup, Convocazione collaudo, Genera mail resoconto, Prepara cartella firma. Lanciano gli script del vault in un sottoprocesso; l'output compare nel pannello.

### Nuovo punto di piano

Dal menu **Nuovo punto di piano**: codice rilascio, sottoprogetto, descrizioni, ruoli, date. Crea la cartella `PO <anno>/<codice>/` e la scheda nello stesso formato di quelle generate dall'Excel PO. Il codice deve avere la forma `ADMxxx-xx-xX` e non esistere già. I campi persona suggeriscono i nomi dell'Anagrafica e con l'icona a destra creano al volo una nuova persona.

---

## Resoconti

Ogni riunione produce un resoconto `ADMxxx-xx-xX - AAAAMMGG Resoconto <Tipo>.md` nella cartella del rilascio (la **bozza**); dopo l'invio i file passano in `inviati/`.

### Nuovo resoconto

Dallo step **+** del ciclo di vita (o dal pulsante "Nuovo resoconto" nella versione Python): si sceglie la fase (uguale o successiva all'ultima già fatta, o un testo libero) e la data. Viene generato lo **scheletro** con le sezioni fisse già compilate dalla scheda e dall'Anagrafica: tabelle RIUNIONE / RESOCONTO / OBIETTIVO, LISTA PARTECIPANTI, formula dell'OBIETTIVO DELLA RIUNIONE; nella scheda viene aggiunta la riga in `## Riunioni` con ❌ (non inviato). Restano da scrivere **ARGOMENTI TRATTATI** e **AZIONI CONCORDATE** (per il collaudo: ESITO, con i casi di test presi dal Verbale).

Nella versione Python i partecipanti possono venire dal **CSV presenze di Teams** caricato con "Carica fonti"; nella versione Web vengono dal team della scheda (la lista va completata a mano).

### Editor a sezioni

Il resoconto si modifica sezione per sezione: partecipanti (selettore con i nomi dell'Anagrafica), argomenti, azioni (una per riga, con responsabile e data), esito del collaudo. Si riscrivono **solo le sezioni cambiate**; `data_riunione`, `approvato_da` e `data_approvazione` restano allineati tra frontmatter e tabelle. Sotto lo stepper del ciclo di vita compare il resoconto della fase scelta: editor inline se è una bozza, sola lettura con il lucchetto se è già inviato.

### Dal markdown al Word

- **Rigenera .docx** produce il documento Word ufficiale dal `.md` con il template giusto (startup/analisi/SAL, collaudo con firme o con approvazione telematica) e imposta DATA COMPILAZIONE a oggi. Nella versione Web il `.docx` non si può generare: la bozza viene marcata ⚠️ "docx superato" e il sync del PC master lo rigenera.
- Il `.msg` (mail con il resoconto allegato) lo genera il **sync** sul PC con Outlook. Non va creato a mano.

### Invio e approvazione tacita

1. Quando la mail è stata inviata davvero, **Segna inviato** (vista "Bozze da inviare"): i file passano in `inviati/`, `inviato: true`, `data_scadenza_approvazione` = +5 giorni lavorativi, ✅ nella scheda.
2. Alla scadenza senza osservazioni il resoconto è approvato tacitamente: **Chiudi approvazione** registra `data_approvazione`; PDF e mail definitiva li completa il sync del master.
3. **Segna definitivo inviato** chiude il ciclo (`definitivo_inviato: true`).

### Riporta in bozza

Per rettificare un resoconto già inviato: **Riporta in bozza** riporta `.md` e `.docx` nella cartella del rilascio, elimina il `.msg` obsoleto, azzera `inviato` e la scadenza, rimette ❌ nella scheda. Si corregge, si rigenera il `.docx` e al prossimo invio si segna di nuovo inviato.

### Verbale di Collaudo

La convocazione del collaudo crea `ADMxxx-xx-xX - AAAAMMGG Verbale di Collaudo.md` con l'elenco delle verifiche. L'editor del Verbale (dal dettaglio rilascio) permette di segnare ogni verifica come superata o non superata, con data, tester e note, e l'esito complessivo (positivo, con riserva, negativo): riepilogo e dettaglio restano allineati. Il resoconto di collaudo prende da qui i casi di test e l'esito.

---

## Cruscotto

Cinque viste, le stesse delle pagine generate in Obsidian, calcolate al volo dai file del vault.

### Scadenze

Quattro sezioni: **Tassative** (convocazione del collaudo entro 20 giorni dalla disponibilità a collaudo: obbligo normativo, con nota "provvisoria" finché il protocollo ADM non è noto), **Scadute**, **Questa settimana**, **Prossime**. Vi compaiono le milestone delle schede (fine analisi, collaudo previsto, rilascio previsto), le azioni aperte con data e le scadenze di approvazione tacita dei resoconti inviati.

### Bozze da inviare

- **Approvazioni tacite scadute**: resoconti inviati oltre la scadenza senza approvazione → Chiudi approvazione.
- **Bozze iniziali**: resoconti pronti nella cartella del rilascio, con lo stato di `.docx` e `.msg` → Segna inviato (chiede conferma se manca il `.msg` e ricorda la scadenza +5 giorni lavorativi).
- **Convocazioni da inviare**: le `.eml` di startup e collaudo → Segna inviata (sposta in `inviati/`).
- **Definitivi**: resoconti approvati di cui manca l'invio della versione definitiva → Segna definitivo inviato.

Un resoconto di collaudo precompilato prima della riunione **non** compare tra le bozze finché la scheda non ha `data_collaudo_effettiva` (vedi "Da collaudare").

### Da collaudare

Punti di piano con disponibilità a collaudo ricevuta e collaudo non ancora svolto. Il campo **Data collaudo effettiva** registra la riunione avvenuta (mai una data futura; conferma richiesta se cade di sabato o domenica) e fa rientrare il resoconto di collaudo nel flusso delle bozze.

### Da firmare

Lettere di fine collaudo (Trasmissione copia verbale · Richiesta estensione in esercizio) presenti nella cartella del rilascio: **da mandare in firma** e **in attesa di protocollazione**. I pulsanti registrano i passaggi (`in_firma`, `protocollata`); nella versione Python "Prepara cartella firma" produce la cartella con i PDF.

### Stato invii

Matrice punti di piano × fase: per ogni resoconto **P** = provvisorio inviato, **D** = definitivo inviato, con il link al file. Sola lettura: gli stati si cambiano da "Bozze da inviare".

---

## Anagrafica

Elenco delle persone del vault (`Anagrafica/<Cognome Nome>.md`) con filtro per nome, organizzazione, direzione e ufficio. **Nuova persona** crea la scheda con organizzazione, direzione, ufficio, email e ruolo tipico; la stessa cosa si può fare al volo dai campi persona di Modifica scheda, Nuovo punto di piano e del selettore dei partecipanti. I nodi delle strutture (direzioni, uffici) stanno in `Anagrafica/Strutture/`.

---

## Azioni e Sync (versione Python)

La pagina **Azioni** raccoglie le operazioni che lanciano gli script del vault: daily check, rigenerazione delle pagine, schede dall'Excel PO, strutture, refresh Anagrafica, audit degli invii, organizzazione delle cartelle Outlook. Ogni pulsante è disabilitato, con il motivo, quando manca un prerequisito (Outlook, Word, pandoc) o quando l'azione è riservata al PC **master**.

Il pulsante **Sync** esegue `scripts/sync.py`: allinea il vault con git, genera i `.msg` mancanti, ricostruisce la cartella locale `Bozze da inviare/`, archivia gli inviati e, sul master, chiude le approvazioni tacite e rigenera i `.docx` superati. **Durante un'azione ogni scrittura dell'app è sospesa** (banner in alto), così nessun file si sposta mentre git lavora. **Log azioni** mostra la cronologia delle esecuzioni.

**Ruoli dei PC.** `scripts/machines.json` assegna a ogni hostname il ruolo master o slave: il master è l'unico che esegue l'automazione mutante; gli slave leggono, scrivono e sincronizzano. **Riavvia backend** (nel menu) riavvia il server in una nuova console.

---

## Regole comuni e casi particolari

- **Conflitti di modifica.** Prima di scrivere, l'app verifica che il file non sia cambiato sul disco da quando lo ha letto (nella versione Web: data di modifica e contenuto). In caso di conflitto compare **Ricarica**: il file viene riletto senza svuotare il modulo, poi si risalva.
- **Fine settimana.** I campi data delle riunioni chiedono conferma se la data cade di sabato o domenica; "Cambia data" svuota il campo.
- **Pausa pranzo.** Le convocazioni non possono iniziare tra le 12:30 e le 14:00.
- **Formato dei file.** I file esistenti conservano i fine riga (CRLF) e l'eventuale BOM; i file nuovi sono in UTF-8 con LF. Il frontmatter si aggiorna chiave per chiave, senza riscrivere il resto.
- **Pagine generate.** Rilasci, Riunioni, Bozze da inviare, Stato invii, Scadenze, Da collaudare e Da firmare in `PO <anno>/` sono prodotte dagli script: le viste dell'app mostrano gli stessi dati, non vanno editate a mano.
- **Contratto dei dati.** Campi, formati e chi legge/scrive ogni sezione sono descritti in `SCHEMA.md`.

---

## Versione Web: differenze

| Funzione | Python | Web |
|---|---|---|
| Lettura di rilasci, resoconti, note, Anagrafica | sì | sì |
| Modifica scheda, Nuovo punto di piano, Nuova persona | sì | sì |
| Nuovo resoconto, editor a sezioni, Verbale, Riporta in bozza | sì | sì (partecipanti dal team, senza CSV presenze) |
| Cruscotto con Segna inviato, Chiudi approvazione, collaudo effettivo, lettere | sì | sì |
| Rigenera .docx, `.msg`, PDF, convocazioni, Carica fonti | sì | no: marcati come superati, li completa il sync del master |
| Azioni, Sync, Log azioni, Riavvia backend, ricerca Ctrl+K | sì | no |
| Requisiti | Python 3.12, Outlook/Word/pandoc per le azioni | Edge o Chrome |

Nella versione Web ogni scrittura passa dalle stesse regole del codice Python (chiavi cambiate, sezioni cambiate, scadenze a +5 giorni lavorativi, ✅/❌ nella scheda), verificate dagli stessi dati di riferimento.
