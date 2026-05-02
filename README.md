# 🔒 PrivateSearch: Wiki Edition

**PrivateSearch** is a semantic document search system, 100% local and private, inspired by Andrej Karpathy's "LLM Wiki" paradigm.

Unlike traditional RAG systems, the "Wiki Edition" distills the essence of every document into an encrypted summary, creating a high-density knowledge base protected by military-grade encryption.

## 🚀 Key Features

- **Encrypted Vault (AES-256)**: All AI-generated data is encrypted using a Master Password. Without it, your wiki index remains unreadable.
- **Essential Synthesis**: The AI (via Ollama) reads your files (PDFs, Images via OCR, Text) and creates an ultra-concise "identity card" (max 20 words) focused on facts.
- **Point & Open**: Find a document via semantic chat and open it instantly using your PC's default application (Acrobat, Word, etc.) with a single click.
- **Total Privacy**: No data ever leaves your PC. Everything runs locally via the Ollama framework.
- **Multi-Vault**: Manage different document folders as separate and independent encrypted vaults.

## 🛠️ Requirements

- **Linux** (tested on Ubuntu)
- **Ollama** installed and running (`ollama serve`)
- **Python 3.10+**
- At least one Qwen2.5 or Llama3 model downloaded in Ollama (e.g., `ollama pull qwen2.5:7b`)

## 📦 Quick Start

1. Clone the repository to your local machine.
2. Ensure Ollama is running.
3. Run the startup script:

```bash
bash start.sh
```

The script will automatically create the virtual environment (`.venv`), install dependencies, and launch the web interface.

## 📖 How to Use

1. **Unlock**: Go to the **"Access & Config"** tab and set your Master Password.
2. **Compile**: In the **"Wiki Management"** tab, enter a local folder path and click **"Compile / Update Wiki"**. The AI will start reading and synthesizing your files.
3. **Search**: Go to the **"Wiki Search"** tab. You'll see the complete file index on the right. On the left, you can ask questions like: *"Find contracts expired in 2023"* or *"Is there a file mentioning Enel?"*.
4. **Open**: Click the **"Open [filename]"** buttons that appear below the chat to consult the original document.

## 🔐 Security

The system implements:
- **PBKDF2** for key derivation from your password.
- **AES-256 (Fernet)** for `.wiki.enc` file encryption.
- **Local OCR**: Text recognition for images and scanned PDFs happens entirely on your machine.

---
*PrivateSearch — Your knowledge, protected and searchable.*
