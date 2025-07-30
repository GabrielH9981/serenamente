# routes/perfil.py
from flask import Blueprint, render_template, request, session, redirect, url_for
from db.db import get_db_connection
import os, base64
from PIL import Image
from io import BytesIO
import datetime
from cloudinary.uploader import upload as cloudinary_upload
from utils.cloudinary_config import cloudinary

perfil_bp = Blueprint('perfil', __name__)


@perfil_bp.route('/perfil', methods=['GET', 'POST'])
def perfil():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    #select dos dados cadastrados no perfil
    cursor.execute("SELECT * FROM profiles WHERE user_id = %s", (session['user_id'],))
    profile = cursor.fetchone()

    #select dos dias restantes de plano
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
                result = cloudinary_upload(buffer, folder="serenamente/perfis",
                                           public_id=f"profile_{session['user_id']}", overwrite=True)
                image_filename = result['secure_url']
            except Exception as e:
                print("Erro ao salvar imagem no Cloudinary:", e)

        data = {
            'short_bio': request.form.get('short_bio'),
            'full_bio': request.form.get('full_bio'),
            'profile_picture_url': image_filename or (profile.get('profile_picture_url') if profile else ''),
            'location': request.form.get('location'),
            'price_range': request.form.get('price_range'),
            'atendimento_online': 1 if request.form.get('atendimento_online') else 0,
            'atendimento_presencial': 1 if request.form.get('atendimento_presencial') else 0,
            'whatsapp_number': request.form.get('whatsapp_number'),
            'instagram_url': request.form.get('instagram_url'),
            'website_url': request.form.get('website_url')
        }

        if profile:
            cursor.execute("""
                UPDATE profiles SET short_bio=%s, full_bio=%s, profile_picture_url=%s, location=%s,
                price_range=%s, atendimento_online=%s, atendimento_presencial=%s,
                whatsapp_number=%s, instagram_url=%s, website_url=%s WHERE user_id=%s
            """, (
                data['short_bio'], data['full_bio'], data['profile_picture_url'], data['location'],
                data['price_range'], data['atendimento_online'], data['atendimento_presencial'],
                data['whatsapp_number'], data['instagram_url'], data['website_url'], session['user_id']
            ))
        else:
            cursor.execute("""
                INSERT INTO profiles (
                    user_id, short_bio, full_bio, profile_picture_url, location,
                    price_range, atendimento_online, atendimento_presencial,
                    whatsapp_number, instagram_url, website_url
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session['user_id'], data['short_bio'], data['full_bio'], data['profile_picture_url'], data['location'],
                data['price_range'], data['atendimento_online'], data['atendimento_presencial'],
                data['whatsapp_number'], data['instagram_url'], data['website_url']
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
            cursor.execute("INSERT INTO profile_approaches (profile_id, approach_id) VALUES (%s, %s)", (profile_id, selected_approach_id))

        cursor.execute("DELETE FROM profile_experiencias WHERE profile_id = %s", (profile_id,))
        for eid in request.form.getlist("experiencias"):
            cursor.execute("INSERT INTO profile_experiencias (profile_id, experiencia_id) VALUES (%s, %s)", (profile_id, eid))

        cursor.execute("DELETE FROM profile_publicos_alvo WHERE profile_id = %s", (profile_id,))
        for pid in request.form.getlist("publicos"):
            cursor.execute("INSERT INTO profile_publicos_alvo (profile_id, publico_id) VALUES (%s, %s)", (profile_id, pid))

        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('perfil.perfil'))

    cursor.close()
    conn.close()

    return render_template('perfil.html', profile=profile or {},
                           approaches=approaches,
                           experiencias=experiencias,
                           publicos=publicos,
                           selected_approaches=selected_approaches,
                           selected_experiencias=selected_experiencias,
                           selected_publicos=selected_publicos,
                           plan_days=plan_days)
