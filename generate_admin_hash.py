#!/usr/bin/env python3
"""
Script para gerar hash da senha do admin.
Execute este script e copie o hash gerado para o arquivo .env
"""
import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()

# Pega a senha atual do .env
admin_pass = os.getenv('ADMIN_PASS')

if not admin_pass:
    print("ERRO: ADMIN_PASS não encontrada no .env")
    print("Execute generate_keys.py primeiro para gerar uma senha forte")
    exit(1)

# Gera o hash
password_bytes = admin_pass.encode('utf-8')
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(password_bytes, salt)
hashed_str = hashed.decode('utf-8')

print("=" * 60)
print("HASH DA SENHA DO ADMIN")
print("=" * 60)
print()
print("Senha original (guarde em local seguro):")
print(f"  {admin_pass}")
print()
print("Hash para colocar no .env:")
print(f"ADMIN_PASS_HASH={hashed_str}")
print()
print("=" * 60)
print("IMPORTANTE:")
print("1. Copie o ADMIN_PASS_HASH acima para o .env")
print("2. Mantenha a ADMIN_PASS original também (para você lembrar)")
print("3. O código vai usar o ADMIN_PASS_HASH para validação")
print("=" * 60)
