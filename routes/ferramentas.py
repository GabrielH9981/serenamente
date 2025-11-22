# routes/ferramentas.py
from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from db.db import get_db_connection
from . import auth as auth_routes  # ✅ importa o módulo inteiro
import calendar   # 👈 adiciona isso
import datetime
import requests

ferramentas_bp = Blueprint('ferramentas', __name__)


@ferramentas_bp.route('/ferramentas')
def ferramentas_home():
    """Página principal de ferramentas (agenda)."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT google_cal_access_token
            FROM users
            WHERE id = %s
        """, (session['user_id'],))
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    calendar_connected = bool(user and user.get('google_cal_access_token'))
    events = []
    error_msg = None

    if calendar_connected:
        access_token = user['google_cal_access_token']

        try:
            headers = {"Authorization": f"Bearer {access_token}"}

            # intervalo: mês atual inteiro
            today = datetime.date.today()
            first_day = today.replace(day=1)

            # primeiro dia do próximo mês (limite superior exclusivo)
            if today.month == 12:
                next_month_first = datetime.date(today.year + 1, 1, 1)
            else:
                next_month_first = datetime.date(today.year, today.month + 1, 1)

            time_min = datetime.datetime.combine(first_day, datetime.time.min).isoformat() + 'Z'
            time_max = datetime.datetime.combine(next_month_first, datetime.time.min).isoformat() + 'Z'

            # label bonitinho pro template (ex: Novembro/2025)
            meses_pt = [
                "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
            ]
            current_month_label = f"{meses_pt[today.month]}/{today.year}"

            params = {
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": True,
                "orderBy": "startTime",
                "maxResults": 50,
            }

            resp = requests.get(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers=headers,
                params=params,
                timeout=10
            )

            if resp.status_code == 401:
                calendar_connected = False
                error_msg = "Token expirado ou inválido. Tente reconectar sua Google Agenda."
            else:
                resp.raise_for_status()
                items = resp.json().get("items", [])

                for ev in items:
                    summary = ev.get("summary", "(Sem título)")

                    start_data = ev.get("start", {}) or {}
                    dt_raw = start_data.get("dateTime") or start_data.get("date") or ""

                    date_str = ""
                    time_str = ""

                    if "T" in dt_raw:
                        date_part, time_part = dt_raw.split("T", 1)
                        date_str = date_part
                        time_str = time_part[:5]  # HH:MM
                    else:
                        date_str = dt_raw

                    events.append({
                        "summary": summary,
                        "date": date_str,
                        "time": time_str,
                    })

        except Exception as e:
            print("Erro ao consultar Google Calendar:", e)
            error_msg = "Não foi possível carregar os eventos da Google Agenda no momento."

    return render_template(
        'agenda.html',
        calendar_connected=calendar_connected,
        events=events,
        error_msg=error_msg,
        current_month=current_month_label  # 👈 novo
    )


@ferramentas_bp.route('/ferramentas/google-calendar/conectar')
def conectar_google_calendar():
    """Inicia o fluxo de OAuth para conectar a Google Agenda."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    oauth = auth_routes.oauth
    if oauth is None:
        print("OAuth ainda não foi inicializado em auth_routes.oauth")
        return redirect(url_for('ferramentas.ferramentas_home'))

    redirect_uri = url_for('ferramentas.google_calendar_callback', _external=True)
    print("REDIRECT URI CALENDAR:", redirect_uri)  # 👈 LOG IMPORTANTE

    return oauth.google.authorize_redirect(
        redirect_uri,
        scope="openid email profile https://www.googleapis.com/auth/calendar",
        access_type="offline",
        prompt="consent"
    )



@ferramentas_bp.route('/ferramentas/google-calendar/callback')
def google_calendar_callback():
    """Callback chamado pelo Google após o usuário aceitar a permissão da Agenda."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    oauth = auth_routes.oauth  # ✅ de novo, pega do módulo auth
    if oauth is None:
        return redirect(url_for('ferramentas.ferramentas_home'))

    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        print("Erro ao obter token do Google Calendar:", e)
        return redirect(url_for('ferramentas.ferramentas_home'))

    access_token = token.get('access_token')
    refresh_token = token.get('refresh_token')
    expires_at = token.get('expires_at')  # timestamp (segundos desde epoch)

    expiry_dt = None
    if expires_at:
        try:
            expiry_dt = datetime.datetime.utcfromtimestamp(expires_at)
        except Exception:
            expiry_dt = None

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE users
            SET google_cal_access_token  = %s,
                google_cal_refresh_token = %s,
                google_cal_token_expiry  = %s
            WHERE id = %s
        """, (access_token, refresh_token, expiry_dt, session['user_id']))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('ferramentas.ferramentas_home'))


@ferramentas_bp.route('/ferramentas/agenda/criar', methods=['POST'])
def criar_evento_agenda():
    """Cria um evento na Google Agenda do usuário."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    # pega tokens do banco
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT google_cal_access_token
            FROM users
            WHERE id = %s
        """, (session['user_id'],))
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not user or not user.get('google_cal_access_token'):
        # sem token → manda reconectar
        return redirect(url_for('ferramentas.ferramentas_home'))

    access_token = user['google_cal_access_token']

    # pega dados do form
    titulo = request.form.get('titulo') or 'Atendimento'
    data = request.form.get('data')         # yyyy-mm-dd
    hora_inicio = request.form.get('hora_inicio')  # HH:MM
    hora_fim = request.form.get('hora_fim')        # HH:MM (opcional)

    if not data or not hora_inicio:
        return redirect(url_for('ferramentas.ferramentas_home'))

    # monta horários em timezone do Brasil (ajusta se quiser outro)
    tz = 'America/Sao_Paulo'

    try:
        start_dt = datetime.datetime.fromisoformat(f"{data}T{hora_inicio}:00")
        if hora_fim:
            end_dt = datetime.datetime.fromisoformat(f"{data}T{hora_fim}:00")
        else:
            # se não informar fim, soma 50 minutos
            end_dt = start_dt + datetime.timedelta(minutes=50)

        # monta strings com offset -03:00 (simples – suficiente pra dev)
        start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")
        end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        body = {
            "summary": titulo,
            "start": {
                "dateTime": start_iso,
                "timeZone": tz
            },
            "end": {
                "dateTime": end_iso,
                "timeZone": tz
            }
        }

        resp = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers=headers,
            json=body,
            timeout=10
        )
        resp.raise_for_status()

    except Exception as e:
        print("Erro ao criar evento na Google Calendar:", e)

    # independente do resultado, volta pra tela da agenda
    return redirect(url_for('ferramentas.ferramentas_home'))
