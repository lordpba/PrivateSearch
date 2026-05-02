"""
PrivateSearch — Main Gradio Application.
100% local document search with AI. Privacy-first.
"""

import sys
import os
import json
import logging
import time
from pathlib import Path
from typing import Generator

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import gradio as gr
import httpx

from app.config import (
    OLLAMA_HOST, PROFILES,
    ALL_EXTENSIONS, GRADIO_HOST, GRADIO_PORT,
    APP_TITLE, APP_SUBTITLE, UserConfig, DATA_DIR,
    host_to_container_path, container_to_host_path,
    set_ollama_host, get_ollama_host, get_active_model,
    get_vault_name
)
from app.indexer.document_loader import scan_folder, load_documents
from app.indexer.ocr_engine import OCREngine
from app.indexer.wiki_compiler import WikiCompiler
from app.search.wiki_store import WikiStore
from app.core.security import security
from app.core.file_utils import open_file
from app.ui.theme import create_theme, CUSTOM_CSS

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("PrivateSearch")

# ─── Global state ─────────────────────────────────────────────────────────────

wiki_store: WikiStore | None = None
wiki_compiler: WikiCompiler | None = None
ocr_engine: OCREngine | None = None


def init_components(vault_name: str = "default_vault"):
    """Initialize wiki components."""
    global wiki_store, wiki_compiler, ocr_engine
    wiki_store = WikiStore(vault_name)
    wiki_compiler = WikiCompiler(wiki_store)
    ocr_engine = OCREngine()


def update_wiki_list():
    """Returns a markdown list of all entries in the wiki."""
    if not wiki_store or wiki_store.is_empty:
        return "_Il wiki è vuoto o bloccato._"
    
    lines = ["### 📚 Indice Wiki\n"]
    for e in sorted(wiki_store.entries, key=lambda x: x['filename']):
        lines.append(f"- **{e['filename']}**\n  _{e['summary']}_")
    return "\n".join(lines)


# ─── Ollama helpers ───────────────────────────────────────────────────────────

def check_ollama_connection() -> tuple[bool, str]:
    """Check if Ollama is reachable."""
    try:
        host = get_ollama_host()
        r = httpx.get(f"{host}/api/tags", timeout=5.0)
        r.raise_for_status()
        return True, "Connesso"
    except Exception as e:
        return False, f"Non raggiungibile: {e}"


def get_installed_models() -> list[str]:
    """Get list of models installed in Ollama."""
    try:
        host = get_ollama_host()
        r = httpx.get(f"{host}/api/tags", timeout=5.0)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def check_required_models(config: UserConfig) -> dict:
    """Check which required models are installed."""
    installed = get_installed_models()
    required = config.required_models
    status = {}
    for model in required:
        status[model] = any(
            m == model or m == f"{model}:latest" or (":" not in model and m.startswith(f"{model}:"))
            for m in installed
        )
    return status


