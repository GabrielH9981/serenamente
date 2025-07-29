# routes/ativacao.py
from flask import Blueprint, render_template, request, session, redirect, url_for
from db.db import get_db_connection
from datetime import datetime

ativacao_bp = Blueprint('ativacao', __name__)


@ativacao_bp.route('/ativar', methods=['GET', 'POST'])
def ativar_conta():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        codigo = request.form.get('codigo')
        user_id_logado = session['user_id']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT ac.user_id, ac.plan_duration_days FROM activation_codes ac
            JOIN users u ON ac.user_id = u.id
            WHERE ac.code = %s AND ac.user_id = %s AND u.is_active = 0 AND ac.activated_at IS NULL
        """, (codigo, user_id_logado))
        result = cursor.fetchone()

        if result:
            now = datetime.now()
            cursor.execute("UPDATE users SET is_active = 1 WHERE id = %s", (user_id_logado,))
            cursor.execute("UPDATE activation_codes SET activated_at = %s, used = 1 WHERE code = %s", (now, codigo))
            conn.commit()
            cursor.close()
            conn.close()

            return """
            <script>
                alert("Conta ativada com sucesso!");
                window.location.href = "/";
            </script>
            """
        else:
            cursor.close()
            conn.close()
            return """
            <script>
                alert("Código inválido, expirado ou não pertence à sua conta.");
                window.location.href = "/ativar";
            </script>
            """

    return render_template("ativar.html")
