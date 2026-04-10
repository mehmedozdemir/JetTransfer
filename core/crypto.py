import os
from cryptography.fernet import Fernet

KEY_FILE = "machine.key"

class CryptoManager:
    @staticmethod
    def get_or_create_key() -> bytes:
        if not os.path.exists(KEY_FILE):
            key = Fernet.generate_key()
            with open(KEY_FILE, "wb") as key_file:
                key_file.write(key)
            return key
        else:
            with open(KEY_FILE, "rb") as key_file:
                return key_file.read()

    @staticmethod
    def encrypt(password: str) -> str:
        if not password:
            return ""
        key = CryptoManager.get_or_create_key()
        f = Fernet(key)
        return f.encrypt(password.encode()).decode()

    @staticmethod
    def decrypt(encrypted_password: str) -> str:
        if not encrypted_password:
            return ""
        key = CryptoManager.get_or_create_key()
        f = Fernet(key)
        return f.decrypt(encrypted_password.encode()).decode()
