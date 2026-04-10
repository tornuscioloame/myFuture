from flask_sqlalchemy import SQLAlchemy

# Istanza unica di db condivisa tra app.py e models
db = SQLAlchemy()