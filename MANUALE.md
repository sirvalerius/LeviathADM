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

**Versione Web.** Aprire `leviathadm.html`, premere **Apri cartella…** e scegliere la cartella del vault (quella che contiene `PO 2026/` e `Anagrafica/`; dal 2.0.2 il selettore parte dal Desktop, ma non può proporre da solo la cartella in cui sta `leviathadm.html`: il browser non la conosce). Il browser chiede il permesso a ogni apertura e non memorizza nulla della cartella scelta. Serve Edge o Chrome (File System Access); se una policy aziendale blocca l'accesso ai file compare un avviso nella schermata iniziale. Il pulsante **⟳** nell'header rilegge tutti i file dal disco. Dal 1.5.0 la web ricorda l'ultima cartella aperta da quella copia dell'app (handle in IndexedDB, chiave = percorso del file): alla prossima apertura basta «Riapri», il browser richiede solo il permesso; «dimentica» cancella il ricordo (consigliato su PC condivisi: altri file HTML aperti nello stesso browser potrebbero leggere l'handle, ma per usarlo dovrebbero ottenere di nuovo il permesso da te).

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
- **Variazioni di date ed effort** (dal 2.1.0): il registro `## Variazioni` della scheda (data, fase, tipo, da, a, motivo, fonte) e il pulsante **Registra variazione**: scegli la fase (Analisi, Collaudo, Rilascio) e il tipo (Date o Effort), il campo "Da" è precompilato con la data prevista attuale della fase, "A" è il nuovo valore, la fonte propone l'ultimo resoconto. Per le date la scheda aggiorna anche la data prevista della fase (il valore precedente resta nel registro); `Rilasci.md` mostra l'ultima variazione di date nella colonna "Var. date" quando la nota manuale è vuota. I flag VARIAZIONE DATE/EFFORT del resoconto restano a cura del PM (valgono per la singola riunione).
- **Modifica scheda**: modulo con i campi del frontmatter (anagrafica, team, date e i cinque **protocolli**: analisi, approvazione analisi, disponibilità a collaudo, collaudo, estensione esercizio — numero e data del protocollo ADM, `DA COMPLETARE` finché manca il numero; il riferimento SOGEI non è un protocollo ADM). Si salvano **solo le chiavi cambiate**; le date si normalizzano in ISO; `DA COMPLETARE` è ammesso dove un dato non è ancora noto. La tabella "Allegati protocolli" si compila in Obsidian.
- **Carica fonti** (entrambe le versioni): trascritti, CSV presenze e PDF di una riunione in `_fonti/` (vedi "Carica fonti" sotto Resoconti).
- **Convoca startup / Convoca collaudo** (entrambe le versioni): bozza `.eml` con invito calendario (vedi "Convocazioni" sotto Resoconti).
- **Lettere di fine collaudo** (entrambe le versioni): i `.docx` di Trasmissione copia verbale e Richiesta estensione in esercizio compilati dai template (vedi "Lettere di fine collaudo" sotto Resoconti).
- **Azioni** (solo Python): Convocazione startup, Convocazione collaudo, Genera mail resoconto, Prepara cartella firma. Lanciano gli script del vault in un sottoprocesso; l'output compare nel pannello.

### Stato del rilascio

Lo stato non va più tenuto a mano: ogni volta che l'app scrive una milestone nella scheda (riga Riunioni di un nuovo resoconto, trascritto caricato, ✅ di invio, data di collaudo effettiva, lettere in firma o protocollate, protocolli salvati da Modifica scheda) lo stato **avanza da solo** allo stato suggerito dai fatti registrati, sempre e solo in avanti: Da Avviare → Bozza → Startup → Analisi → In corso → In Verifica → Collaudo → Concluso. La regola è in `SCHEMA.md` ("Avanzamento automatico dello stato"); il sync del master e il daily check la applicano in blocco a tutte le schede, così valgono anche le modifiche fatte in Obsidian.

Nel dettaglio rilascio, accanto allo stato, compare `→ <suggerito>` e il pulsante **Avanza stato** quando il suggerito supera lo stato scritto. Per bloccare l'automatismo su una scheda, in Modifica scheda spunta **Stato manuale**: resta il solo badge. Uno stato scelto a mano in Modifica scheda non viene riavanzato in quello stesso salvataggio; `Rinominato` non si tocca mai.

### Nuovo punto di piano

Dal menu **Nuovo punto di piano**: codice rilascio, sottoprogetto, descrizioni, ruoli, date. Crea la cartella `PO <anno>/<codice>/` e la scheda nello stesso formato di quelle generate dall'Excel PO. Il codice deve avere la forma `ADMxxx-xx-xX` e non esistere già. I campi persona suggeriscono i nomi dell'Anagrafica e con l'icona a destra creano al volo una nuova persona.

---

## Resoconti

Ogni riunione produce un resoconto `ADMxxx-xx-xX - AAAAMMGG Resoconto <Tipo>.md` nella cartella del rilascio (la **bozza**); dopo l'invio i file passano in `inviati/`.

### Nuovo resoconto

Dallo step **+** del ciclo di vita (o dal pulsante "Nuovo resoconto" nella versione Python): si sceglie la fase (uguale o successiva all'ultima già fatta, o un testo libero) e la data. Viene generato lo **scheletro** con le sezioni fisse già compilate dalla scheda e dall'Anagrafica: tabelle RIUNIONE / RESOCONTO / OBIETTIVO, LISTA PARTECIPANTI, formula dell'OBIETTIVO DELLA RIUNIONE; nella scheda viene aggiunta la riga in `## Riunioni` con ❌ (non inviato). Restano da scrivere **ARGOMENTI TRATTATI** e **AZIONI CONCORDATE** (per il collaudo: ESITO, con i casi di test presi dal Verbale).

Se nella cartella del rilascio c'è il **CSV presenze di Teams** con la data della riunione (caricato con "Carica fonti"), la LISTA PARTECIPANTI nasce dai presenti veri (ruoli PM/RA/RP/RB riconosciuti dal team della scheda, referente SOGEI per primo) e i presenti nuovi ricevono una scheda in Anagrafica; altrimenti dal team della scheda, con la nota "[lista incompleta — integrare con report presenze Teams]". Nell'editor il pulsante **Importa CSV presenze** sostituisce le liste ADM e SOGEI con quelle del CSV della data del resoconto.

### Resoconto con Copilot 365 (dalla 2.0)

Dove c'è Copilot 365 e non Claude Code, la prima stesura di ARGOMENTI TRATTATI e AZIONI CONCORDATE la scrive un **agente Copilot** (istruzioni in `Template/copilot/Istruzioni agente Resoconti.md`: conoscenza = cartella `Desktop/PO VAULT` del OneDrive del PM, strumenti = flussi "Leggi file vault" e "Salva proposta Copilot"; installazione in `Template/copilot/Guida installazione agente.md`). L'agente legge il trascritto Teams e salva `Proposta Copilot.md` in `_fonti/AAAAMMGG <Fase>/` del rilascio (frontmatter con codice, data e fase; sezioni PARTECIPANTI, ARGOMENTI TRATTATI, AZIONI CONCORDATE, NOTE PER IL PM). Dopo il sync la proposta è nel vault locale.

L'agente legge e scrive nella **copia del vault su OneDrive** (cartella `Desktop/PO VAULT`), non nel vault git: dopo che ha salvato la proposta, portala nel vault con "Carica fonti" (il file viene riconosciuto come proposta) oppure copiandola a mano in `_fonti/AAAAMMGG <Fase>/`; allo stesso modo il trascritto deve essere presente nella copia OneDrive prima di chiedere la proposta.

Nel modulo **Nuova riunione**, se per data e fase scelte c'è una proposta, compare la casella "Importa da Copilot (generata il …)": lo scheletro nasce con argomenti e azioni già compilati (i partecipanti della proposta contano solo senza CSV presenze, con la nota di lista incompleta) e le NOTE PER IL PM arrivano come avvisi, mai nel resoconto. Ciclone agente: **Copia prompt per Copilot** mette negli appunti (e mostra) il prompt di `Template/copilot/Prompt resoconto.txt` con codice, fase, data e il percorso del trascritto; la risposta si incolla nel campo "Proposta": viene salvata in `_fonti/` con il frontmatter generato e usata subito. Nell'**editor** il pulsante "Importa da Copilot" sostituisce le due sezioni, dopo conferma, con la proposta della stessa data e fase. Una proposta di un'altra riunione (frontmatter discordante) è ignorata con avviso; per il **collaudo** la proposta non si usa mai (struttura fissa). "Carica fonti" riconosce il file (`tipo: proposta_copilot`) e lo salva senza trattarlo come trascritto. Il resoconto resta l'unico documento ufficiale: si rilegge e si corregge come sempre.

### Carica fonti

Dal dettaglio del rilascio (o dal modulo Nuova riunione, "Carica fonti prima"): data, fase e uno o più file — trascritti `.docx`/`.md`/`.vtt`, il CSV presenze scaricato da Teams (col suo nome originale: contiene la data), PDF. I file vanno in `_fonti/AAAAMMGG <Fase>/` del rilascio; i `.docx` e i `.vtt` vengono convertiti in `.md` (nella versione Python con pandoc, nella Web con il lettore Word dell'app: stesso testo, senza pandoc); il CSV aggiorna l'Anagrafica (schede nuove, email mancanti); il primo trascritto entra nella riga `## Riunioni` se la colonna è vuota. Per ogni file compare l'esito: salvato, identico (già presente uguale), conflitto (esiste con contenuto diverso: "Sovrascrivi" per forzare), rifiutato (estensione non ammessa o oltre 200 MB). Se il resoconto di quella riunione esiste già in bozza, un link apre l'editor con le presenze importate (da salvare).

### Editor a sezioni

Il resoconto si modifica sezione per sezione: partecipanti (selettore con i nomi dell'Anagrafica), argomenti, azioni (una per riga, con responsabile e data), esito del collaudo. Si riscrivono **solo le sezioni cambiate**; `data_riunione`, `approvato_da` e `data_approvazione` restano allineati tra frontmatter e tabelle. Sotto lo stepper del ciclo di vita compare il resoconto della fase scelta: editor inline se è una bozza, sola lettura con il lucchetto se è già inviato.

### Dal markdown al Word

- **Rigenera .docx** produce il documento Word ufficiale dal `.md` con il template giusto (startup/analisi/SAL, collaudo con firme o con approvazione telematica) e imposta DATA COMPILAZIONE a oggi, nel `.md` e nel Word. Il `.msg` precedente, ormai superato, viene eliminato. Funziona in entrambe le versioni: nel browser il Word nasce dallo stesso template, letto dalla cartella `Template/` del vault, e viene scritto accanto al `.md`.
- **Genera mail** crea la bozza `.msg` con il Word allegato: oggetto, testo dal template di mail (variante telematica per i collaudi con approvazione telematica), destinatari dai partecipanti del resoconto e dal team della scheda (email dall'Anagrafica; chi non ha l'email viene elencato, da aggiungere a mano in Outlook). Nella finestra scegli i PDF della cartella del rilascio da allegare (per il collaudo telematico il documento di analisi con i suoi allegati). Nella versione Python la bozza la compone Outlook stesso, con la firma istituzionale; nel browser il `.msg` è scritto dall'app e porta la firma testuale del template: per quella di Outlook usa Inserisci → Firma prima di inviare. Il `.msg` si apre con doppio clic (versione Python: pulsanti **Apri in Outlook** e **Apri cartella**; Web: **Copia percorso** nell'esito).
- Se modifichi il `.md` dopo aver generato Word e mail, Bozze da inviare segnala ⚠️ "docx superato": rigenera il Word e poi la mail. Anche il sync (versione Python) rigenera i Word superati.

### Invio e approvazione tacita

1. Quando la mail è stata inviata davvero, **Segna inviato** (vista "Bozze da inviare"): i file passano in `inviati/`, `inviato: true`, `data_scadenza_approvazione` = +5 giorni lavorativi, ✅ nella scheda.
2. Alla scadenza senza osservazioni il resoconto è approvato tacitamente: **Chiudi approvazione** registra `data_approvazione`; PDF e mail definitiva li completa il sync del master.
3. **Mail definitiva** (quando il PDF esiste): bozza `.msg` con il template "versione definitiva" e il PDF allegato; poi **Segna definitivo inviato** chiude il ciclo (`definitivo_inviato: true`).

### Riporta in bozza

Per rettificare un resoconto già inviato: **Riporta in bozza** riporta `.md` e `.docx` nella cartella del rilascio, elimina il `.msg` obsoleto, azzera `inviato` e la scadenza, rimette ❌ nella scheda. Si corregge, si rigenera il `.docx` e al prossimo invio si segna di nuovo inviato.

### Convocazioni

**Convoca startup** e **Convoca collaudo** (dal dettaglio rilascio; nella versione Python nella card Azioni) producono `ADMxxx-xx-xX - AAAAMMGG Convocazione Startup.eml` / `… Convocazione Collaudo.eml` nella cartella del rilascio: la `.eml` **è essa stessa l'invito** (invito calendario incorporato), basta aprirla in Outlook e premere Invia. Destinatari dai ruoli della scheda (A = RA, in copia RP, RB e SOGEI; per la startup anche il referente SOGEI del frontmatter); chi non ha l'email in Anagrafica è segnalato nell'esito e va aggiunto in Outlook. Data proposta: startup 7 giorni lavorativi dopo oggi; collaudo dalla disponibilità a collaudo + 20 giorni, 15 (o 10) giorni prima, mai nel weekend (campo vuoto con avviso se la disponibilità è `DA COMPLETARE`). Ora `HH:MM`, mai tra le 12:30 e le 14:00; conferma se la data cade di sabato o domenica. Startup: fino a tre date alternative nel corpo. Collaudo: PDF del piano di test (fra quelli del rilascio e di `_fonti/`), documento di analisi e casi di test, precompilati dal `… Piano di Test.md` del rilascio se c'è; crea anche il **Verbale di Collaudo** (mai sovrascritto). Il mittente (organizzatore dell'invito) è il PM della dashboard `PO 2026.md`, modificabile nella finestra.

**Cambio di data del collaudo:** una nuova convocazione con un'altra data elimina la bozza `.eml` precedente non ancora segnata inviata e rinomina il Verbale alla nuova data conservando le spunte (anche quelle fatte in Obsidian), purché il collaudo non risulti già svolto (esito complessivo compilato, data del Verbale già passata o `data_collaudo_effettiva` nella scheda): in quel caso il vecchio Verbale resta e se ne crea uno nuovo.

### Verbale di Collaudo

La convocazione del collaudo crea `ADMxxx-xx-xX - AAAAMMGG Verbale di Collaudo.md` con l'elenco delle verifiche. L'editor del Verbale (dal dettaglio rilascio) permette di segnare ogni verifica come superata o non superata, con data, tester e note, e l'esito complessivo (positivo, con riserva, negativo): riepilogo e dettaglio restano allineati. Il resoconto di collaudo prende da qui i casi di test e l'esito.

### Lettere di fine collaudo

Dal dettaglio del rilascio (nella versione Python nella card Azioni), **Lettere di fine collaudo** compila i template Word `Template - ADMXXX-XX-XX Trasmissione copia verbale di collaudo.docx` e `… Richiesta estensione in esercizio.docx` e scrive i `.docx` nella cartella del rilascio (`ADMxxx-xx-xX Trasmissione copia verbale di collaudo.docx`, `ADMxxx-xx-xX - Richiesta estensione in esercizio.docx`), gli stessi nomi che Da firmare cerca. La finestra propone, modificabili: la tabella del Piano Operativo dalla scheda; i rappresentanti ADM e SOGEI dal resoconto di collaudo (altrimenti dal CSV presenze del collaudo, altrimenti dal team della scheda), un nome per riga in forma Cognome Nome (i cognomi composti con particella — De Luca, Lo Presti, Della Valle — vengono riconosciuti; per gli altri scrivi `Cognome | Nome`); l'esito dal Verbale (POSITIVO · con riserva · NEGATIVO: con NEGATIVO la Richiesta estensione parte deselezionata); per la Richiesta estensione la Direzione e l'Ufficio del referente business, ricavati dall'Anagrafica (Direzione dal nodo Strutture, Ufficio come "Ufficio" + denominazione dell'organigramma in iniziali maiuscole) e l'Area di Staff. **Rileggi sempre l'intestazione in Word prima della firma**: la denominazione dell'ufficio è una convenzione, non un dato. Solo i segnaposto vengono sostituiti: tab, rientri e firma del Dirigente restano quelli del template; la riga `Prot.:` la compila la protocollazione.

Una lettera già presente non viene toccata ("esistente, non sovrascritta"); con **Sovrascrivi** viene riscritta e la cartella `da mandare in firma/<Lettera>/` viene svuotata, così il sync del PC master rifà i PDF dalla lettera nuova (li rifà solo se la cartella è vuota). I PDF per Arcipelago e la cartella restano al sync del master (Word). Ciclone `data_collaudo_effettiva` le lettere si creano comunque, ma compaiono in Da firmare solo quando il collaudo è registrato come svolto.

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

Lettere di fine collaudo (Trasmissione copia verbale · Richiesta estensione in esercizio) presenti nella cartella del rilascio: **da mandare in firma** e **in attesa di protocollazione**. I pulsanti registrano i passaggi (`in_firma`, `protocollata`); nella versione Python "Prepara cartella firma" produce la cartella con i PDF (il sync del master lo fa da solo); nella Web i `.docx` delle lettere si creano con "Lettere di fine collaudo" nel dettaglio rilascio.

### Stato invii

Matrice punti di piano × fase: per ogni resoconto **P** = provvisorio inviato, **D** = definitivo inviato, con il link al file. Sola lettura: gli stati si cambiano da "Bozze da inviare".

---

## Anagrafica

Elenco delle persone del vault (`Anagrafica/<Cognome Nome>.md`) con filtro per nome, organizzazione, direzione e ufficio. **Nuova persona** crea la scheda con organizzazione, direzione, ufficio, email e ruolo tipico; la stessa cosa si può fare al volo dai campi persona di Modifica scheda, Nuovo punto di piano e del selettore dei partecipanti. I nodi delle strutture (direzioni, uffici) stanno in `Anagrafica/Strutture/`.

---

## Azioni e Sync (versione Python)

La pagina **Azioni** raccoglie le operazioni che lanciano gli script del vault: daily check, rigenerazione delle pagine, schede dall'Excel PO, strutture, refresh Anagrafica, audit degli invii, organizzazione delle cartelle Outlook. Ogni pulsante è disabilitato, con il motivo, quando manca un prerequisito (Outlook, Word, pandoc) o quando l'azione è riservata al PC **master**.

Il pulsante **Sync** esegue `scripts/sync.py`: allinea il vault con git, genera i `.msg` mancanti, ricostruisce la cartella locale `Bozze da inviare/`, archivia gli inviati e, sul master, chiude le approvazioni tacite e rigenera i `.docx` superati. **Durante un'azione ogni scrittura dell'app è sospesa** (banner in alto), così nessun file si sposta mentre git lavora. **Log azioni** mostra la cronologia delle esecuzioni.

**Vault senza git.** La versione web e il pack dimostrativo sono strumenti autonomi sul PC di utilizzo: non scrivono mai su git. Se il vault non è un repository git, il sync salta pull e push e fa solo il ricalcolo locale (pagine, Bozze da inviare, archiviazione, `.msg` mancanti con Outlook, PDF con Word).

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
| Nuovo resoconto, editor a sezioni, Verbale, Riporta in bozza, partecipanti dal CSV presenze | sì | sì |
| Resoconto con Copilot 365 (Importa da Copilot, proposta incollata, Copia prompt) | sì | sì |
| Carica fonti (trascritti → `.md`, CSV presenze → Anagrafica, riga Riunioni), protocolli in Modifica scheda | sì | sì (i `.docx` convertiti dall'app, senza pandoc) |
| Cruscotto con Segna inviato, Chiudi approvazione, collaudo effettivo, lettere | sì | sì |
| Rigenera .docx, Genera mail `.msg`, Mail definitiva | sì | sì (il `.msg` del browser porta la firma del template) |
| Convocazioni startup e collaudo (`.eml` con invito, PDF del piano di test, Verbale) | sì | sì (organizzatore dalla dashboard; al cambio di data bozza precedente eliminata e Verbale rinominato) |
| Lettere di fine collaudo (`.docx` dai template, dati dalla scheda/resoconto/Verbale/Anagrafica) | sì | sì |
| PDF e cartella `da mandare in firma/` | sì (Word) | no: li produce il sync del PC master |
| Azioni, Sync, Log azioni, Riavvia backend, ricerca Ctrl+K, Apri in Outlook/Apri cartella | sì | no |
| Requisiti | Python 3.12, Outlook/Word/pandoc per le azioni | Edge o Chrome (103 o successivi per Word e mail) |

Nella versione Web ogni scrittura passa dalle stesse regole del codice Python (chiavi cambiate, sezioni cambiate, scadenze a +5 giorni lavorativi, ✅/❌ nella scheda), verificate dagli stessi dati di riferimento.
