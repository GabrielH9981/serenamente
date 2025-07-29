import mysql.connector
import secrets
import string
import datetime

def gerar_codigo_ativacao(user_id, dias_plano):
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="catalogo_psicologos"
    )
    cursor = conn.cursor()

    codigo = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

    cursor.execute("""
        INSERT INTO activation_codes (user_id, code, plan_duration_days, created_at)
        VALUES (%s, %s, %s, NOW())
    """, (user_id, codigo, dias_plano))

    conn.commit()
    cursor.close()
    conn.close()
    return codigo

user_id = int(input("ID do usuário para gerar código: "))
dias_plano = int(input("Plano (30/90/180): "))
# Exemplo de uso:
print("Código gerado:")
print(gerar_codigo_ativacao(user_id, dias_plano))
