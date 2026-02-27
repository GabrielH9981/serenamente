# utils/encryption.py
"""
Módulo para criptografia de dados sensíveis (tokens, etc).
Usa Fernet (criptografia simétrica) do cryptography.
"""
import os
from cryptography.fernet import Fernet
from typing import Optional
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()


def get_encryption_key() -> bytes:
    """
    Obtém a chave de criptografia do ambiente.
    
    Returns:
        bytes: Chave de criptografia
        
    Raises:
        ValueError: Se ENCRYPTION_KEY não estiver configurada
    """
    key = os.getenv('ENCRYPTION_KEY')
    if not key:
        raise ValueError("ENCRYPTION_KEY não configurada no .env")
    
    # Converte hex string para bytes
    return bytes.fromhex(key)


def encrypt_token(token: str) -> Optional[str]:
    """
    Criptografa um token.
    
    Args:
        token: Token em texto plano
        
    Returns:
        str: Token criptografado (base64) ou None se falhar
    """
    if not token:
        return None
    
    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted = f.encrypt(token.encode('utf-8'))
        return encrypted.decode('utf-8')
    except Exception as e:
        print(f"Erro ao criptografar token: {e}")
        return None


def decrypt_token(encrypted_token: str) -> Optional[str]:
    """
    Descriptografa um token.
    
    Args:
        encrypted_token: Token criptografado (base64)
        
    Returns:
        str: Token em texto plano ou None se falhar
    """
    if not encrypted_token:
        return None
    
    try:
        key = get_encryption_key()
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_token.encode('utf-8'))
        return decrypted.decode('utf-8')
    except Exception as e:
        print(f"Erro ao descriptografar token: {e}")
        return None
