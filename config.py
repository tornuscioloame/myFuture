import os
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _running_in_cloud():
    return any(
        os.environ.get(name)
        for name in ('WEBSITE_HOSTNAME', 'WEBSITE_SITE_NAME', 'WEBSITE_INSTANCE_ID')
    )


def _normalize_database_url(value):
    value = (value or '').strip()
    if not value:
        return ''
    if value.startswith('postgres://'):
        return 'postgresql://' + value[len('postgres://'):]
    return value


def _augment_postgres_url(value):
    if not value.startswith('postgresql://'):
        return value

    parts = urlsplit(value)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if _running_in_cloud():
        query.setdefault('sslmode', 'require')
    query.setdefault('connect_timeout', '10')
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _azure_connection_string():
    for prefix in ('POSTGRESQLCONNSTR_', 'CUSTOMCONNSTR_'):
        for key, value in os.environ.items():
            if key.startswith(prefix) and value.strip():
                return _augment_postgres_url(_normalize_database_url(value))
    return ''


def _database_uri():
    database_url = _augment_postgres_url(_normalize_database_url(os.environ.get('DATABASE_URL', '')))
    if not database_url:
        database_url = _augment_postgres_url(_normalize_database_url(os.environ.get('SQLALCHEMY_DATABASE_URI', '')))
    if not database_url:
        database_url = _azure_connection_string()
    if database_url:
        return database_url
    if _running_in_cloud():
        raise RuntimeError(
            'Database non configurato in cloud. Imposta DATABASE_URL oppure una '
            'connection string Azure PostgreSQL.'
        )
    return 'sqlite:///' + os.path.join(BASE_DIR, 'myfuture.db')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'myfuture-dev-secret-2025'
    DEBUG = _env_flag('FLASK_DEBUG', not _running_in_cloud())
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', '5000'))

    # In cloud richiede un database esplicito; in locale ricade su SQLite.
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    if SQLALCHEMY_DATABASE_URI.startswith('sqlite'):
        SQLALCHEMY_ENGINE_OPTIONS['connect_args'] = {'check_same_thread': False}
    elif SQLALCHEMY_DATABASE_URI.startswith('postgresql://'):
        SQLALCHEMY_ENGINE_OPTIONS['connect_args'] = {'connect_timeout': 10}
        if _running_in_cloud():
            SQLALCHEMY_ENGINE_OPTIONS['connect_args']['sslmode'] = 'require'

    # Sessione permanente: 30 giorni
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_SECURE = _env_flag('SESSION_COOKIE_SECURE', not DEBUG)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Chiave AI da impostare come variabile ambiente in locale o su Azure.
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
