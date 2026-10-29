# Agente Copilot "Resoconti PO 2026" — guida di installazione per un altro PM

Ogni PM usa **una propria copia** dell'agente, collegata al **proprio OneDrive** e alle **proprie connessioni**: non
esiste un agente condiviso, perché la conoscenza (la cartella del vault) e i percorsi dei flussi sono fissi e non
cambiano in base a chi scrive. Tempo stimato: 30–40 minuti la prima volta.

## 1. Prerequisiti

- Licenza Microsoft 365 con **Copilot Studio** (copilotstudio.microsoft.com, ambiente predefinito dell'organizzazione).
- **OneDrive aziendale** sincronizzato sul PC (client OneDrive, cartella Desktop inclusa nel backup cartelle).
- LeviathADM 2.0 (Python o web) con il proprio vault PO 2026.

## 2. La copia del vault su OneDrive

1. Sul Desktop (sincronizzato con OneDrive) crea la cartella **`PO VAULT`**.
2. Copia dentro, dal tuo vault: `PO 2026/`, `Anagrafica/`, `Aree/`, `Template/` (basta `Template/copilot/`), `Manuale protocollo/`.
3. Attendi che OneDrive segni tutto in verde. Il percorso che l'agente userà è `/Desktop/PO VAULT/...`.

Il vault git resta la copia ufficiale: la cartella OneDrive serve all'agente per leggere e per scrivere la proposta.
Prima di chiedere una proposta, il trascritto della riunione deve stare in `PO VAULT/PO 2026/<codice>/_fonti/<AAAAMMGG Fase>/`.

## 3. Come ottenere la propria copia

**Costruiscila a mano (sezione 4), ~30 minuti.** Nello stesso ambiente Power Platform (`adm.gov.it (default)`) l'import
di una soluzione esportata **non crea una copia**: sovrascrive l'agente originale (stesso identificativo), e Copilot Studio
non ha un pulsante "Duplica". La soluzione `Resoconti PO 2026` (agente + flussi) esiste comunque: l'import dello zip ha
senso solo in un **ambiente diverso** (es. un ambiente di sviluppo personale, se l'amministratore lo consente): in quel
caso, all'import, scegli la tua connessione OneDrive for Business nei riferimenti di connessione, poi elimina la fonte di
conoscenza importata e aggiungi la tua cartella `Desktop/PO VAULT`.

## 4. Costruire l'agente

1. **Agenti → Nuovo agente → Agente (Standard)**, nome `Resoconti PO 2026`.
2. **Istruzioni**: incolla `Template/copilot/Istruzioni agente Resoconti.md` dalla sezione "Ruolo" in poi (sezione "Strumenti" compresa).
   I percorsi `/Desktop/PO VAULT/...` sono relativi al OneDrive di chi possiede la connessione: valgono per tutti senza modifiche.
3. **Knowledge Base → Aggiungi → OneDrive → Sfoglia** → `Desktop/PO VAULT` → Aggiungi. Nella Panoramica spegni **Ricerca Web**.
4. **Strumenti → Aggiungi uno strumento → Flusso dell'agente**, flusso **Salva proposta Copilot**:
   - trigger "Quando un agente chiama il flusso" con tre input di testo: `cartella`, `nome_file`, `contenuto`;
   - azione OneDrive for Business **Crea file**: Percorso cartella = `cartella`, Nome file = `nome_file`, Contenuto file = `contenuto`;
   - "Rispondi all'agente": output di testo `esito` = `File salvato su OneDrive nella cartella indicata`;
   - Salva bozza, rinomina, **Pubblica**, "Torna all'agente"; poi **Aggiungi uno strumento → filtro Flusso →** il flusso → Aggiungi e configura.
5. Allo stesso modo il flusso **Leggi file vault**: input di testo `percorso`; azione OneDrive **Ottieni contenuto file in base al percorso**
   (Percorso file = `percorso`); output di testo `testo` = espressione `string(body('Ottieni_contenuto_file_in_base_al_percorso'))`.
6. Nelle descrizioni dei due strumenti indica i percorsi d'esempio (`/Desktop/PO VAULT/PO 2026/<codice>/_fonti/<AAAAMMGG Fase>`).
7. Non usare il connettore OneDrive "Crea file" direttamente come strumento: il parametro "File Content" è binario e l'IA non riesce a compilarlo.

## 5. Prova

Nel pannello **Testa il tuo agente**:

1. `Chi è il referente SOGEI del rilascio <codice>?` → deve rispondere dalla scheda `.md` (se no, l'indice non è pronto: attendi).
2. `Con Leggi file vault leggi /Desktop/PO VAULT/PO 2026/<codice>/_fonti/<cartella>/<trascritto>.md e riporta le prime tre battute` → deve leggerlo.
3. Il prompt di **"Copia prompt per Copilot"** di LeviathADM (Nuova riunione) → deve salvare `Proposta Copilot.md` nella cartella `_fonti/<AAAAMMGG Fase>/`.

Poi **Pubblica** l'agente e, in **Canali**, abilita Teams / Microsoft 365 Copilot per usarlo fuori da Copilot Studio.

## 6. Uso quotidiano

1. Scarica trascritto (e CSV presenze) da Teams, caricali con "Carica fonti" in LeviathADM e copiali anche in `PO VAULT` (OneDrive).
2. In LeviathADM, Nuova riunione → **Copia prompt per Copilot** → incolla nella chat dell'agente.
3. L'agente scrive `Proposta Copilot.md` nella copia OneDrive: portala nel vault con **Carica fonti** (riconosciuta come proposta) o copiandola in `_fonti/<AAAAMMGG Fase>/`.
4. Nuova riunione con la stessa data e fase → casella **Importa da Copilot** → scheletro con ARGOMENTI e AZIONI già compilati; le NOTE PER IL PM compaiono come avvisi. Rileggi, correggi, Rigenera .docx, sync.
