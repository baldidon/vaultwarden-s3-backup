import os
import tempfile

import pytest

from src.crypto import decrypt_file, encrypt_file


class TestEncryptDecryptRoundTrip:
    def test_round_trip(self, tmp_path):
        input_file = tmp_path / "plain.txt"
        encrypted_file = tmp_path / "plain.txt.enc"
        decrypted_file = tmp_path / "plain_restored.txt"

        input_file.write_text("Hello, Vaultwarden!")

        encrypt_file(str(input_file), str(encrypted_file), "my-password")
        assert encrypted_file.exists()
        assert encrypted_file.stat().st_size > 0

        decrypt_file(str(encrypted_file), str(decrypted_file), "my-password")
        assert decrypted_file.read_text() == "Hello, Vaultwarden!"

    def test_binary_round_trip(self, tmp_path):
        input_file = tmp_path / "data.bin"
        encrypted_file = tmp_path / "data.bin.enc"
        decrypted_file = tmp_path / "data_restored.bin"

        data = os.urandom(1024 * 64)
        input_file.write_bytes(data)

        encrypt_file(str(input_file), str(encrypted_file), "pw")
        decrypt_file(str(encrypted_file), str(decrypted_file), "pw")

        assert decrypted_file.read_bytes() == data

    def test_empty_file_round_trip(self, tmp_path):
        input_file = tmp_path / "empty.txt"
        encrypted_file = tmp_path / "empty.txt.enc"
        decrypted_file = tmp_path / "empty_restored.txt"

        input_file.write_bytes(b"")

        encrypt_file(str(input_file), str(encrypted_file), "pw")
        decrypt_file(str(encrypted_file), str(decrypted_file), "pw")

        assert decrypted_file.read_bytes() == b""

    def test_wrong_password_raises(self, tmp_path):
        input_file = tmp_path / "secret.txt"
        encrypted_file = tmp_path / "secret.txt.enc"

        input_file.write_text("secret data")
        encrypt_file(str(input_file), str(encrypted_file), "correct-password")

        with pytest.raises(Exception):
            decrypt_file(
                str(encrypted_file),
                str(tmp_path / "out.txt"),
                "wrong-password",
            )

    def test_encrypted_file_is_different(self, tmp_path):
        input_file = tmp_path / "data.txt"
        encrypted_file = tmp_path / "data.txt.enc"

        input_file.write_text("some data")
        encrypt_file(str(input_file), str(encrypted_file), "pw")

        assert encrypted_file.read_bytes() != input_file.read_bytes()

    def test_encrypted_file_has_salt_and_nonce(self, tmp_path):
        input_file = tmp_path / "data.txt"
        encrypted_file = tmp_path / "data.txt.enc"

        input_file.write_text("some data")
        encrypt_file(str(input_file), str(encrypted_file), "pw")

        raw = encrypted_file.read_bytes()
        assert len(raw) >= 16 + 12

    def test_different_salts_produce_different_ciphertext(self, tmp_path):
        input_file = tmp_path / "data.txt"
        enc1 = tmp_path / "enc1.bin"
        enc2 = tmp_path / "enc2.bin"

        input_file.write_text("same data")

        encrypt_file(str(input_file), str(enc1), "pw")
        encrypt_file(str(input_file), str(enc2), "pw")

        assert enc1.read_bytes() != enc2.read_bytes()
