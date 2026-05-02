# 🔒 PrivateSearch: Wiki Edition

**PrivateSearch** è un sistema di ricerca documentale semantica, 100% locale e privato, ispirato al paradigma "LLM Wiki" di Andrej Karpathy. 

A differenza dei sistemi RAG tradizionali, questa versione "Wiki Edition" distilla l'essenza di ogni documento in una sintesi criptata, creando una base di conoscenza ad alta densità di significato, protetta da crittografia militare.

## 🚀 Caratteristiche Principali

- **Vault Criptato (AES-256)**: Tutti i dati generati dall'IA sono cifrati con una Master Password. Senza di essa, il tuo indice wiki è un ammasso di dati illeggibili.
- **Sintesi Essenziale**: L'IA (via Ollama) legge i tuoi file (PDF, Immagini via OCR, Testo) e ne crea una "carta d'identità" ultra-concisa (max 20 parole) focalizzata sui fatti.
- **Point & Open**: Trova un documento tramite chat semantica e aprilo istantaneamente con l'applicazione predefinita del tuo PC (Acrobat, Word, ecc.) con un solo click.
- **Privacy Totale**: Nessun dato lascia mai il tuo PC. Tutto gira localmente tramite il framework Ollama.
- **Multi-Vault**: Gestisci diverse cartelle di documenti come vault separati e indipendenti.

## 🛠️ Requisiti

- **Linux** (testato su Ubuntu)
- **Ollama** installato e in esecuzione (`ollama serve`)
- **Python 3.10+**
- Almeno un modello Qwen2.5 o Llama3 scaricato in Ollama (es. `ollama pull qwen2.5:7b`)

## 📦 Installazione Rapida

1. Clona la repository nella tua cartella preferita.
2. Assicurati che Ollama sia attivo.
3. Avvia lo script di configurazione e avvio:

```bash
bash start.sh
```

Lo script creerà automaticamente l'ambiente virtuale (`.venv`), installerà le dipendenze e avvierà l'interfaccia web.

## 📖 Come si usa

1. **Sblocco**: Vai nella scheda **"Accesso & Config"** e inserisci una Master Password.
2. **Compilazione**: Nella scheda **"Gestione Wiki"**, inserisci il percorso di una cartella locale e clicca su **"Compila / Aggiorna Wiki"**. L'IA inizierà a leggere e sintetizzare i file.
3. **Ricerca**: Vai nella scheda **"Ricerca Wiki"**. A destra vedrai l'indice completo dei tuoi file. A sinistra potrai fare domande come: *"Trova i contratti scaduti nel 2023"* o *"C'è un file che parla di Enel?"*.
4. **Apertura**: Clicca sui pulsanti **"Apri [nome file]"** che appaiono sotto la chat per consultare l'originale.

## 🔐 Sicurezza

Il sistema utilizza:
- **PBKDF2** per la derivazione della chiave dalla tua password.
- **AES-256 (Fernet)** per la cifratura dei file `.wiki.enc`.
- **OCR Locale**: Per le immagini e i PDF scansiti, il riconoscimento del testo avviene interamente sul tuo PC.

---
*PrivateSearch — La tua conoscenza, protetta e interpellabile.*
