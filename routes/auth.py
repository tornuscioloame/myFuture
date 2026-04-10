from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import UserModel

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_email' in session:
        return _redirect_by_role(session.get('user_role'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role     = request.form.get('role', 'student')

        if UserModel.verify_password(email, password):
            user = UserModel.find_by_email(email)
            if user.role != role:
                flash('Ruolo non corrispondente per questo account.', 'error')
                return render_template('auth/login.html')

            if request.form.get('remember'):
                session.permanent = True

            session['user_email']   = email
            session['user_name']    = user.name
            session['user_role']    = user.role
            session['profile_done'] = user.profile_done

            if user.role == 'student':
                return redirect(url_for('student.app_shell'))
            return _redirect_by_role(user.role)
        else:
            flash('Email o password non corretti.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_email' in session:
        return _redirect_by_role(session.get('user_role'))

    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        role     = request.form.get('role', 'student')

        if not name or not email or not password:
            flash('Compila tutti i campi.', 'error')
            return render_template('auth/register.html')
        if password != confirm:
            flash('Le password non coincidono.', 'error')
            return render_template('auth/register.html')
        if len(password) < 6:
            flash('La password deve essere di almeno 6 caratteri.', 'error')
            return render_template('auth/register.html')

        user = UserModel.create(email, password, name, role)
        if user is None:
            flash('Email già registrata. Prova ad accedere.', 'error')
            return render_template('auth/register.html')

        session.permanent = True
        session['user_email']   = email
        session['user_name']    = name
        session['user_role']    = role
        session['profile_done'] = False

        flash(f'Benvenuto/a {name}! Inizia a chattare con Mya.', 'success')
        if role == 'student':
            return redirect(url_for('student.app_shell'))
        return _redirect_by_role(role)

    return render_template('auth/register.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


def _redirect_by_role(role):
    if role == 'student':
        return redirect(url_for('student.dashboard'))
    return redirect(url_for('student.dashboard'))
