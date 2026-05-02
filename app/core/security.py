import base64
import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.fernet import Fernet, InvalidToken

class VaultSecurity:
    """Handles encryption and decryption of the Wiki Vault."""

    def __init__(self):
        self._fernet = None
        self._salt = b'PrivateSearchSalt'  # In a production app, this should be unique and stored

    def derive_key(self, password: str) -> bool:
        """Derive a cryptographic key from the password."""
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self._salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            self._fernet = Fernet(key)
            return True
        except Exception:
            return False

    def encrypt(self, data: str) -> bytes:
        """Encrypt string data."""
        if not self._fernet:
            raise ValueError("Vault is locked. Unlock with password first.")
        return self._fernet.encrypt(data.encode())

    def decrypt(self, encrypted_data: bytes) -> str:
        """Decrypt bytes data back to string."""
        if not self._fernet:
            raise ValueError("Vault is locked. Unlock with password first.")
        try:
            return self._fernet.decrypt(encrypted_data).decode()
        except InvalidToken:
            raise ValueError("Invalid password or corrupted data.")

    @property
    def is_unlocked(self) -> bool:
        return self._fernet is not None

# Global security instance
security = VaultSecurity()
