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

    hoje = datetime.datetime.now()

    cursor.execute("""
                SELECT ac.user_id, ac.activated_at, ac.plan_duration_days
                FROM activation_codes ac
                JOIN users u ON ac.user_id = u.id
                WHERE ac.user_id = 3 AND ac.activated_at IS NOT NULL
            """)

    for user_id, ativado_em, dias in cursor.fetchall():
        data_expiracao = ativado_em + datetime.timedelta(days=dias)
        plan_days = data_expiracao - datetime.datetime.now()
        print(plan_days.days)

    conn.commit()
    cursor.close()
    conn.close()
#
#
# Execute:
desativar_usuarios_expirados()
