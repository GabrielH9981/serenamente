# routes/main.py
from flask import Blueprint, render_template, session, redirect, url_for

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('index.html')


@main_bp.route('/parceiro')
def parceiro():
    return render_template('psicologo_apresentacao.html')
