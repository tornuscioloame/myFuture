from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash
from models import UserModel
from extensions import db
from functools import wraps
import random
import re
import json
import os

# ── Groq AI (principale) ──────────────────────────────────────────────────────
# 14.400 req/giorno gratis — https://console.groq.com
try:
    from groq import Groq as GroqClient
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False

GROQ_MODEL = 'llama-3.3-70b-versatile'   # eccellente in italiano, molto veloce
_groq_client = None  # inizializzato lazy al primo uso


def _get_ai_client():
    """Restituisce il client Groq, inizializzandolo al primo uso dalla config Flask."""
    global _groq_client
    if _groq_client is not None:
        return _groq_client
    if not _GROQ_AVAILABLE:
        return None
    from flask import current_app
    api_key = current_app.config.get('GROQ_API_KEY', '') or os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        return None
    _groq_client = GroqClient(api_key=api_key)
    print(f'[AI] Groq client inizializzato con modello {GROQ_MODEL}')
    return _groq_client

student_bp = Blueprint('student', __name__)

GOAL_LABELS = {
    'universita': 'Università (triennale)',
    'magistrale': 'Laurea magistrale',
    'lavoro':     'Lavoro',
}

# ── System prompt per Mya ─────────────────────────────────────────────────────
MYA_SYSTEM_PROMPT = """Sei Mya, l'assistente IA di orientamento della piattaforma myFuture.
Il tuo scopo è aiutare gli studenti italiani a capire il loro percorso futuro (università, lavoro, magistrale).

PERSONALITÀ:
- Sei empatica, diretta e stimolante — non usi frasi fatte o motivazionali vuote
- Parli in italiano colloquiale ma professionale (non usare gergo giovanile eccessivo)
- Fai UNA domanda alla volta, non liste di domande
- Sei curiosa: vai in profondità sulle risposte dell'utente prima di cambiare argomento
- Non sei mai giudicante, anche di fronte a idee vaghe o apparentemente "impossibili"

OBIETTIVO DELLA CONVERSAZIONE:
Attraverso una conversazione fluida, devi capire:
1. Le passioni e gli interessi dell'utente
2. Il modo in cui lavora (autonomo vs team, creativo vs sistematico, ecc.)
3. Le soft skills emergenti (problem solving, comunicazione, leadership, creatività, teamwork, adattabilità)
4. I vincoli pratici (zona geografica, preferenze economiche, situazione familiare se la condivide)

REGOLE:
- Rispondi sempre in italiano
- Mantieni il filo della conversazione: fai riferimento a cose dette in precedenza
- Tieni le risposte brevi: 2-4 frasi massimo
- Non citare mai che "stai analizzando le sue skill" o che "stai aggiornando il profilo" — fallo in modo invisibile
- Se l'utente è in dubbio, aiutalo a escludere invece di scegliere
- Se l'utente parla di qualcosa di specifico (un corso, un'azienda, ecc.), mostra di conoscerlo
- Non usare asterischi, grassetti o formattazione markdown nelle risposte
"""


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_email' not in session:
            flash('Devi effettuare il login.', 'error')
            return redirect(url_for('auth.login'))
        if session.get('user_role') != 'student':
            flash('Accesso riservato agli studenti.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def _user():
    return UserModel.find_by_email(session['user_email'])


def _append_message(user, role, text):
    messages = user.chat_history
    messages.append({'role': role, 'text': text})
    user.chat_history = messages


def _mya_welcome_first_name():
    name = session.get('user_name') or 'lì'
    parts = name.split()
    return parts[0] if parts else 'lì'


# ── Groq AI call ────────────────────────────────────────────────────────────
def _call_ai(user, user_text: str) -> str:
    """Chiama l'AI con la cronologia della chat come contesto."""
    client = _get_ai_client()
    if client is None:
        print('[AI] client non disponibile — uso fallback')
        return _fallback_reply(user, user_text)

    print(f'[AI] chiamata con testo: {user_text[:60]!r}')

    messages = [{"role": "system", "content": MYA_SYSTEM_PROMPT}]

    # Costruisce la history nel formato Groq
    for msg in user.chat_history:
        if isinstance(msg, dict):
            role = 'user' if msg.get('role') == 'user' else 'assistant'
            messages.append({"role": role, "content": msg.get('text', '')})
        else:
            # Fallback in caso di corruzione datamodel nel db
            messages.append({"role": "assistant", "content": str(msg)})

    # Aggiunge il messaggio corrente
    messages.append({"role": "user", "content": user_text})

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.85,
            max_tokens=300,
        )
        reply = response.choices[0].message.content.strip()
        print(f'[AI] risposta ok: {reply[:80]!r}')
        return reply
    except Exception as e:
        print(f'[AI ERROR] {type(e).__name__}: {e}')
        return _fallback_reply(user, user_text)


