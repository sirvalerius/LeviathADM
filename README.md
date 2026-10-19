# LeviathADM — pack demo

Pacchetto dimostrativo di **LeviathADM** con un vault "PO 2026" interamente **inventato**: persone, uffici,
progetti e rilasci sono fittizi (lotterie lunari, dazi sui dirigibili, accise sul vapore…). Nessun dato reale.

## Versione Python (dashboard locale)

1. doppio clic su `leviathadm.cmd` (usa il Python embedded in `python/`, nessuna installazione);
2. apri http://127.0.0.1:8080 nel browser (`leviathadm.cmd --porta 8090` per un'altra porta).

Il PC è configurato come **slave** (`scripts/machines.json`): le viste e le scritture funzionano tutte;
le azioni che richiedono Word (PDF) o pandoc restano disabilitate se i programmi mancano. Nel pack
**Sync, audit invii e organizzazione delle cartelle Outlook sono sostituiti da segnaposto** che escono
subito: il pack non è un repository git e non deve mai toccare una casella di posta reale.

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
