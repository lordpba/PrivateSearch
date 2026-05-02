import json
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional
from app.core.security import security
from app.config import DATA_DIR

logger = logging.getLogger(__name__)

class WikiEntry:
    def __init__(self, filename: str, filepath: str, summary: str, category: str = "general"):
        self.filename = filename
        self.filepath = filepath
        self.summary = summary
        self.category = category

    def to_dict(self):
        return {
            "filename": self.filename,
            "filepath": self.filepath,
            "summary": self.summary,
            "category": self.category
        }

class WikiStore:
    """Manages an encrypted collection of file summaries (Wiki)."""

    def __init__(self, vault_name: str = "default_vault"):
        self.vault_path = DATA_DIR / f"{vault_name}.wiki.enc"
        self.entries: List[Dict] = []

    def load(self) -> bool:
        """Load and decrypt the wiki entries."""
        if not self.vault_path.exists():
            self.entries = []
            return True

        try:
            with open(self.vault_path, "rb") as f:
                encrypted_data = f.read()
            
            decrypted_json = security.decrypt(encrypted_data)
            self.entries = json.loads(decrypted_json)
            return True
        except Exception as e:
            logger.error(f"Failed to load vault: {e}")
            return False

    def save(self) -> bool:
        """Encrypt and save the current entries."""
        if not security.is_unlocked:
            logger.error("Cannot save vault while locked.")
            return False

        try:
            json_data = json.dumps(self.entries, indent=2)
            encrypted_data = security.encrypt(json_data)
            
            with open(self.vault_path, "wb") as f:
                f.write(encrypted_data)
            return True
        except Exception as e:
            logger.error(f"Failed to save vault: {e}")
            return False

    def add_entry(self, entry: WikiEntry):
        """Add or update an entry for a file."""
        # Remove existing entry for the same path
        self.entries = [e for e in self.entries if e["filepath"] != entry.filepath]
        self.entries.append(entry.to_dict())

    def search_by_filename(self, query: str) -> List[Dict]:
        """Simple keyword search in filenames."""
        q = query.lower()
        return [e for e in self.entries if q in e["filename"].lower()]

    def clear(self):
        """Empty the wiki."""
        self.entries = []
        if self.vault_path.exists():
            self.vault_path.unlink()

    @property
    def is_empty(self) -> bool:
        return len(self.entries) == 0
