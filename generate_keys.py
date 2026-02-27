#!/usr/bin/env python3
"""
Script para gerar chaves de segurança fortes.
Execute este script e copie as chaves geradas para o arquivo .env
"""
import secrets
from cryptography.fernet import Fernet

print("=" * 60)
print("GERADOR DE CHAVES DE SEGURANÇA")
print("=" * 60)
print()

# Gera SECRET_KEY forte (64 caracteres hexadecimais = 256 bits)
secret_key = secrets.token_hex(32)
print("SECRET_KEY (copie para o .env):")
print(f"SECRET_KEY={secret_key}")
print()

# Gera senha forte para admin
admin_password = secrets.token_urlsafe(16)
print("ADMIN_PASS (copie para o .env e guarde em local seguro):")
print(f"ADMIN_PASS={admin_password}")
print()

# Gera chave Fernet para criptografia de tokens
fernet_key = Fernet.generate_key()
encryption_key = fernet_key.hex()
print("ENCRYPTION_KEY (para criptografar tokens - adicione ao .env):")
print(f"ENCRYPTION_KEY={encryption_key}")
print()

print("=" * 60)
print("IMPORTANTE:")
print("1. Copie estas chaves para o arquivo .env")
print("2. NUNCA compartilhe estas chaves")
print("3. NUNCA commite o arquivo .env no Git")
print("4. Guarde a senha do admin em local seguro")
print("=" * 60)
