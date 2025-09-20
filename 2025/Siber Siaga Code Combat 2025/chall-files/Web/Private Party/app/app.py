from flask import Flask, request, session, redirect, url_for, render_template, flash
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
import os

app = Flask(__name__)
app.secret_key = os.urandom(32)

engine = create_engine('sqlite:///ctf.db', connect_args={"check_same_thread": False})
Base = declarative_base()
DBSession = sessionmaker(bind=engine)
dbs = DBSession()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    pw_hash = Column(String)
    registered_via_admin = Column(Boolean, default=False)

Base.metadata.create_all(engine, checkfirst=True)

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    data = request.form
    u = dbs.query(User).filter_by(username=data.get("username")).first()
    if not u or not check_password_hash(u.pw_hash, data.get("password","")):
        flash("Invalid username or password.", "error")
        return render_template("login.html"), 401
    if not u.registered_via_admin:
        flash("Access denied: account not registered via admin.", "error")
        return render_template("login.html"), 403
    session['user'] = u.username
    flash("Login successful.", "success")
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    if 'user' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))
    u = dbs.query(User).filter_by(username=session['user']).first()
    if not u or not u.registered_via_admin:
        flash("Access denied.", "error")
        return redirect(url_for("login"))
    return render_template("dashboard.html", username=u.username)

@app.route("/admin" , methods=["GET","POST"])
def admin():
    if request.method== "POST":
        data = request.get_json() or {}
        username = data.get("username")
        password = data.get("password")
        if not username or not password:
            return "missing fields", 400
        if dbs.query(User).filter_by(username=username).first():
            return "exists", 409
        u = User(username=username, pw_hash=generate_password_hash(password), registered_via_admin=True)
        dbs.add(u)
        dbs.commit()
        return "created", 201
    else:
        return render_template("admin.html")