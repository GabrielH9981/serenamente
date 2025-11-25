# routes/ferramentas.py
from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from db.db import get_db_connection
from . import auth as auth_routes  # importa o módulo auth (com oauth)
import calendar
import datetime
import requests
import os

ferramentas_bp = Blueprint('ferramentas', __name__)

# constants / env
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


def refresh_google_tokens(user_id):
    """
    Usa refresh_token salvo no banco para obter novo access_token.
    Atualiza google_cal_access_token e google_cal_token_expiry no banco.
    Retorna dict com 'access_token' e 'expires_at' em caso de sucesso, ou None.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT google_cal_refresh_token
            FROM users WHERE id = %s
        """, (user_id,))
        row = cursor.fetchone()
        if not row or not row.get('google_cal_refresh_token'):
            return None

        refresh_token = row['google_cal_refresh_token']

        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }

        resp = requests.post(GOOGLE_TOKEN_URL, data=payload, timeout=10)
        if resp.status_code != 200:
            print("Refresh token failed:", resp.status_code, resp.text)
            return None

        token_data = resp.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in")  # segundos

        expiry_dt = None
        if expires_in:
            expiry_dt = datetime.datetime.utcnow() + datetime.timedelta(seconds=int(expires_in))

        # atualiza DB
        cur_upd = conn.cursor()
        cur_upd.execute("""
            UPDATE users
            SET google_cal_access_token = %s,
                google_cal_token_expiry = %s
            WHERE id = %s
        """, (access_token, expiry_dt, user_id))
        conn.commit()
        cur_upd.close()

        return {"access_token": access_token, "expires_at": expiry_dt}

    except Exception as e:
        print("Erro ao tentar refresh token:", e)
        return None
    finally:
        cursor.close()
        conn.close()


