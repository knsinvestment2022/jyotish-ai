"""
Database models using Flask-SQLAlchemy (SQLite by default).
"""

from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    plan = db.Column(db.String(20), default="free")  # free | pro
    message_count = db.Column(db.Integer, default=0)
    is_beta = db.Column(db.Boolean, default=True)   # first 100 users = 90 days free
    beta_expires_at = db.Column(db.DateTime, nullable=True)  # 90 days from signup
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sessions = db.relationship("ChatSession", back_populates="user", lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def beta_active(self) -> bool:
        """True if user is beta AND their 90-day window hasn't expired."""
        if not self.is_beta:
            return False
        if self.beta_expires_at and datetime.utcnow() > self.beta_expires_at:
            return False
        return True

    @property
    def can_chat(self) -> bool:
        """Returns True if user is allowed to send another message."""
        if self.beta_active or self.plan == "pro":
            return True
        free_limit = int(__import__("os").environ.get("FREE_MESSAGE_LIMIT", "20"))
        return self.message_count < free_limit

    @property
    def messages_remaining(self) -> int:
        if self.beta_active or self.plan == "pro":
            return 9999
        free_limit = int(__import__("os").environ.get("FREE_MESSAGE_LIMIT", "20"))
        return max(0, free_limit - self.message_count)

    @property
    def beta_days_left(self) -> int:
        if not self.beta_active or not self.beta_expires_at:
            return 0
        delta = self.beta_expires_at - datetime.utcnow()
        return max(0, delta.days)


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(120), default="New Reading")
    birth_name = db.Column(db.String(100))
    birth_date = db.Column(db.String(20))   # "YYYY-MM-DD"
    birth_time = db.Column(db.String(10))   # "HH:MM"
    birth_place = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="sessions")
    messages = db.relationship("Message", back_populates="session",
                               cascade="all, delete-orphan", lazy=True)

    @property
    def birth_context(self) -> str:
        if not self.birth_date:
            return ""
        parts = []
        if self.birth_name:
            parts.append(f"Name: {self.birth_name}")
        if self.birth_date:
            parts.append(f"DOB: {self.birth_date}")
        if self.birth_time:
            parts.append(f"Time: {self.birth_time}")
        if self.birth_place:
            parts.append(f"Place: {self.birth_place}")
        return ", ".join(parts)


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)    # "user" | "assistant"
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship("ChatSession", back_populates="messages")
    feedback = db.relationship("Feedback", back_populates="message",
                               uselist=False, cascade="all, delete-orphan")


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("messages.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Integer)             # 1 = thumbs down, 5 = thumbs up
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    message = db.relationship("Message", back_populates="feedback")
