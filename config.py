import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _database_uri():
    database_url = os.environ.get('DATABASE_URL', '').strip()
    if database_url:
        if database_url.startswith('postgres://'):
            return 'postgresql://' + database_url[len('postgres://'):]
        return database_url
    return 'sqlite:///' + os.path.join(BASE_DIR, 'myfuture.db')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'myfuture-dev-secret-2025'
    DEBUG = _env_flag('FLASK_DEBUG', True)
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', '5000'))

    # In cloud usa DATABASE_URL, in locale ricade su SQLite.
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }

    # Sessione permanente: 30 giorni
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_SECURE = _env_flag('SESSION_COOKIE_SECURE', not DEBUG)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Chiave AI da impostare come variabile ambiente in locale o su Azure.
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