def get_events_from_calendar(access_token, time_min, time_max):
    """
    Faz a requisição à Calendar API e retorna o objeto Response.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "timeMin": time_min,
        "timeMax": time_max,
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": 250,
    }
    resp = requests.get(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers=headers,
        params=params,
        timeout=10
    )
    return resp


@ferramentas_bp.route('/ferramentas')
def ferramentas_home():
    """Página principal da agenda mensal do psicólogo."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    # --- LÊ MÊS / ANO DA URL ---
    hoje = datetime.date.today()
    ano = request.args.get("ano", type=int, default=hoje.year)
    mes = request.args.get("mes", type=int, default=hoje.month)

    # Garantir mês entre 1 e 12
    if mes < 1:
        mes = 12
        ano -= 1
    if mes > 12:
        mes = 1
        ano += 1

    # Primeiro e último dia do mês
    first_day = datetime.date(ano, mes, 1)
    last_day_num = calendar.monthrange(ano, mes)[1]
    last_day = datetime.date(ano, mes, last_day_num)

    # Intervalo pro Google Calendar
    time_min = datetime.datetime.combine(first_day, datetime.time.min).isoformat() + 'Z'

    # primeiro dia do mês seguinte
    if mes == 12:
        next_month_first = datetime.date(ano + 1, 1, 1)
    else:
        next_month_first = datetime.date(ano, mes + 1, 1)

    time_max = datetime.datetime.combine(next_month_first, datetime.time.min).isoformat() + 'Z'

    # Label do mês
    meses_pt = [
        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    month_label = f"{meses_pt[mes]} / {ano}"

    # Cálculo da paginação
    if mes == 1:
        prev_month, prev_year = 12, ano - 1
    else:
        prev_month, prev_year = mes - 1, ano

    if mes == 12:
        next_month, next_year = 1, ano + 1
    else:
        next_month, next_year = mes + 1, ano

    # ----------------------------
    # CARREGAR TOKEN DO BANCO
    # ----------------------------
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT google_cal_access_token FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    calendar_connected = bool(user and user.get("google_cal_access_token"))
    events = []
    error_msg = None

    if calendar_connected:
        access_token = user["google_cal_access_token"]

        headers = {"Authorization": f"Bearer {access_token}"}

        params = {
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": 200
        }

        try:
            resp = requests.get(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers=headers,
                params=params,
                timeout=10
            )

            if resp.status_code == 401:
                calendar_connected = False
                error_msg = "Token expirado ou inválido. Reconecte sua Google Agenda."
            else:
                resp.raise_for_status()
                items = resp.json().get("items", [])

                # Normalizar eventos
                for ev in items:
                    start_data = ev.get("start", {})
                    dt_raw = start_data.get("dateTime") or start_data.get("date") or ""

                    if "T" in dt_raw:
                        date_part, time_part = dt_raw.split("T", 1)
                        time_part = time_part[:5]
                    else:
                        date_part = dt_raw
                        time_part = ""

                    events.append({
                        "id": ev.get("id"),
                        "summary": ev.get("summary", "(Sem título)"),
                        "description": ev.get("description", "") or "",
                        "date": date_part,
                        "time": time_part
                    })


        except Exception as e:
            print("Erro ao consultar Google Calendar:", e)
            error_msg = "Erro ao carregar a agenda do Google."

    # -----------------------------------
    # CONSTRUIR ESTRUTURA DO CALENDÁRIO
    # -----------------------------------
    # Primeiro dia da semana (0=Seg → queremos 6=Sab) Google usa Domingo=0,
    # Python usa Segunda=0, então adaptamos:
    first_weekday = (first_day.weekday() + 1) % 7  # domingo=0

    # Criar dias vazios antes do dia 1
    calendar_days = []

    for _ in range(first_weekday):
        calendar_days.append({
            "day": "",
            "date": "",
            "is_today": False,
            "events": []
        })

    # Dias reais
    for dia in range(1, last_day_num + 1):
        data_str = f"{ano}-{mes:02d}-{dia:02d}"

        # eventos desse dia
        day_events = [ev for ev in events if ev["date"] == data_str]

        calendar_days.append({
            "day": dia,
            "date": data_str,
            "is_today": (data_str == hoje.strftime("%Y-%m-%d")),
            "events": day_events
        })

    return render_template(
        "agenda.html",
        calendar_connected=calendar_connected,
        calendar_days=calendar_days,
        month_label=month_label,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        error_msg=error_msg
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
    print("REDIRECT URI CALENDAR:", redirect_uri)

    return oauth.google.authorize_redirect(
        redirect_uri,
        scope="openid email profile https://www.googleapis.com/auth/calendar",
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )


@ferramentas_bp.route('/ferramentas/google-calendar/callback')
def google_calendar_callback():
    """Callback chamado pelo Google após o usuário aceitar a permissão da Agenda."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    oauth = auth_routes.oauth
    if oauth is None:
        return redirect(url_for('ferramentas.ferramentas_home'))

    # Tenta obter o token
    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        print("Erro ao obter token do Google Calendar:", e)
        return redirect(url_for('ferramentas.ferramentas_home'))

    access_token = token.get('access_token')
    new_refresh_token = token.get('refresh_token')  # pode vir None
    expires_at = token.get('expires_at')

    expiry_dt = None
    if expires_at:
        try:
            expiry_dt = datetime.datetime.utcfromtimestamp(expires_at)
        except:
            expiry_dt = None

    # Buscar refresh_token atual no banco
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT google_cal_refresh_token
        FROM users
        WHERE id = %s
    """, (session['user_id'],))

    row = cursor.fetchone()
    old_refresh_token = row["google_cal_refresh_token"] if row else None

    # Se o Google NÃO enviou refresh_token novo, mantém o antigo.
    refresh_token_to_save = new_refresh_token if new_refresh_token else old_refresh_token

    # Agora salva tokens
    cursor2 = conn.cursor()
    cursor2.execute("""
        UPDATE users
        SET google_cal_access_token  = %s,
            google_cal_refresh_token = %s,
            google_cal_token_expiry  = %s
        WHERE id = %s
    """, (
        access_token,
        refresh_token_to_save,
        expiry_dt,
        session['user_id']
    ))

    conn.commit()
    cursor2.close()
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

    tz = 'America/Sao_Paulo'

    try:
        start_dt = datetime.datetime.fromisoformat(f"{data}T{hora_inicio}:00")
        if hora_fim:
            end_dt = datetime.datetime.fromisoformat(f"{data}T{hora_fim}:00")
        else:
            end_dt = start_dt + datetime.timedelta(minutes=50)

        # monta strings com offset -03:00 (suficiente pra dev)
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

        # Se token expirou, tenta refresh e reenvia
        if resp.status_code == 401:
            refreshed = refresh_google_tokens(session['user_id'])
            if refreshed and refreshed.get('access_token'):
                headers["Authorization"] = f"Bearer {refreshed['access_token']}"
                resp = requests.post(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    headers=headers,
                    json=body,
                    timeout=10
                )

        resp.raise_for_status()

    except Exception as e:
        print("Erro ao criar evento na Google Calendar:", e)
        # opcional: flash pra UI
        flash("Não foi possível criar o evento na Google Agenda.", "danger")

    return redirect(url_for('ferramentas.ferramentas_home'))


@ferramentas_bp.route('/ferramentas/google-calendar/desconectar', methods=['POST'])
def desconectar_google_calendar():
    """Limpa tokens da Google Agenda do usuário."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE users
            SET google_cal_access_token=NULL, google_cal_refresh_token=NULL, google_cal_token_expiry=NULL
            WHERE id = %s
        """, (session['user_id'],))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('ferramentas.ferramentas_home'))


