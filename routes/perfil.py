# routes/perfil.py
from flask import Blueprint, render_template, request, session, redirect, url_for
from db.db import get_db_connection
import os, base64
from PIL import Image
from io import BytesIO
import datetime
from cloudinary.uploader import upload as cloudinary_upload
from utils.cloudinary_config import cloudinary
import json
from datetime import date, timedelta, time as dt_time, timezone
from routes.ferramentas import refresh_google_tokens, get_events_from_calendar
from routes import psicologos as psic_mod  # para reutilizar iso_to_utc_ts e comparadores

perfil_bp = Blueprint('perfil', __name__)


@perfil_bp.route('/perfil', methods=['GET', 'POST'])
def perfil():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # select dos dados cadastrados no perfil
    cursor.execute("SELECT * FROM profiles WHERE user_id = %s", (session['user_id'],))
    profile = cursor.fetchone()

    # select dos dias restantes de plano (mantive sua lógica)
    cursor.execute("""
            SELECT ac.user_id, ac.activated_at, ac.plan_duration_days
            FROM activation_codes ac
            JOIN users u ON ac.user_id = u.id
            WHERE ac.user_id = %s AND ac.activated_at IS NOT NULL
        """, (session['user_id'],))

    plan_days = 'SEM PLANO'
    for row in cursor.fetchall():
        dias = int(row['plan_duration_days'])
        ativado_em = row['activated_at']
        data_expiracao = ativado_em + datetime.timedelta(days=dias)
        plan_days = data_expiracao - datetime.datetime.now()
        plan_days = str(plan_days.days)

    if request.method == 'POST':
        cropped_data = request.form.get('cropped_image')
        image_filename = None

        if cropped_data:
            try:
                header, encoded = cropped_data.split(",", 1)
                data = base64.b64decode(encoded)
                img = Image.open(BytesIO(data)).convert("RGB")

                # Redimensiona
                img = img.resize((300, 300))

                # Converte para buffer
                buffer = BytesIO()
                img.save(buffer, format="JPEG")
                buffer.seek(0)

                # Upload para Cloudinary
                result = cloudinary_upload(
                    buffer,
                    folder="serenamente/perfis",
                    public_id=f"profile_{session['user_id']}",
                    overwrite=True
                )
                image_filename = result['secure_url']
            except Exception as e:
                print("Erro ao salvar imagem no Cloudinary:", e)


        # Função utilitária de truncamento
        def trunc(s, n):
            if s is None:
                return ''
            try:
                return s[:n]
            except Exception:
                return s

        # limites
        MAX_SHORT_BIO = 160
        MAX_FULL_BIO = 3000
        MAX_WEBSITE = 200
        MAX_HANDLE = 100
        MAX_WHATSAPP = 20
        MAX_CIDADE = 120
        MAX_RUA = 200
        MAX_NUMERO = 20
        MAX_AVAILABILITY_LENGTH = 15000  # máximo razoável para o JSON

        # novos campos de endereço
        online_estado = trunc(request.form.get('online_estado') or '', 2)
        pres_cep = trunc(request.form.get('pres_cep') or '', 9)
        pres_cidade = trunc(request.form.get('pres_cidade') or '', MAX_CIDADE)
        pres_estado = trunc(request.form.get('pres_estado') or '', 2)
        pres_rua = trunc(request.form.get('pres_rua') or '', MAX_RUA)
        pres_numero = trunc(request.form.get('pres_numero') or '', MAX_NUMERO)

        atendimento_online = 1 if request.form.get('atendimento_online') else 0
        atendimento_presencial = 1 if request.form.get('atendimento_presencial') else 0

        # monta location amigável
        location = ''
        if atendimento_presencial and pres_cep and pres_cidade and pres_rua and pres_numero and pres_estado:
            location = f"{pres_cep} - {pres_rua}, {pres_numero} - {pres_cidade.upper()} - {pres_estado}"
        elif atendimento_online and not atendimento_presencial and online_estado:
            location = online_estado

        # novos campos sociais (truncados)
        whatsapp_number = trunc(request.form.get('whatsapp_number') or '', MAX_WHATSAPP)

        instagram_handle = trunc((request.form.get('instagram_handle') or '').strip(), MAX_HANDLE)
        linkedin_handle = trunc((request.form.get('linkedin_handle') or '').strip(), MAX_HANDLE)
        tiktok_handle = trunc((request.form.get('tiktok_handle') or '').strip(), MAX_HANDLE)

        def build_url(base, handle, strip_at=False):
            if not handle:
                return ''
            h = handle.strip()
            if strip_at and h.startswith('@'):
                h = h[1:]
            h = h.lstrip('/').strip()
            # trunc novamente por segurança
            h = h[:MAX_HANDLE]
            return base + h

        instagram_url = build_url("https://instagram.com/", instagram_handle, strip_at=True)
        linkedin_url = build_url("https://linkedin.com/in/", linkedin_handle)
        tiktok_url = build_url("https://tiktok.com/@", tiktok_handle, strip_at=True)

        # disponibilidade (já fazia validação antes) -> validar/truncar
        availability_raw = request.form.get('availability', '') or ''
        availability_json = ''
        if availability_raw:
            try:
                parsed = json.loads(availability_raw)
                # opcional: validação superficial (cada start/end em formato HH:MM)
                # serializa com ensure_ascii=False para preservar acentos se houver
                availability_json = json.dumps(parsed, ensure_ascii=False)
                if len(availability_json) > MAX_AVAILABILITY_LENGTH:
                    # se muito grande, trunca (melhor decisão pode ser rejeitar; escolhi truncar)
                    availability_json = availability_json[:MAX_AVAILABILITY_LENGTH]
            except Exception as e:
                print("JSON de disponibilidade inválido:", e)
                availability_json = ''

        # campos textuais (truncados)
        short_bio = trunc(request.form.get('short_bio') or '', MAX_SHORT_BIO)
        full_bio = trunc(request.form.get('full_bio') or '', MAX_FULL_BIO)
        website_url = trunc(request.form.get('website_url') or '', MAX_WEBSITE)

        # modo de agendamento
        scheduling_mode = request.form.get('scheduling_mode') or 'manual'
        if scheduling_mode not in ('none', 'manual', 'auto'):
            scheduling_mode = 'manual'


        # monta dicionário data (substitui os campos anteriores)
        data = {
            'short_bio': short_bio,
            'full_bio': full_bio,
            'profile_picture_url': image_filename or (profile.get('profile_picture_url') if profile else ''),
            'location': location,
            'price_range': request.form.get('price_range'),
            'atendimento_online': atendimento_online,
            'atendimento_presencial': atendimento_presencial,
            'whatsapp_number': whatsapp_number,
            'instagram_url': instagram_url,
            'website_url': website_url,
            'online_estado': online_estado,
            'pres_cep': pres_cep,
            'pres_cidade': pres_cidade,
            'pres_estado': pres_estado,
            'pres_rua': pres_rua,
            'pres_numero': pres_numero,
            'linkedin_url': linkedin_url,
            'tiktok_url': tiktok_url,
            'availability': availability_json,
            'scheduling_mode': scheduling_mode
        }

        if profile:
            cursor.execute("""
                UPDATE profiles SET
                    short_bio=%s,
                    full_bio=%s,
                    profile_picture_url=%s,
                    location=%s,
                    price_range=%s,
                    atendimento_online=%s,
                    atendimento_presencial=%s,
                    whatsapp_number=%s,
                    instagram_url=%s,
                    website_url=%s,
                    online_estado=%s,
                    pres_cep=%s,
                    pres_cidade=%s,
                    pres_estado=%s,
                    pres_rua=%s,
                    pres_numero=%s,
                    linkedin_url=%s,
                    tiktok_url=%s,
                    availability=%s,
                    scheduling_mode=%s
                WHERE user_id=%s
            """, (
                data['short_bio'], data['full_bio'], data['profile_picture_url'], data['location'],
                data['price_range'], data['atendimento_online'], data['atendimento_presencial'],
                data['whatsapp_number'], data['instagram_url'], data['website_url'],
                data['online_estado'], data['pres_cep'], data['pres_cidade'],
                data['pres_estado'], data['pres_rua'], data['pres_numero'],
                data['linkedin_url'], data['tiktok_url'],
                data['availability'],
                data['scheduling_mode'],
                session['user_id']
            ))
        else:
            cursor.execute("""
                INSERT INTO profiles (
                    user_id, short_bio, full_bio, profile_picture_url, location,
                    price_range, atendimento_online, atendimento_presencial,
                    whatsapp_number, instagram_url, website_url,
                    online_estado, pres_cep, pres_cidade, pres_estado, pres_rua, pres_numero,
                    linkedin_url, tiktok_url, availability, scheduling_mode
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session['user_id'], data['short_bio'], data['full_bio'], data['profile_picture_url'],
                data['location'], data['price_range'], data['atendimento_online'],
                data['atendimento_presencial'], data['whatsapp_number'],
                data['instagram_url'], data['website_url'],
                data['online_estado'], data['pres_cep'], data['pres_cidade'],
                data['pres_estado'], data['pres_rua'], data['pres_numero'],
                data['linkedin_url'], data['tiktok_url'],
                data['availability'], data['scheduling_mode']
            ))

            conn.commit()
            cursor.execute("SELECT * FROM profiles WHERE user_id = %s", (session['user_id'],))
            profile = cursor.fetchone()

    profile_id = profile['id'] if profile else None

    cursor.execute("SELECT * FROM approaches")
    approaches = cursor.fetchall()
    cursor.execute("SELECT * FROM experiencias")
    experiencias = cursor.fetchall()
    cursor.execute("SELECT * FROM publicos_alvo")
    publicos = cursor.fetchall()

    selected_approaches, selected_experiencias, selected_publicos = [], [], []
    if profile_id:
        cursor.execute("SELECT approach_id FROM profile_approaches WHERE profile_id = %s", (profile_id,))
        selected_approaches = [row['approach_id'] for row in cursor.fetchall()]

        cursor.execute("SELECT experiencia_id FROM profile_experiencias WHERE profile_id = %s", (profile_id,))
        selected_experiencias = [row['experiencia_id'] for row in cursor.fetchall()]

        cursor.execute("SELECT publico_id FROM profile_publicos_alvo WHERE profile_id = %s", (profile_id,))
        selected_publicos = [row['publico_id'] for row in cursor.fetchall()]

    if request.method == 'POST' and profile_id:
        cursor.execute("DELETE FROM profile_approaches WHERE profile_id = %s", (profile_id,))
        selected_approach_id = request.form.get("approach")
        if selected_approach_id:
            cursor.execute(
                "INSERT INTO profile_approaches (profile_id, approach_id) VALUES (%s, %s)",
                (profile_id, selected_approach_id)
            )

        cursor.execute("DELETE FROM profile_experiencias WHERE profile_id = %s", (profile_id,))
        for eid in request.form.getlist("experiencias"):
            cursor.execute(
                "INSERT INTO profile_experiencias (profile_id, experiencia_id) VALUES (%s, %s)",
                (profile_id, eid)
            )

        cursor.execute("DELETE FROM profile_publicos_alvo WHERE profile_id = %s", (profile_id,))
        for pid in request.form.getlist("publicos"):
            cursor.execute(
                "INSERT INTO profile_publicos_alvo (profile_id, publico_id) VALUES (%s, %s)",
                (profile_id, pid)
            )

        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('perfil.perfil'))

    cursor.close()
    conn.close()

    return render_template(
        'perfil.html',
        profile=profile or {},
        approaches=approaches,
        experiencias=experiencias,
        publicos=publicos,
        selected_approaches=selected_approaches,
        selected_experiencias=selected_experiencias,
        selected_publicos=selected_publicos,
        plan_days=plan_days
    )


# Rota para gerar a prévia do perfil usando os dados do formulário (não salva nada)
@perfil_bp.route('/perfil/preview', methods=['POST'])
def perfil_preview():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    from routes.ferramentas import refresh_google_tokens, get_events_from_calendar
    from routes import psicologos as psic_mod  # reutilizar iso_to_utc_ts e slot_conflicts_with_events_ts
    import datetime  # garantir acesso ao módulo

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # dados atuais do usuário/perfil (fallback)
    cursor.execute("""
        SELECT u.name, u.crp, u.id AS user_id,
               u.google_cal_access_token, u.google_cal_refresh_token, u.google_cal_token_expiry,
               p.*
        FROM users u
        LEFT JOIN profiles p ON p.user_id = u.id
        WHERE u.id = %s
    """, (session['user_id'],))
    dbrow = cursor.fetchone() or {}

    # metadados
    cursor.execute("SELECT * FROM approaches")
    abordagens_all = cursor.fetchall()
    cursor.execute("SELECT * FROM experiencias")
    experiencias_all = cursor.fetchall()
    cursor.execute("SELECT * FROM publicos_alvo")
    publicos_all = cursor.fetchall()

    def safe(v, maxlen=None):
        if v is None:
            return ''
        s = str(v).strip()
        return s[:maxlen] if (maxlen and len(s) > maxlen) else s

    profile_temp = {}
    profile_temp['id'] = dbrow.get('id') or None
    profile_temp['name'] = dbrow.get('name') or ''
    profile_temp['crp'] = dbrow.get('crp') or ''

    # foto (usa dataURL do cropped se tiver)
    cropped = request.form.get('cropped_image') or ''
    if cropped:
        profile_temp['profile_picture_url'] = cropped
    else:
        profile_temp['profile_picture_url'] = dbrow.get('profile_picture_url') or ''

    # modo de agendamento (form > banco > default)
    scheduling_mode = request.form.get('scheduling_mode') or dbrow.get('scheduling_mode') or 'manual'
    if scheduling_mode not in ('none', 'manual', 'auto'):
        scheduling_mode = 'manual'
    profile_temp['scheduling_mode'] = scheduling_mode

    profile_temp['short_bio'] = safe(request.form.get('short_bio') or dbrow.get('short_bio') or '', 160)
    profile_temp['full_bio'] = safe(request.form.get('full_bio') or dbrow.get('full_bio') or '', 3000)
    profile_temp['price_range'] = safe(request.form.get('price_range') or dbrow.get('price_range') or '', 50)
    profile_temp['website_url'] = safe(request.form.get('website_url') or dbrow.get('website_url') or '', 200)
    profile_temp['whatsapp_number'] = safe(request.form.get('whatsapp_number') or dbrow.get('whatsapp_number') or '', 30)

    # redes sociais (prioriza o que veio do form)
    def build_url(base, handle, strip_at=False):
        if not handle:
            return ''
        h = handle.strip()
        if strip_at and h.startswith('@'):
            h = h[1:]
        h = h.lstrip('/').strip()
        return base + h

    profile_temp['instagram_url'] = build_url(
        "https://instagram.com/",
        safe(request.form.get('instagram_handle') or ''),
        strip_at=True
    ) or dbrow.get('instagram_url') or ''

    profile_temp['linkedin_url'] = build_url(
        "https://linkedin.com/in/",
        safe(request.form.get('linkedin_handle') or '')
    ) or dbrow.get('linkedin_url') or ''

    profile_temp['tiktok_url'] = build_url(
        "https://tiktok.com/@",
        safe(request.form.get('tiktok_handle') or ''),
        strip_at=True
    ) or dbrow.get('tiktok_url') or ''

    # modalidades
    atendimento_online = 1 if request.form.get('atendimento_online') else (1 if dbrow.get('atendimento_online') else 0)
    atendimento_presencial = 1 if request.form.get('atendimento_presencial') else (1 if dbrow.get('atendimento_presencial') else 0)
    profile_temp['atendimento_online'] = atendimento_online
    profile_temp['atendimento_presencial'] = atendimento_presencial

    # localização (pega do form e monta igual na rota /perfil)
    online_estado = request.form.get('online_estado') or dbrow.get('online_estado') or ''
    pres_cep = request.form.get('pres_cep') or dbrow.get('pres_cep') or ''
    pres_cidade = request.form.get('pres_cidade') or dbrow.get('pres_cidade') or ''
    pres_estado = request.form.get('pres_estado') or dbrow.get('pres_estado') or ''
    pres_rua = request.form.get('pres_rua') or dbrow.get('pres_rua') or ''
    pres_numero = request.form.get('pres_numero') or dbrow.get('pres_numero') or ''

    location = ''
    if (atendimento_presencial and pres_cep and pres_cidade and pres_rua and pres_numero and pres_estado):
        location = f"{pres_cep} - {pres_rua}, {pres_numero} - {pres_cidade.upper()} - {pres_estado}"
    elif atendimento_online and not atendimento_presencial and online_estado:
        location = online_estado

    profile_temp['location'] = location
    profile_temp['online_estado'] = online_estado
    profile_temp['pres_cep'] = pres_cep
    profile_temp['pres_cidade'] = pres_cidade
    profile_temp['pres_estado'] = pres_estado
    profile_temp['pres_rua'] = pres_rua
    profile_temp['pres_numero'] = pres_numero

    # disponibilidade (JSON)
    availability_raw = request.form.get('availability') or dbrow.get('availability') or ''
    try:
        availability_obj = json.loads(availability_raw) if availability_raw else {}
    except Exception:
        availability_obj = {}
    profile_temp['availability'] = availability_raw

    # coleções selecionadas (badges)
    selected_approach = request.form.get('approach')
    sel_exps = request.form.getlist('experiencias') or []
    sel_pubs = request.form.getlist('publicos') or []

    def filter_by_ids(all_list, ids):
        if not ids:
            return []
        ids_set = set(str(i) for i in ids)
        return [x for x in all_list if str(x.get('id')) in ids_set]

    abordagens = filter_by_ids(abordagens_all, [selected_approach] if selected_approach else [])
    experiencias = filter_by_ids(experiencias_all, sel_exps)
    publicos = filter_by_ids(publicos_all, sel_pubs)

    # -------- Google Calendar (se conectado) ----------
    busy_events_ts = []
    access_token = dbrow.get('google_cal_access_token')
    if access_token:
        try:
            now = datetime.datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + datetime.timedelta(days=30)).isoformat() + 'Z'

            resp = get_events_from_calendar(access_token, time_min, time_max)
            if resp.status_code == 401:
                refreshed = refresh_google_tokens(session['user_id'])
                if refreshed and refreshed.get('access_token'):
                    access_token = refreshed['access_token']
                    resp = get_events_from_calendar(access_token, time_min, time_max)

            resp.raise_for_status()
            items = resp.json().get('items', [])
            for ev in items:
                start_raw = ev.get('start', {}).get('dateTime') or ev.get('start', {}).get('date') or None
                end_raw = ev.get('end', {}).get('dateTime') or ev.get('end', {}).get('date') or None
                s_ts = psic_mod.iso_to_utc_ts(start_raw) if start_raw else None
                e_ts = psic_mod.iso_to_utc_ts(end_raw) if end_raw else None
                if s_ts and e_ts:
                    busy_events_ts.append({'start_ts': s_ts, 'end_ts': e_ts})
        except Exception as e:
            print("Erro ao consultar Google Calendar (perfil_preview):", e)
            busy_events_ts = []

    cursor.close()
    conn.close()

    # ---------- gerar dias/slots exatamente como em psicologos.perfil_publico ----------
    from datetime import date, timedelta, time as dt_time, timezone
    window_days = 21
    page_size = 7
    start_date = date.today()

    all_days = []

    # se o psicólogo optou por NÃO DEFINIR HORÁRIOS, não gera slots
    if scheduling_mode != 'none':
        for offset in range(window_days):
            d = start_date + timedelta(days=offset)
            py_weekday = d.weekday()
            weekday_key = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'][py_weekday]
            ranges = availability_obj.get(weekday_key, []) if isinstance(availability_obj, dict) else []
            slots = []
            for r in ranges:
                try:
                    s_raw = r.get('start') or '00:00'
                    e_raw = r.get('end') or '00:00'
                    s_h, s_m = map(int, s_raw.split(':'))
                    e_h, e_m = map(int, e_raw.split(':'))
                    first_hour = s_h + (1 if s_m > 0 else 0)
                    last_start = e_h - 1 if e_m == 0 else e_h
                    for hour in range(first_hour, last_start + 1):
                        tz_offset = timedelta(hours=-3)
                        slot_start_local = datetime.datetime.combine(
                            d, dt_time(hour=hour, minute=0, tzinfo=timezone(tz_offset))
                        )
                        slot_end_local = slot_start_local + timedelta(hours=1)
                        slot_start_ts = int(slot_start_local.astimezone(timezone.utc).timestamp())
                        slot_end_ts = int(slot_end_local.astimezone(timezone.utc).timestamp())

                        if psic_mod.slot_conflicts_with_events_ts(slot_start_ts, slot_end_ts, busy_events_ts):
                            continue

                        slots.append({
                            'time': f"{hour:02d}:00",
                            'start_iso': slot_start_local.isoformat(),
                            'start_ts': slot_start_ts
                        })
                except Exception as e:
                    print("Erro gerando slots (preview):", e, r)
                    continue

            all_days.append({
                'date': d.isoformat(),
                'weekday': weekday_key,
                'label': d.strftime('%a %d/%m'),
                'slots': slots
            })

    pages = [all_days[i:i+page_size] for i in range(0, len(all_days), page_size)]
    total_pages = len(pages)
    page = int(request.args.get('page', 1)) if request.args.get('page') else 1
    page = max(1, min(page, total_pages)) if pages else 1
    current_page_days = pages[page - 1] if pages else []

    if request.args.get('ajax'):
        return render_template(
            'partials/_calendar_fragment.html',
            current_page_days=current_page_days,
            profile=profile_temp,
            current_page=page,
            total_pages=total_pages
        )

    return render_template(
        "perfil_publico.html",
        profile=profile_temp,
        abordagens=abordagens,
        experiencias=experiencias,
        publicos=publicos,
        pages=pages,
        current_page=page,
        total_pages=total_pages,
        current_page_days=current_page_days
    )



