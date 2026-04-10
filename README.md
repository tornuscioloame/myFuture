# MyFuture — Prototipo App

## Struttura del progetto

```
myfuture/
├── app.py                          ← Entry point Flask
├── config.py                       ← Configurazione (secret key, ecc.)
├── requirements.txt
├── routes/
│   ├── __init__.py
│   ├── auth.py                     ← Login, Register, Logout
│   └── student.py                  ← Dashboard, Intervista, API
├── models/
│   ├── __init__.py
│   └── user.py                     ← Gestione utenti (in-memory per il prototipo)
├── static/
│   ├── css/style.css               ← Design system completo
│   └── js/main.js
├── templates/
│   ├── base.html
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   └── student/
│       ├── interview.html          ← Intervista gamificata
│       └── dashboard.html          ← Profilo + Match
└── data/
    └── interview_questions.json    ← Le 7 domande dell'intervista
```

## Setup in PyCharm

### 1. Installa le dipendenze

Apri il terminale integrato di PyCharm:
```bash
pip install -r requirements.txt
```

### 2. Avvia l'app

```bash
python app.py
```

Oppure in PyCharm: click destro su `app.py` → **Run 'app'**

Apri il browser su: **http://127.0.0.1:5000**

## Accesso da altri dispositivi

L'app ascolta anche sulla rete locale, quindi puo essere aperta da telefono, tablet o un altro computer collegato alla stessa Wi-Fi.

1. Avvia il server:
```bash
python app.py
```

2. Nel terminale vedrai un URL locale e un URL LAN:
```text
App disponibile in locale: http://127.0.0.1:5000
App disponibile in LAN:    http://192.168.x.x:5000
```

3. Apri dal secondo dispositivo l'URL LAN mostrato nel terminale.

Se non funziona:
- controlla che i dispositivi siano sulla stessa rete
- consenti Python nel firewall di Windows
- disattiva eventuali VPN durante il test

## Configurazione host e porta

Puoi personalizzare host, porta e debug con variabili ambiente.

```powershell
$env:FLASK_HOST="0.0.0.0"
$env:FLASK_PORT="5000"
$env:FLASK_DEBUG="true"
python app.py
```

Per renderla accessibile anche fuori dalla tua rete locale serve invece un deploy pubblico o un tunnel sicuro, ad esempio Render, Railway o ngrok.

## Deploy su Azure App Service

Questa app ora e pronta per essere pubblicata su Azure App Service senza avvio manuale da PyCharm.

Configurazione consigliata su Azure:

- Sistema operativo: Linux
- Runtime: Python 3.11 o compatibile
- Startup command: `gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app`

Application Settings da creare su Azure:

- `SECRET_KEY` = una chiave lunga casuale
- `FLASK_DEBUG` = `false`
- `SESSION_COOKIE_SECURE` = `true`
- `GROQ_API_KEY` = la tua chiave API
- `DATABASE_URL` = stringa di connessione del database

Note pratiche:

- Se non imposti `DATABASE_URL`, l'app usa SQLite locale. Va bene in sviluppo, ma per Azure e meglio PostgreSQL.
- L'entrypoint per Azure e `wsgi.py`.
- Le dipendenze di deploy includono `gunicorn`, `groq` e `psycopg2-binary`.

Flusso tipico:

1. Pubblica il progetto su GitHub.
2. Crea una Web App su Azure App Service.
3. Collega il repository GitHub alla Web App.
4. Imposta le Application Settings sopra.
5. Inserisci la startup command `gunicorn --bind=0.0.0.0 --timeout 600 wsgi:app`.
6. Fai deploy e apri l'URL pubblico Azure.

## Flusso dell'app

1. **/** → redirect automatico a `/auth/login`
2. **Login** → se nuovo utente, vai a Registrazione
3. **Registrazione** → login automatico → redirect a Intervista
4. **Intervista** → 7 domande gamificate con IA (Mya)
5. **Dashboard** → profilo soft skills + match percentuali

## Prossimi passi (TODO)

- [ ] Sostituire il "database" in memoria con SQLite/PostgreSQL (SQLAlchemy)
- [ ] Integrare vera IA (OpenAI / Claude API) per analisi risposte
- [ ] Aggiungere lato Aziende (B2B)
- [ ] Autenticazione sicura (Flask-Login + bcrypt)
- [ ] Deploy su Heroku / Railway / Render
