import os
import socket
from flask import Flask, redirect, url_for
from sqlalchemy import text
from config import Config
from extensions import db


def _migrate_sqlite_columns():
    """Aggiunge colonne nuove su DB esistenti (SQLite) senza framework di migrazione."""
    stmts = [
        "ALTER TABLE users ADD COLUMN chat_history_json TEXT DEFAULT '[]'",
        "ALTER TABLE users ADD COLUMN onboarding_step INTEGER DEFAULT 0",
    ]
    for sql in stmts:
        try:
            db.session.execute(text(sql))
            db.session.commit()
        except Exception:
            db.session.rollback()


def _is_sqlite_database(uri: str) -> bool:
    return (uri or '').startswith('sqlite:')


def create_app():
    app = Flask(__name__)

    # Config DEVE essere caricata prima di db.init_app
    app.config.from_object(Config)

    # Verifica esplicita (debug)
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        raise RuntimeError("SQLALCHEMY_DATABASE_URI non trovato nel config!")

    db.init_app(app)

    from models.user import User
    with app.app_context():
        database_uri = app.config['SQLALCHEMY_DATABASE_URI']
        print(f'[BOOT] Database in uso: {database_uri.split("?")[0]}')
        db.create_all()
        if _is_sqlite_database(database_uri):
            _migrate_sqlite_columns()

    from routes.auth import auth_bp
    from routes.student import student_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(student_bp, url_prefix='/student')

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app


def _get_local_ip():
    """Prova a ricavare l'IP locale per facilitare l'accesso da altri dispositivi."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('8.8.8.8', 80))
        return sock.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        sock.close()


if __name__ == '__main__':
    app = create_app()
    host = app.config.get('HOST', '0.0.0.0')
    port = app.config.get('PORT', 5000)
    debug = app.config.get('DEBUG', True)

    local_ip = _get_local_ip()
    print(f'App disponibile in locale: http://127.0.0.1:{port}')
    if host == '0.0.0.0':
        print(f'App disponibile in LAN:    http://{local_ip}:{port}')

    app.run(debug=debug, host=host, port=port)
