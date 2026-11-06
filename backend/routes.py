import re
from flask import Blueprint, request, session, jsonify
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash, check_password_hash
from db import engine
from models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def user_json(u):
    return {"id": u.id, "username": u.username, "email": u.email}

@auth_bp.post("/register")
def register():
    d = request.get_json(silent=True) or {}
    username = (d.get("username") or "").strip()
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""

    errors = {}
    if len(username) < 3: errors["username"] = "Use at least 3 characters"
    if not EMAIL_RE.match(email): errors["email"] = "Enter a valid email"
    if len(password) < 8: errors["password"] = "Use at least 8 characters"
    if errors: return jsonify(errors=errors), 400

    with Session(engine) as db:
        taken = db.scalar(select(User).where(or_(User.email == email, User.username == username)))
        if taken:
            return jsonify(errors={"email": "Those details are already in use"}), 409
        user = User(username=username, email=email,
                    password_hash=generate_password_hash(password))
        db.add(user); db.commit()
        session.clear(); session["user_id"] = user.id
        return jsonify(user=user_json(user)), 201

@auth_bp.post("/login")
def login():
    d = request.get_json(silent=True) or {}
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        if not user or not user.is_active or not check_password_hash(user.password_hash, password):
            return jsonify(errors={"form": "Incorrect email or password"}), 401
        session.clear(); session["user_id"] = user.id
        return jsonify(user=user_json(user))

@auth_bp.post("/logout")
def logout():
    session.clear()
    return jsonify(ok=True)

@auth_bp.get("/me")
def me():
    uid = session.get("user_id")
    if not uid: return jsonify(user=None), 401
    with Session(engine) as db:
        user = db.get(User, uid)
        return (jsonify(user=user_json(user)), 200) if user else (jsonify(user=None), 401)