from urllib.parse import quote_plus
from flask import jsonify

@ferramentas_bp.route('/ferramentas/agenda/deletar', methods=['POST'])
def deletar_evento_agenda():
    """Deleta um evento na Google Calendar pelo eventId."""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "not_authenticated"}), 401

    event_id = request.form.get('event_id') or request.json.get('event_id')
    if not event_id:
        return jsonify({"success": False, "error": "missing_event_id"}), 400

    # pega token do DB
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT google_cal_access_token FROM users WHERE id = %s", (session['user_id'],))
        row = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not row or not row.get('google_cal_access_token'):
        return jsonify({"success": False, "error": "no_token"}), 400

    access_token = row['google_cal_access_token']

    # tenta deletar
    url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{quote_plus(event_id)}"
    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.delete(url, headers=headers, timeout=10)

    # se expirou token, tenta refresh e reenvia
    if resp.status_code == 401:
        refreshed = refresh_google_tokens(session['user_id'])
        if refreshed and refreshed.get('access_token'):
            headers["Authorization"] = f"Bearer {refreshed['access_token']}"
            resp = requests.delete(url, headers=headers, timeout=10)

    if resp.status_code in (200, 204):
        return jsonify({"success": True})
    else:
        # retorna o body do Google pra debugging
        try:
            return jsonify({"success": False, "status": resp.status_code, "body": resp.json()}), 400
        except Exception:
            return jsonify({"success": False, "status": resp.status_code, "body": resp.text}), 400


@ferramentas_bp.route('/ferramentas/agenda/editar', methods=['POST'])
def editar_evento_agenda():
    """Edita um evento existente na Google Calendar."""
    if 'user_id' not in session:
        return jsonify({"success": False, "error": "not_authenticated"}), 401

    data = request.form or request.json or {}
    event_id = data.get('event_id')
    titulo = data.get('titulo')
    data_day = data.get('data')    # yyyy-mm-dd
    hora_inicio = data.get('hora_inicio')  # HH:MM
    hora_fim = data.get('hora_fim')        # HH:MM (opcional)
    descricao = data.get('descricao', '')

    if not event_id or not data_day or not hora_inicio:
        return jsonify({"success": False, "error": "missing_fields"}), 400

    # pega token
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT google_cal_access_token FROM users WHERE id = %s", (session['user_id'],))
        row = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    if not row or not row.get('google_cal_access_token'):
        return jsonify({"success": False, "error": "no_token"}), 400

    access_token = row['google_cal_access_token']
    tz = 'America/Sao_Paulo'

    try:
        start_dt = datetime.datetime.fromisoformat(f"{data_day}T{hora_inicio}:00")
        if hora_fim:
            end_dt = datetime.datetime.fromisoformat(f"{data_day}T{hora_fim}:00")
        else:
            end_dt = start_dt + datetime.timedelta(minutes=50)

        start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")
        end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S-03:00")

        url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{quote_plus(event_id)}"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        body = {
            "summary": titulo,
            "description": descricao,
            "start": {"dateTime": start_iso, "timeZone": tz},
            "end": {"dateTime": end_iso, "timeZone": tz}
        }

        resp = requests.patch(url, headers=headers, json=body, timeout=10)

        if resp.status_code == 401:
            refreshed = refresh_google_tokens(session['user_id'])
            if refreshed and refreshed.get('access_token'):
                headers["Authorization"] = f"Bearer {refreshed['access_token']}"
                resp = requests.patch(url, headers=headers, json=body, timeout=10)

        resp.raise_for_status()
        return jsonify({"success": True, "event": resp.json()})
    except Exception as e:
        print("Erro ao editar evento:", e)
        try:
            return jsonify({"success": False, "error": str(e)}), 500
        except:
            return jsonify({"success": False, "error": "unknown"}), 500

