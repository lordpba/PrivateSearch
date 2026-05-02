#!/bin/bash
# Script di avvio per PrivateSearch: Wiki Edition

# 1. Attiva l'ambiente virtuale
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ Ambiente virtuale non trovato. Creazione in corso..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    pip install cryptography gradio
fi

# 2. Avvia l'applicazione
echo "🚀 Avvio di PrivateSearch..."
python3 app/main.py
