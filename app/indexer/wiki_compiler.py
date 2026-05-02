import logging
import httpx
import json
from typing import List, Dict
from app.config import get_ollama_host, TEMPERATURE, get_active_model
from app.search.wiki_store import WikiStore, WikiEntry

logger = logging.getLogger(__name__)

WIKI_COMPILER_PROMPT = (
    "Sei un assistente specializzato nella sintesi essenziale di documenti.\n"
    "Il tuo compito è analizzare il contenuto di un file e produrre una descrizione ULTRA-CONCISA (massimo 20 parole).\n"
    "Concentrati solo su fatti concreti: chi, cosa, quando, dove.\n"
    "NON usare preamboli come 'Questo file contiene...' o 'Il documento parla di...'.\n"
    "Sii diretto e denso di informazioni.\n"
    "Esempio: 'Contratto affitto Mario Rossi, Milano, Via Roma 1, scadenza 12/2025, canone 1200€'."
)

class WikiCompiler:
    """Uses Ollama to generate essential summaries for documents."""

    def __init__(self, wiki_store: WikiStore):
        self.wiki_store = wiki_store

    def compile_file(self, filename: str, filepath: str, text_content: str) -> bool:
        """Generate a summary for a single file and add it to the wiki."""
        if not text_content or len(text_content.strip()) < 10:
            summary = "[Nessun contenuto testuale rilevante trovato]"
        else:
            try:
                summary = self._get_summary_from_llm(text_content)
            except Exception as e:
                logger.error(f"LLM Summary failed for {filename}: {e}")
                summary = "[Errore durante la generazione della sintesi]"

        entry = WikiEntry(
            filename=filename,
            filepath=filepath,
            summary=summary
        )
        self.wiki_store.add_entry(entry)
        return True

    def _get_summary_from_llm(self, text: str) -> str:
        """Call Ollama to get the essential summary."""
        host = get_ollama_host()
        model = get_active_model()
        
        # Limit input text to avoid context window issues (first 4000 chars should be enough for a summary)
        truncated_text = text[:4000]
        
        messages = [
            {"role": "system", "content": WIKI_COMPILER_PROMPT},
            {"role": "user", "content": f"File: {truncated_text}"}
        ]

        try:
            response = httpx.post(
                f"{host}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.0}  # Fixed for consistency
                },
                timeout=120.0
            )
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            raise