def _fallback_reply(user, text='') -> str:
    """Usato solo se AI non è disponibile o va in errore."""
    fallbacks = [
        "Capito! Raccontami: cosa ti entusiasma di più quando pensi al tuo futuro?",
        "Interessante. E come ti piace lavorare: più in autonomia o in gruppo?",
        "Grazie per averlo condiviso. C'è un ambito — studio o lavoro — che ti attira di più ultimamente?",
        "Ti ascolto. Se dovessi immaginarti tra un anno, cosa ti piacerebbe aver imparato o provato?",
        "Ha senso. Quando affronti qualcosa di nuovo, preferisci pianificare molto o provare e correggere strada facendo?",
    ]
    random.seed(len(user.chat_history) + (user.id or 0))
    return random.choice(fallbacks)


# ── Aggiornamento skills tramite AI ──────────────────────────────────────────
def _analyze_skills_with_ai(user) -> dict | None:
    """Usa l'AI per estrarre le skill dall'intera conversazione."""
    client = _get_ai_client()
    if client is None:
        return None

    # Costruisci testo della conversazione
    convo = '\n'.join(
        f"{'Utente' if m['role'] == 'user' else 'Mya'}: {m['text']}"
        for m in user.chat_history if m.get('role') in ('user', 'mya')
    )

    prompt = f"""Analizza questa conversazione di orientamento e valuta le seguenti soft skill dell'utente su una scala 0-99.
Considera SOLO ciò che emerge dalla conversazione. Se non hai informazioni sufficienti per una skill, mantieni un valore neutro (55-65).

Soft skills da valutare:
- Problem Solving
- Teamwork
- Comunicazione
- Creatività
- Leadership
- Adattabilità

Conversazione:
{convo}

Rispondi ESCLUSIVAMENTE con un JSON valido in questo formato (senza markdown, senza testo aggiuntivo):
{{"Problem Solving": 72, "Teamwork": 65, "Comunicazione": 80, "Creatività": 70, "Leadership": 58, "Adattabilità": 75}}
"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=100,
        )
        text = response.choices[0].message.content.strip()
        # Rimuovi eventuale markdown
        text = re.sub(r'^```[a-z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        parsed = json.loads(text)
        # Valida e clamp
        skills = {}
        for k in ['Problem Solving', 'Teamwork', 'Comunicazione', 'Creatività', 'Leadership', 'Adattabilità']:
            v = parsed.get(k, 60)
            skills[k] = max(30, min(99, int(v)))
        return skills
    except Exception as e:
        print(f'[AI skill analysis error] {e}')
        return None


def _ensure_chat_initialized(user):
    """Primo accesso alla chat: messaggio di benvenuto e onboarding."""
    if user.profile_done and (user.onboarding_step or 0) < 4:
        user.onboarding_step = 4
    if user.chat_history:
        return
    first = _mya_welcome_first_name()
    if user.profile_done:
        _append_message(
            user, 'mya',
            f"Ciao di nuovo {first}! Sono Mya. Puoi scrivermi quando vuoi: "
            "parliamo del tuo percorso, dei dubbi o dei prossimi passi.",
        )
        db.session.commit()
        return
    welcome = (
        f"Ciao {first}, sono Mya, la tua guida in myFuture. "
        "Qui non c'è un'intervista con domande a elenco: parliamo come in chat, "
        "e io ti aiuto a chiarire il tuo percorso.\n\n"
        "Per personalizzare i tuoi suggerimenti ho bisogno di tre informazioni veloci. "
        "Per iniziare: quanti anni hai? (scrivi un numero.)"
    )
    _append_message(user, 'mya', welcome)
    user.onboarding_step = 1
    db.session.commit()


def _finalize_profile(user):
    goal = user.goal or 'magistrale'
    # Prova a usare Gemini per l'analisi skills, altrimenti random
    ai_skills = _analyze_skills_with_ai(user)
    if ai_skills:
        skills = ai_skills
    else:
        random.seed(len(user.chat_history) * 42 + 7)
        skills = {
            'Problem Solving': random.randint(60, 98),
            'Teamwork':        random.randint(55, 97),
            'Comunicazione':   random.randint(50, 95),
            'Creatività':      random.randint(45, 96),
            'Leadership':      random.randint(40, 90),
            'Adattabilità':    random.randint(55, 95),
        }
    matches = _get_matches_for_goal(goal, skills)
    user.skills_profile = {'skills': skills, 'matches': matches}
    user.profile_done = True
    user.onboarding_step = 4
    session['profile_done'] = True


def _get_matches_for_goal(goal, skills):
    # Score leggermente influenzato dalle skill reali
    avg_skill = sum(skills.values()) / len(skills) if skills else 70
    base = int(avg_skill * 0.3)

    random.seed(int(avg_skill * 100))
    all_matches = {
        'universita': [
            {'type': 'universita', 'name': 'Laurea Triennale in Informatica',        'university': 'Politecnico di Milano',  'score': min(99, base + random.randint(52, 69))},
            {'type': 'universita', 'name': 'Laurea Triennale in Economia Aziendale', 'university': 'Università Bocconi',     'score': min(99, base + random.randint(48, 65))},
            {'type': 'universita', 'name': 'Laurea Triennale in Design',             'university': 'Politecnico di Torino',  'score': min(99, base + random.randint(44, 62))},
            {'type': 'universita', 'name': 'Laurea Triennale in Psicologia',         'university': 'Università La Sapienza', 'score': min(99, base + random.randint(40, 60))},
        ],
        'magistrale': [
            {'type': 'magistrale', 'name': 'Laurea Magistrale in Data Science',             'university': 'Politecnico di Milano',  'score': min(99, base + random.randint(52, 69))},
            {'type': 'magistrale', 'name': 'Laurea Magistrale in Innovation Management',    'university': 'Università Bocconi',     'score': min(99, base + random.randint(45, 64))},
            {'type': 'magistrale', 'name': 'Laurea Magistrale in Digital Marketing',        'university': 'LUISS Roma',             'score': min(99, base + random.randint(40, 61))},
            {'type': 'magistrale', 'name': 'Laurea Magistrale in Intelligenza Artificiale', 'university': 'Università di Bologna',  'score': min(99, base + random.randint(38, 60))},
        ],
        'lavoro': [
            {'type': 'lavoro', 'name': 'Junior Product Manager',   'company': 'TechCorp Italia', 'score': min(99, base + random.randint(52, 69))},
            {'type': 'lavoro', 'name': 'Business Analyst Trainee', 'company': 'Accenture',       'score': min(99, base + random.randint(45, 64))},
            {'type': 'lavoro', 'name': 'Junior UX Designer',       'company': 'Jakala',          'score': min(99, base + random.randint(40, 61))},
            {'type': 'lavoro', 'name': 'Marketing Specialist Jr.', 'company': 'Publicis Group',  'score': min(99, base + random.randint(38, 59))},
        ],
    }
    matches = all_matches.get(goal, all_matches['magistrale'])
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches


def _update_skills_after_chat(user):
    """Aggiorna le skills via Gemini ogni 3 messaggi utente nella fase libera."""
    user_messages = [m for m in user.chat_history if m.get('role') == 'user']
    # Aggiorna ogni 3 messaggi utente
    if len(user_messages) % 3 != 0:
        return False
    ai_skills = _analyze_skills_with_ai(user)
    if not ai_skills:
        return False
    profile = user.skills_profile
    if not profile:
        return False
    profile['skills'] = ai_skills
    user.skills_profile = profile
    return True


# ── APP SHELL (Nuovo Layout 3 Colonne) ──────────────────────────────────────
@student_bp.route('/app')
@student_required
def app_shell():
    user = _user()
    if user is None:
        session.clear()
        return redirect(url_for('auth.login'))
        
    if user.profile_done and (user.onboarding_step or 0) < 4:
        user.onboarding_step = 4
        db.session.commit()
        
    _ensure_chat_initialized(user)
    db.session.commit()
    
    return render_template(
        'student/app.html', 
        user=user,
        messages=user.chat_history,
        onboarding_step=user.onboarding_step or 0
    )


# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@student_bp.route('/dashboard')
@student_required
def dashboard():
    # La vecchia dashboard non esiste più, Mya e il Motore vivono nell'App Shell unificata
    return redirect(url_for('student.app_shell'))


@student_bp.route('/api/dashboard')
@student_required
def api_dashboard():
    """Restituisce skills e matches aggiornati per polling live dalla dashboard."""
    user = _user()
    if user is None:
        return jsonify({'error': 'session'}), 401
    profile = user.skills_profile
    return jsonify({
        'skills': profile.get('skills', {}),
        'matches': profile.get('matches', []),
        'goal': user.goal,
        'name': user.name,
    })


# ── CHAT MYA ──────────────────────────────────────────────────────────────────
@student_bp.route('/interview')
@student_required
def interview():
    return redirect(url_for('student.chat'))


@student_bp.route('/chat')
@student_required
def chat():
    user = _user()
    if user is None:
        session.clear()
        flash('Sessione scaduta. Effettua di nuovo il login.', 'error')
        return redirect(url_for('auth.login'))
    if user.profile_done and (user.onboarding_step or 0) < 4:
        user.onboarding_step = 4
        db.session.commit()
    _ensure_chat_initialized(user)
    db.session.commit()
    return render_template(
        'student/chat.html',
        user=user,
        messages=user.chat_history,
        onboarding_step=user.onboarding_step or 0,
        goal_labels=GOAL_LABELS,
        gemini_active=_get_ai_client() is not None,
    )


@student_bp.route('/api/chat', methods=['POST'])
@student_required
def api_chat():
    user = _user()
    if user is None:
        return jsonify({'error': 'session'}), 401

    data = request.get_json() or {}
    goal_key = data.get('goal_key')
    text = (data.get('text') or '').strip()

    # ── Scelta obiettivo (pulsanti rapidi) ────────────────────────────────────
    if goal_key in GOAL_LABELS and (user.onboarding_step or 0) == 3:
        user.goal = goal_key
        _append_message(user, 'user', f"Il mio obiettivo: {GOAL_LABELS[goal_key]}")
        _append_message(
            user, 'mya',
            "Perfetto, ho salvato il tuo obiettivo. "
            "Ho abbastanza elementi per proporti un profilo iniziale: trovi soft skills e match nella dashboard. "
            "Da qui in poi resto disponibile: puoi scrivermi quando vuoi, anche solo per riflettere sul tuo percorso.",
        )
        _finalize_profile(user)
        db.session.commit()
        return jsonify({
            'messages': user.chat_history,
            'profile_done': True,
            'onboarding_step': user.onboarding_step,
        })

    if not text:
        return jsonify({'error': 'empty'}), 400

    step = user.onboarding_step or 0

    # ── Fase libera con Gemini ────────────────────────────────────────────────
    if user.profile_done and step >= 4:
        _append_message(user, 'user', text)
        mya_reply = _call_ai(user, text)
        _append_message(user, 'mya', mya_reply)
        profile_updated = _update_skills_after_chat(user)
        db.session.commit()
        return jsonify({
            'messages': user.chat_history,
            'profile_done': True,
            'onboarding_step': 4,
            'profile_updated': profile_updated,
            'skills': user.skills_profile.get('skills', {}),
            'matches': user.skills_profile.get('matches', []),
        })

    _append_message(user, 'user', text)

    # ── Onboarding guidato ────────────────────────────────────────────────────
    if step == 1:
        age = re.sub(r'\D', '', text)[:3]
        if not age:
            _append_message(
                user, 'mya',
                "Scrivi solo la tua età in numeri (es. 19), così registro bene il dato.",
            )
        else:
            user.age = age
            _append_message(
                user, 'mya',
                "Grazie! Qual è il tuo titolo di studio attuale? "
                "(Es. diploma, triennale in corso, ecc.)",
            )
            user.onboarding_step = 2

    elif step == 2:
        user.education = text[:200]
        _append_message(
            user, 'mya',
            "Ottimo. Ultima cosa per i match: cosa stai cercando adesso? "
            "Scegli uno dei pulsanti sotto la chat (Università, Magistrale o Lavoro).",
        )
        user.onboarding_step = 3

    elif step == 3:
        _append_message(
            user, 'mya',
            "Per questa scelta usa i tre pulsanti colorati sotto: così aggiorno correttamente i tuoi suggerimenti.",
        )

    db.session.commit()
    return jsonify({
        'messages': user.chat_history,
        'profile_done': user.profile_done,
        'onboarding_step': user.onboarding_step,
    })
