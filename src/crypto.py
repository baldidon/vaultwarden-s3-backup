import os
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


SALT_SIZE = 16
NONCE_SIZE = 12
KEY_DERIVATION_ITERATIONS = 600_000


def _derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        KEY_DERIVATION_ITERATIONS,
    )


def encrypt_file(input_path: str, output_path: str, password: str) -> None:
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)

    plaintext = Path(input_path).read_bytes()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    with open(output_path, "wb") as f:
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)


def decrypt_file(input_path: str, output_path: str, password: str) -> None:
    data = Path(input_path).read_bytes()

    salt = data[:SALT_SIZE]
    nonce = data[SALT_SIZE : SALT_SIZE + NONCE_SIZE]
    ciphertext = data[SALT_SIZE + NONCE_SIZE :]

    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    Path(output_path).write_bytes(plaintext)
