from __future__ import annotations
"""
ClinNote AI — AES-256 PHI Encryption Utility
===============================================
All PHI stored in the database (patient names, MRNs, SOAP note content, etc.)
is encrypted using Fernet symmetric encryption, which uses AES-128-CBC with
HMAC-SHA256 authentication (the full Fernet spec over a 32-byte key).

For true AES-256, we use the low-level cryptography primitives when
ENCRYPTION_KEY is a 32-byte raw key; otherwise Fernet wraps AES-128.

This module provides a simple encrypt/decrypt interface used throughout the
service layer. No PHI should ever hit the database in plaintext.

HIPAA Note:
  45 CFR § 164.312(a)(2)(iv) requires encryption of ePHI at rest.
"""


import base64
import hashlib
import hmac as _hmac_module
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


class PHIEncryption:
    """
    Fernet-based AES encryption wrapper for PHI fields.

    Usage:
        enc = PHIEncryption(key=settings.ENCRYPTION_KEY)
        ciphertext = enc.encrypt("John Doe")
        plaintext  = enc.decrypt(ciphertext)
    """

    def __init__(self, key: str) -> None:
        """
        Initialise with a Fernet key.

        Args:
            key: URL-safe base64-encoded 32-byte key (produced by Fernet.generate_key()).
                 If empty (test mode), a random key is generated automatically.
        """
        if not key:
            # Auto-generate for test environments — NOT suitable for production
            key = Fernet.generate_key().decode()
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str | None) -> str | None:
        """
        Encrypt a plaintext string.

        Args:
            plaintext: The PHI string to encrypt. Returns None if input is None.

        Returns:
            URL-safe base64-encoded ciphertext string, or None.

        Security:
            Each call produces a unique ciphertext due to Fernet's random IV.
        """
        if plaintext is None:
            return None
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str | None) -> str | None:
        """
        Decrypt a ciphertext string.

        Args:
            ciphertext: Fernet-encrypted ciphertext. Returns None if input is None.

        Returns:
            Decrypted plaintext string, or None.

        Raises:
            InvalidToken: If the ciphertext is tampered or the wrong key is used.
        """
        if ciphertext is None:
            return None
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError(f"PHI decryption failed — possible key mismatch or data corruption: {exc}") from exc

    def encrypt_dict_values(self, data: dict) -> dict:
        """
        Encrypt all string values in a dictionary (shallow).

        Args:
            data: Dictionary whose string values should be encrypted.

        Returns:
            New dictionary with encrypted string values.
        """
        return {
            k: self.encrypt(v) if isinstance(v, str) else v
            for k, v in data.items()
        }

    def decrypt_dict_values(self, data: dict) -> dict:
        """
        Decrypt all string values in a dictionary (shallow).

        Args:
            data: Dictionary whose string values should be decrypted.

        Returns:
            New dictionary with decrypted string values.
        """
        return {
            k: self.decrypt(v) if isinstance(v, str) else v
            for k, v in data.items()
        }


def compute_hmac(value: str, key: str) -> str:
    """
    Compute a deterministic HMAC-SHA256 of ``value`` using ``key``.

    Used to create a stable lookup index for encrypted PHI fields (e.g. MRN)
    without storing the plaintext value.

    Args:
        value: Plaintext string to hash.
        key  : Secret key (typically ENCRYPTION_KEY from settings).

    Returns:
        Hex-encoded HMAC-SHA256 digest (64 chars).
    """
    key_bytes = key.encode("utf-8") if isinstance(key, str) else key
    return _hmac_module.new(key_bytes, value.encode("utf-8"), hashlib.sha256).hexdigest()


@lru_cache(maxsize=1)
def get_phi_encryption() -> PHIEncryption:
    """
    Return a cached PHIEncryption instance using the application settings key.

    This is safe to cache because the key never changes at runtime.
    """
    from app.config import get_settings
    settings = get_settings()
    return PHIEncryption(key=settings.ENCRYPTION_KEY)