def pull_model(model_name: str) -> Generator:
    """Pull a model from Ollama with progress tracking."""
    try:
        with httpx.stream(
            "POST",
            f"{get_ollama_host()}/api/pull",
            json={"name": model_name, "stream": True},
            timeout=httpx.Timeout(connect=10.0, read=600.0, write=10.0, pool=10.0),
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        status = data.get("status", "")
                        total = data.get("total", 0)
                        completed = data.get("completed", 0)
                        if total > 0:
                            pct = completed / total * 100
                            yield f"{status}: {pct:.0f}% ({completed // (1024*1024)}MB / {total // (1024*1024)}MB)"
                        else:
                            yield status
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        yield f"Errore: {e}"


# ─── UI Callbacks ─────────────────────────────────────────────────────────────

def on_check_system():
    """Check system status: Ollama connection + models."""
    connected, msg = check_ollama_connection()
    if not connected:
        return (
            f"🔴 Ollama non raggiungibile\n\n"
            f"Assicurati che Ollama sia installato e in esecuzione.\n"
            f"Scarica da: https://ollama.com\n\n"
            f"Errore: {msg}"
        )

    config = UserConfig.load()
    models_status = check_required_models(config)

    lines = ["🟢 Ollama connesso\n"]
    all_ok = True
    for model, installed in models_status.items():
        icon = "✅" if installed else "❌"
        lines.append(f"  {icon} {model}")
        if not installed:
            all_ok = False

    if all_ok:
        lines.append("\n✅ Tutti i modelli sono pronti!")
    else:
        lines.append("\n⚠️ Modelli mancanti. Clicca 'Scarica modelli' per installarli.")

    return "\n".join(lines)


def on_download_models(progress=gr.Progress()):
    """Download all required models."""
    config = UserConfig.load()
    models_status = check_required_models(config)
    missing = [m for m, installed in models_status.items() if not installed]

    if not missing:
        return "✅ Tutti i modelli sono già installati!"

    results = []
    for i, model in enumerate(missing):
        progress((i) / len(missing), f"Scaricamento {model}...")
        last_status = ""
        for status_msg in pull_model(model):
            last_status = status_msg
            progress((i) / len(missing), f"{model}: {status_msg}")
        results.append(f"✅ {model}: completato")
        progress((i + 1) / len(missing), f"{model} completato")

    config.models_downloaded = True
    config.save()

    return "\n".join(results) + "\n\n✅ Tutti i modelli scaricati! Puoi procedere."


def on_select_profile(profile_key: str):
    """Save selected profile."""
    config = UserConfig.load()
    config.profile = profile_key
    config.save()
    profile = PROFILES[profile_key]
    return f"Profilo selezionato: {profile['name']} ({profile['model']})"


def on_change_ollama_url(url: str):
    """Update the Ollama server URL and test connection."""
    url = url.strip()
    if not url:
        # Reset to default
        from app.config import _DEFAULT_OLLAMA_HOST
        url = _DEFAULT_OLLAMA_HOST

    # Normalize: ensure http(s):// prefix
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "http://" + url

    set_ollama_host(url)

    # Save to config
    config = UserConfig.load()
    config.ollama_host = url
    config.save()

    # Re-initialize components with new URL
    init_components()

    # Test connection
    connected, msg = check_ollama_connection()
    if connected:
        return f"✅ Connesso a {url}"
    else:
        return f"❌ {url} — {msg}"


def on_unlock_vault(password: str):
    """Attempt to unlock the vault with the provided password."""
    if not password:
        return "❌ Inserisci una password."
    
    if security.derive_key(password):
        config = UserConfig.load()
        init_components(config.active_vault)
        if wiki_store.load():
            return "✅ Vault sbloccato correttamente!"
        else:
            return "❌ Impossibile caricare il vault. Password errata o dati corrotti."
    return "❌ Errore nella generazione della chiave."


def on_open_local_file(filepath: str):
    """Open a file on the local system."""
    # We need to translate back to host path if in Docker
    host_path = container_to_host_path(filepath)
    if open_file(host_path):
        return f"✅ Apertura in corso: {host_path}"
    return f"❌ Impossibile aprire il file: {host_path}"


def on_check_folder(folder_path: str):
    """Check folder and detect changes."""
    if not folder_path:
        return "❌ Inserisci un percorso.", ""

    if not security.is_unlocked:
        return "🔒 Sblocca il vault con la password nella scheda Configurazione prima di procedere.", ""

    actual_path = host_to_container_path(folder_path.strip())
    if not Path(actual_path).exists():
        return f"❌ Cartella non trovata: {folder_path}", ""

    vault_name = get_vault_name(folder_path.strip())
    config = UserConfig.load()
    config.folder_path = folder_path.strip()
    config.active_vault = vault_name
    config.save()

    # Re-init with correct vault
    init_components(vault_name)
    wiki_store.load()

    try:
        files = scan_folder(actual_path, ALL_EXTENSIONS)
    except Exception as e:
        return f"❌ Errore scansione: {e}", ""

    if not files:
        return "⚠️ Nessun file supportato trovato nella cartella.", ""

    # Check which files are already in the wiki
    existing_paths = {e["filepath"] for e in wiki_store.entries}
    new_files = [f for f in files if f["path"] not in existing_paths]

    summary = f"📂 {folder_path.strip()}\n\n"
    summary += f"📦 **Vault:** `{vault_name}`\n"
    summary += f"📄 **{len(files)} file** trovati.\n"

    if new_files:
        changes_text = f"⚠️ **{len(new_files)} nuovi file** da processare.\n\n**Clicca 'Compila Wiki' per iniziare.**"
    elif not wiki_store.is_empty:
        changes_text = f"✅ **Wiki aggiornato** ({len(wiki_store.entries)} file descritti).\n\nPuoi iniziare la ricerca semantica!"
    else:
        changes_text = "🆕 **Nessuna descrizione presente.** Clicca 'Compila Wiki'."

    return summary, changes_text


def on_compile_wiki(folder_path: str, progress=gr.Progress()):
    """Run the wiki compilation pipeline: scan → load → summary → store."""
    if not security.is_unlocked:
        yield "❌ Vault bloccato. Inserisci la password nella scheda Configurazione."
        return

    actual_path = host_to_container_path(folder_path.strip()) if folder_path else ""
    if not actual_path or not Path(actual_path).is_dir():
        yield "❌ Cartella non valida."
        return

    vault_name = get_vault_name(folder_path.strip())
    init_components(vault_name)
    wiki_store.load()

    t0 = time.time()

    def _status(phase: str, detail: str, file_num: int = 0, total: int = 0):
        pct = int(file_num / total * 100) if total else 0
        elapsed = time.time() - t0
        return (
            f"### 📝 Compilazione Wiki in corso…\n"
            f"**Fase:** {phase}\n"
            f"**Progresso:** {pct}%  —  file {file_num}/{total}\n"
            f"**File corrente:** `{detail}`\n"
            f"⏱️ Tempo trascorso: {elapsed:.0f}s"
        )

    # 1. Scan folder
    yield _status("Scansione cartella", folder_path.strip())
    files = scan_folder(actual_path, ALL_EXTENSIONS)
    
    # Identify files that need compilation
    existing_paths = {e["filepath"] for e in wiki_store.entries}
    files_to_process = [f for f in files if f["path"] not in existing_paths]
    
    if not files_to_process:
        yield f"✅ Wiki già aggiornato con {len(wiki_store.entries)} file."
        return

    total_files = len(files_to_process)
    processed = 0

    for i, file_info in enumerate(files_to_process):
        fp = Path(file_info["path"])
        yield _status("Generazione sintesi", fp.name, i + 1, total_files)
        progress((i) / total_files, f"Elaborazione {fp.name}...")

        try:
            # Load text (handles PDF, OCR, etc.)
            docs, ocr_queue = load_documents(actual_path, [file_info])
            
            # Simple OCR if queue exists
            if ocr_queue:
                ocr_docs = ocr_engine.process_ocr_queue(ocr_queue)
                docs.extend(ocr_docs)
            
            full_text = "\n".join(d.text for d in docs)
            
            # Compile Wiki Entry
            wiki_compiler.compile_file(file_info["name"], file_info["path"], full_text)
            processed += 1
            
            # Save incrementally every 5 files
            if processed % 5 == 0:
                wiki_store.save()
                
        except Exception as e:
            logger.error(f"Failed to process {fp.name}: {e}")

    # Final save
    wiki_store.save()
    elapsed = time.time() - t0
    
    yield (
        f"### ✅ Wiki Compilato!\n\n"
        f"| | |\n|---|---|\n"
        f"| 📄 File nuovi elaborati | **{processed}** |\n"
        f"| 📊 Totale nel Wiki | **{len(wiki_store.entries)}** file |\n"
        f"| ⏱️ Tempo | **{elapsed:.0f}** secondi |\n"
        f"\n🎉 Il tuo vault criptato è pronto per la consultazione."
    )


def on_chat_message(message: str, history: list):
    """Handle a chat message using the Wiki summaries."""
    if not message or not message.strip():
        return history, ""

    if not security.is_unlocked or not wiki_store:
        history.append({"role": "user", "content": message})
        history.append({
            "role": "assistant",
            "content": "🔒 Il vault è bloccato. Inserisci la password nella scheda **Configurazione**.",
        })
        return history, ""

    if wiki_store.is_empty:
        history.append({"role": "user", "content": message})
        history.append({
            "role": "assistant",
            "content": "⚠️ Wiki vuoto. Vai nella scheda **📂 Documenti** e compila il wiki per questa cartella.",
        })
        return history, ""

    history.append({"role": "user", "content": message})

    # 1. Prepare Wiki context (all summaries)
    wiki_context = "\n".join([
        f"- FILE: {e['filename']}\n  SINTESI: {e['summary']}\n  PATH: {e['filepath']}"
        for e in wiki_store.entries
    ])

    # 2. Ask LLM to find relevant files
    prompt = (
        "Sei un assistente alla ricerca documentale.\n"
        "Sotto hai un elenco di file con le loro sintesi.\n"
        "Il tuo compito è rispondere alla domanda dell'utente indicando i file più pertinenti.\n\n"
        "ELENCO WIKI:\n"
        f"{wiki_context}\n\n"
        "RISPONDI COSI':\n"
        "1. Fornisci una risposta breve basandoti sulle sintesi.\n"
        "2. Elenca i file trovati usando ESATTAMENTE questo formato per i link:\n"
        "   `[APRI: percorso/completo/del/file]`\n\n"
        "Non inventare informazioni non presenti nelle sintesi."
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": message}
    ]

    # 3. Stream response
    full_response = ""
    host = get_ollama_host()
    model = get_active_model()

    try:
        with httpx.stream(
            "POST",
            f"{host}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {"temperature": 0.1}
            },
            timeout=120.0
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    full_response += token
                    yield history + [{"role": "assistant", "content": full_response}], ""
    except Exception as e:
        yield history + [{"role": "assistant", "content": f"❌ Errore LLM: {e}"}], ""

    return history + [{"role": "assistant", "content": full_response}], ""


def on_clear_chat():
    """Clear chat history."""
    return [], ""


def on_clear_index():
    """Clear the entire vector store."""
    if vector_store:
        vector_store.clear()
    if ocr_engine:
        ocr_engine.clear_cache()
    return "🗑️ Indice e cache eliminati. Puoi re-indicizzare."


# ─── Build Gradio UI ──────────────────────────────────────────────────────────

def create_app() -> gr.Blocks:
    """Build the complete Gradio application."""
    theme = create_theme()

    with gr.Blocks(
        theme=theme,
        css=CUSTOM_CSS,
        title=APP_TITLE,
        analytics_enabled=False,
    ) as app:

        # ─── Header ────────────────────────────────────────────
        gr.HTML(
            f"""
            <div style="text-align: center; padding: 20px 0 10px 0;">
                <h1 class="app-title">🔒 {APP_TITLE} <span style="font-size: 0.5em; vertical-align: middle; opacity: 0.7;">Wiki Edition</span></h1>
                <p class="app-subtitle">{APP_SUBTITLE}</p>
            </div>
            <div class="security-banner">
                <span class="lock-icon">🛡️</span>
                100% LOCALE & CRIPTATO — Vault protetto da AES-256.
            </div>
            """
        )

        with gr.Tabs() as tabs:

            # ═══════════════ TAB 1: CONFIG & UNLOCK ═══════════════════════
            with gr.Tab("⚙️ Accesso & Config", id="setup"):
                with gr.Row():
                    with gr.Column(scale=2):
                        gr.Markdown("### 🔑 Sblocca il tuo Vault")
                        password_input = gr.Textbox(
                            label="Master Password",
                            placeholder="Inserisci la password per sbloccare o creare il wiki...",
                            type="password",
                        )
                        unlock_btn = gr.Button("🔓 Sblocca Vault", variant="primary")
                        unlock_status = gr.Markdown("Vault bloccato.")

                    with gr.Column(scale=1):
                        gr.Markdown("### 🖥️ Stato Sistema")
                        system_status = gr.Textbox(
                            label="Ollama Status",
                            lines=4,
                            interactive=False,
                            value="Verifica in corso...",
                        )
                        check_btn = gr.Button("🔍 Verifica", variant="secondary")

                with gr.Accordion("Impostazioni Hardware", open=False):
                    profile_radio = gr.Radio(
                        choices=[
                            ("⚡ Veloce — GPU 4 GB (qwen3.5:4b)", "fast"),
                            ("🎯 Preciso — GPU 8 GB (qwen3.5:9b)", "precise"),
                            ("🚀 Massimo — 2× GPU 12 GB (qwen3.5:27b)", "maximum"),
                        ],
                        value=UserConfig.load().profile,
                        label="Profilo GPU",
                    )
                    ollama_url_input = gr.Textbox(
                        label="URL server Ollama",
                        value=get_ollama_host(),
                    )

            # ═══════════════ TAB 2: WIKI COMPILER ═══════════════════
            with gr.Tab("📂 Gestione Wiki", id="documents"):
                gr.Markdown("### 📚 Compilazione Wiki della Cartella")
                gr.Markdown(
                    "Seleziona una cartella. L'IA genererà una sintesi essenziale criptata per ogni file."
                )

                with gr.Row():
                    folder_input = gr.Textbox(
                        label="Percorso cartella locale",
                        placeholder="/home/mario/Documenti",
                        value=UserConfig.load().folder_path,
                        scale=3,
                    )
                    check_folder_btn = gr.Button("🔍 Analizza Cartella", variant="secondary", scale=1)

                with gr.Row():
                    folder_info = gr.Markdown("Inserisci un percorso.")
                    changes_info = gr.Markdown("")

                compile_btn = gr.Button(
                    "📝 Compila / Aggiorna Wiki",
                    variant="primary",
                    size="lg",
                )
                compile_result = gr.Markdown("")

                with gr.Accordion("⚠️ Zona Pericolosa", open=False):
                    clear_wiki_btn = gr.Button("🗑️ Elimina questo Wiki", variant="stop")
                    clear_result = gr.Textbox(label="", interactive=False)

            # ═══════════════ TAB 3: RICERCA SEMANTICA ════════════════════════
            with gr.Tab("💬 Ricerca Wiki", id="chat"):
                with gr.Row():
                    with gr.Column(scale=2):
                        chatbot = gr.Chatbot(
                            label="",
                            height=550,
                            type="messages",
                            show_copy_button=True,
                            placeholder=(
                                "📚 **Il tuo Wiki Criptato**\n\n"
                                "Chiedimi cosa cerchi. Esempio: 'Trova le fatture Enel del 2023'.\n\n"
                                "I file trovati appariranno qui sotto."
                            ),
                        )

                        with gr.Row():
                            chat_input = gr.Textbox(
                                placeholder="Cosa stai cercando?",
                                show_label=False,
                                scale=5,
                                container=False,
                            )
                            send_btn = gr.Button("Cerca", variant="primary", scale=1)

                        gr.Markdown("### 📄 File trovati nell'ultima ricerca")
                        with gr.Row():
                            found_files_container = gr.HTML("<p style='opacity: 0.5;'>Nessun file aperto di recente.</p>")
                    
                    with gr.Column(scale=1):
                        wiki_list_display = gr.Markdown(
                            value="_Sblocca il vault per vedere l'indice._",
                            elem_classes="wiki-sidebar"
                        )
                
                # Hidden component to trigger file opening
                open_trigger = gr.Textbox(visible=False)
                open_status = gr.Markdown("")

        # ─── Event Handlers ─────────────────────────────────────


        # Setup
        check_btn.click(fn=on_check_system, outputs=system_status)
        unlock_btn.click(fn=on_unlock_vault, inputs=password_input, outputs=unlock_status)
        unlock_btn.click(fn=update_wiki_list, outputs=wiki_list_display)
        profile_radio.change(fn=on_select_profile, inputs=profile_radio)
        
        # Wiki
        check_folder_btn.click(
            fn=on_check_folder,
            inputs=folder_input,
            outputs=[folder_info, changes_info],
        )
        compile_btn.click(
            fn=on_compile_wiki,
            inputs=folder_input,
            outputs=compile_result,
        )
        compile_btn.click(fn=update_wiki_list, outputs=wiki_list_display)
        clear_wiki_btn.click(
            fn=on_clear_index,
            outputs=clear_result,
        )

        # Chat
        def handle_chat(msg, history):
            # First, get the generator from on_chat_message
            for new_history, _ in on_chat_message(msg, history):
                # Extract file paths from the last message to update the "Found Files" area
                last_content = new_history[-1]["content"] if new_history else ""
                import re
                paths = re.findall(r"\[APRI:\s*(.*?)\]", last_content)
                
                html_list = "<div style='display: flex; flex-wrap: wrap; gap: 10px;'>"
                if not paths:
                    html_list += "<p style='opacity: 0.5;'>Nessun file trovato in questo messaggio.</p>"
                for p in paths:
                    fname = Path(p).name
                    html_list += f"""
                    <button onclick="document.querySelector('#open-trigger-input').value='{p}'; 
                                     document.querySelector('#open-trigger-input').dispatchEvent(new Event('submit'))" 
                            style="padding: 8px 15px; background: #2d3436; color: white; border: none; border-radius: 5px; cursor: pointer; border-left: 4px solid #00b894;">
                        📄 Apri {fname}
                    </button>
                    """
                html_list += "</div>"
                
                yield new_history, "", html_list

        # Assign unique ID to open_trigger for JS selection
        open_trigger.elem_id = "open-trigger-input"

        send_btn.click(
            fn=handle_chat,
            inputs=[chat_input, chatbot],
            outputs=[chatbot, chat_input, found_files_container],
        )
        chat_input.submit(
            fn=handle_chat,
            inputs=[chat_input, chatbot],
            outputs=[chatbot, chat_input, found_files_container],
        )
        
        open_trigger.submit(fn=on_open_local_file, inputs=open_trigger, outputs=open_status)

        # Footer
        gr.HTML(
            """
            <div class="privacy-footer">
                🔒 PrivateSearch Wiki Edition — 100% Criptato. Nessun dato lascia il tuo PC.
            </div>
            """
        )

        app.load(fn=on_check_system, outputs=system_status)

    return app


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    """Launch the application."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Don't init components until unlocked
    
    app = create_app()
    app.launch(
        server_name=GRADIO_HOST,
        server_port=GRADIO_PORT,
        share=False,
        show_error=True,
    )


if __name__ == "__main__":
    main()
