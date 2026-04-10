from extensions import db
import hashlib
import json


class User(db.Model):
    __tablename__ = 'users'

    id               = db.Column(db.Integer, primary_key=True)
    email            = db.Column(db.String(150), unique=True, nullable=False)
    password_hash    = db.Column(db.String(64), nullable=False)
    name             = db.Column(db.String(100), nullable=False)
    role             = db.Column(db.String(20), default='student')   # student | company
    profile_done     = db.Column(db.Boolean, default=False)

    # Campi onboarding
    age              = db.Column(db.String(10))
    education        = db.Column(db.String(200))
    goal             = db.Column(db.String(20))   # universita | magistrale | lavoro

    # JSON serializzati
    interview_answers_json = db.Column(db.Text, default='[]')  # legacy intervista
    chat_history_json      = db.Column(db.Text, default='[]')   # messaggi con Mya
    skills_profile_json    = db.Column(db.Text, default='{}')

    # 1=età, 2=studio, 3=obiettivo, 4=chat libera / profilo pronto
    onboarding_step = db.Column(db.Integer, default=0)

    # ── Helpers password ───────────────────────────────────────
    @staticmethod
    def _hash(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def set_password(self, password: str):
        self.password_hash = self._hash(password)

    def check_password(self, password: str) -> bool:
        return self.password_hash == self._hash(password)

    # ── Helpers JSON ───────────────────────────────────────────
    @property
    def interview_answers(self):
        return json.loads(self.interview_answers_json or '[]')

    @interview_answers.setter
    def interview_answers(self, value):
        self.interview_answers_json = json.dumps(value, ensure_ascii=False)

    @property
    def skills_profile(self):
        return json.loads(self.skills_profile_json or '{}')

    @skills_profile.setter
    def skills_profile(self, value):
        self.skills_profile_json = json.dumps(value, ensure_ascii=False)

    @property
    def chat_history(self):
        return json.loads(self.chat_history_json or '[]')

    @chat_history.setter
    def chat_history(self, value):
        self.chat_history_json = json.dumps(value, ensure_ascii=False)

    # ── API compatibile con il vecchio UserModel ───────────────
    @staticmethod
    def create(email, password, name, role):
        if User.query.filter_by(email=email).first():
            return None
        u = User(email=email, name=name, role=role)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        return u

    @staticmethod
    def find_by_email(email):
        return User.query.filter_by(email=email).first()

    @staticmethod
    def verify_password(email, password):
        u = User.find_by_email(email)
        return u is not None and u.check_password(password)

    def update_fields(self, data: dict):
        """Aggiorna i campi passati come dizionario e salva."""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()

    def to_dict(self):
        """Compatibilità con il vecchio codice che usava dizionari."""
        return {
            'email':            self.email,
            'name':             self.name,
            'role':             self.role,
            'profile_done':     self.profile_done,
            'age':              self.age,
            'education':        self.education,
            'goal':             self.goal,
            'interview_answers': self.interview_answers,
            'chat_history':      self.chat_history,
            'skills_profile':   self.skills_profile,
        }