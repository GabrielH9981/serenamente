import mysql.connector
import datetime


def desativar_usuarios_expirados():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="catalogo_psicologos"
    )
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ac.user_id, ac.activated_at, ac.plan_duration_days
        FROM activation_codes ac
        JOIN users u ON ac.user_id = u.id
        WHERE u.is_active = 1 AND ac.activated_at IS NOT NULL
    """)

    hoje = datetime.datetime.now()

    for user_id, ativado_em, dias in cursor.fetchall():
        data_expiracao = ativado_em + datetime.timedelta(days=dias)
        if hoje > data_expiracao:
            print(f"Desativando usuário ID {user_id} (plano expirado em {data_expiracao})")
            #cursor.execute("UPDATE users SET is_active = 0 WHERE id = %s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()


# Execute:
desativar_usuarios_expirados()
