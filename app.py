"""
Jyotish AI — Vedic Astrology Chatbot + Pay-per-Reading Web App

Routes:
  /              -> Landing page
  /signup        -> Create account
  /login         -> Login
  /logout        -> Logout
  /chat          -> Main chat interface (login required)
  /api/chat      -> POST: send message, get AI response (streaming SSE)
  /api/session   -> POST: create/update chat session with birth details
  /api/feedback  -> POST: thumbs up/down on a message
  /api/sessions  -> GET: list user's past sessions
  /admin/feedback -> GET: view all feedback (admin only)

  Legacy pay-per-reading routes still work:
  /reading-form  -> Birth detail form for one-time reading
  /preview       -> Teaser reading
  /checkout      -> Stripe payment
  /reading       -> Full reading after payment
"""

import datetime
from datetime import timedelta
import json
import os
import io

# Load .env file automatically
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    pass  # dotenv not installed, use system env vars

from flask import (
    Flask, request, render_template, redirect, url_for,
    send_file, abort, jsonify, Response, session, flash
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
import stripe

from models import db, User, ChatSession, Message, Feedback
from chart_engine import compute_natal_chart, vimshottari_dasha
from location import geocode_place, resolve_utc_offset
from reading_generator import generate_teaser, generate_full_reading
from pdf_export import build_reading_pdf
from chat_engine import chat, chat_stream

# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

# Database
DB_PATH = os.environ.get("DATABASE_URL", f"sqlite:///{os.path.join(os.path.dirname(__file__), 'astro.db')}")
# Render provides postgres:// but SQLAlchemy requires postgresql://
if DB_PATH.startswith("postgres://"):
    DB_PATH = DB_PATH.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_PATH
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# Auth
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to start your reading."

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_PLACEHOLDER")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "pk_test_PLACEHOLDER")
READING_PRICE_CENTS = int(os.environ.get("READING_PRICE_CENTS", "99"))
READING_CURRENCY = os.environ.get("READING_CURRENCY", "usd")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "knsinvestment2022@gmail.com")
FREE_MESSAGE_LIMIT = int(os.environ.get("FREE_MESSAGE_LIMIT", "20"))
BETA_USER_LIMIT = int(os.environ.get("BETA_USER_LIMIT", "100"))


# ---------------------------------------------------------------------------
# Database init
# ---------------------------------------------------------------------------
with app.app_context():
    db.create_all()


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("chat_page"))
    return render_template("landing.html")


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("chat_page"))

    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            error = "All fields are required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif User.query.filter_by(email=email).first():
            error = "An account with this email already exists."
        else:
            # First 100 users are beta (unlimited free)
            total_users = User.query.count()
            is_beta = total_users < BETA_USER_LIMIT

            user = User(name=name, email=email, is_beta=is_beta)
            if is_beta:
                user.beta_expires_at = datetime.datetime.utcnow() + timedelta(days=90)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=True)
            flash(
                "Welcome! You have free beta access for 90 days — ask anything." if is_beta
                else f"Account created! You have {FREE_MESSAGE_LIMIT} free messages.",
                "success"
            )
            return redirect(url_for("chat_page"))

    return render_template("signup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("chat_page"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            error = "Invalid email or password."
        else:
            login_user(user, remember=True)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("chat_page"))

    return render_template("login.html", error=error)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Chat page
# ---------------------------------------------------------------------------
@app.route("/chat")
@login_required
def chat_page():
    sessions = (ChatSession.query
                .filter_by(user_id=current_user.id)
                .order_by(ChatSession.created_at.desc())
                .limit(20).all())
    return render_template("chat.html",
                           user=current_user,
                           sessions=sessions,
                           messages_remaining=current_user.messages_remaining)


# ---------------------------------------------------------------------------
# API: Create / update session
# ---------------------------------------------------------------------------
@app.route("/api/session", methods=["POST"])
@login_required
def api_session():
    data = request.get_json() or {}
    session_id = data.get("session_id")

    if session_id:
        sess = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first()
        if not sess:
            return jsonify({"error": "Session not found"}), 404
    else:
        sess = ChatSession(user_id=current_user.id)
        db.session.add(sess)

    # Update birth details if provided — save to both session AND user profile
    if data.get("birth_name"):
        sess.birth_name = data["birth_name"]
        current_user.birth_name = data["birth_name"]
    if data.get("birth_date"):
        sess.birth_date = data["birth_date"]
        current_user.birth_date = data["birth_date"]
    if data.get("birth_time"):
        sess.birth_time = data["birth_time"]
        current_user.birth_time = data["birth_time"]
    if data.get("birth_place"):
        sess.birth_place = data["birth_place"]
        current_user.birth_place = data["birth_place"]

    # Auto-title from first question or birth name
    if not session_id and sess.birth_name:
        sess.title = f"Reading for {sess.birth_name}"

    # Auto-populate new session from user's saved profile if nothing was provided
    if not session_id:
        if not sess.birth_name and current_user.birth_name:
            sess.birth_name = current_user.birth_name
        if not sess.birth_date and current_user.birth_date:
            sess.birth_date = current_user.birth_date
        if not sess.birth_time and current_user.birth_time:
            sess.birth_time = current_user.birth_time
        if not sess.birth_place and current_user.birth_place:
            sess.birth_place = current_user.birth_place
        if sess.birth_name and not data.get("birth_name"):
            sess.title = f"Reading for {sess.birth_name}"

    db.session.commit()
    return jsonify({"session_id": sess.id, "title": sess.title})


# ---------------------------------------------------------------------------
# API: Chat (streaming SSE)
# ---------------------------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    if not current_user.can_chat:
        return jsonify({
            "error": f"You've used your {FREE_MESSAGE_LIMIT} free messages. "
                     "Upgrade to Pro for unlimited access.",
            "upgrade": True
        }), 402

    data = request.get_json() or {}
    user_message = (data.get("message") or "").strip()
    session_id = data.get("session_id")
    stream_mode = data.get("stream", True)

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    # Get or create session
    if session_id:
        sess = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first()
        if not sess:
            return jsonify({"error": "Session not found"}), 404
    else:
        sess = ChatSession(user_id=current_user.id, title=user_message[:60])
        db.session.add(sess)
        db.session.commit()

    # Load history (last 12 messages to keep context window manageable)
    history_msgs = (Message.query
                    .filter_by(session_id=sess.id)
                    .order_by(Message.created_at.asc())
                    .limit(12).all())
    history = [{"role": m.role, "content": m.content} for m in history_msgs]

    # Save user message
    user_msg = Message(session_id=sess.id, role="user", content=user_message)
    db.session.add(user_msg)
    current_user.message_count += 1
    db.session.commit()

    birth_ctx = sess.birth_context

    if stream_mode:
        # Streaming SSE response
        def generate():
            full_response = ""
            yield "data: {\"type\":\"start\",\"session_id\":" + str(sess.id) + "}\n\n"

            for chunk in chat_stream(history, user_message, birth_ctx):
                full_response += chunk
                payload = json.dumps({"type": "chunk", "text": chunk})
                yield f"data: {payload}\n\n"

            # Save assistant message
            with app.app_context():
                assistant_msg = Message(
                    session_id=sess.id,
                    role="assistant",
                    content=full_response
                )
                db.session.add(assistant_msg)
                db.session.commit()
                msg_id = assistant_msg.id

            yield f"data: {{\"type\":\"done\",\"message_id\":{msg_id}}}\n\n"

        return Response(generate(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    else:
        # Non-streaming for simplicity
        response_text = chat(history, user_message, birth_ctx)
        assistant_msg = Message(session_id=sess.id, role="assistant", content=response_text)
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({
            "response": response_text,
            "message_id": assistant_msg.id,
            "session_id": sess.id,
        })


# ---------------------------------------------------------------------------
# API: Feedback
# ---------------------------------------------------------------------------
@app.route("/api/feedback", methods=["POST"])
@login_required
def api_feedback():
    data = request.get_json() or {}
    message_id = data.get("message_id")
    rating = data.get("rating")  # 1=bad, 5=good
    comment = data.get("comment", "")

    if not message_id or rating is None:
        return jsonify({"error": "message_id and rating required"}), 400

    msg = Message.query.get(message_id)
    if not msg:
        return jsonify({"error": "Message not found"}), 404

    # Upsert feedback
    fb = Feedback.query.filter_by(message_id=message_id, user_id=current_user.id).first()
    if fb:
        fb.rating = rating
        fb.comment = comment
    else:
        fb = Feedback(message_id=message_id, user_id=current_user.id,
                      rating=rating, comment=comment)
        db.session.add(fb)

    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API: Load session messages
# ---------------------------------------------------------------------------
@app.route("/api/sessions/<int:session_id>/messages")
@login_required
def api_session_messages(session_id):
    sess = ChatSession.query.filter_by(id=session_id, user_id=current_user.id).first()
    if not sess:
        return jsonify({"error": "Not found"}), 404

    msgs = [{"id": m.id, "role": m.role, "content": m.content,
             "created_at": m.created_at.isoformat()}
            for m in sess.messages]
    return jsonify({
        "session_id": sess.id,
        "title": sess.title,
        "birth": {
            "name": sess.birth_name,
            "date": sess.birth_date,
            "time": sess.birth_time,
            "place": sess.birth_place,
        },
        "messages": msgs,
    })


# ---------------------------------------------------------------------------
# Admin: View feedback
# ---------------------------------------------------------------------------
@app.route("/admin/feedback")
@login_required
def admin_feedback():
    if current_user.email != ADMIN_EMAIL:
        abort(403)
    rows = (db.session.query(Feedback, Message, User)
            .join(Message, Feedback.message_id == Message.id)
            .join(User, Feedback.user_id == User.id)
            .order_by(Feedback.created_at.desc())
            .limit(200).all())
    return render_template("admin_feedback.html", rows=rows)


# ---------------------------------------------------------------------------
# Admin: View all users
# ---------------------------------------------------------------------------
@app.route("/admin/users")
@login_required
def admin_users():
    if current_user.email != ADMIN_EMAIL:
        abort(403)
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin_users.html", users=users)


# ---------------------------------------------------------------------------
# Legacy pay-per-reading routes (unchanged)
# ---------------------------------------------------------------------------
def _parse_birth_form(form):
    return {
        "name": form.get("name", "").strip() or "there",
        "year": int(form["year"]),
        "month": int(form["month"]),
        "day": int(form["day"]),
        "hour": int(form["hour"]),
        "minute": int(form["minute"]),
        "place": form.get("place", "").strip(),
    }


def _build_chart_and_dasha(birth):
    lat, lon, display_name = geocode_place(birth["place"])
    utc_offset, tz_name = resolve_utc_offset(
        lat, lon, birth["year"], birth["month"], birth["day"], birth["hour"], birth["minute"]
    )
    chart = compute_natal_chart(
        birth["year"], birth["month"], birth["day"], birth["hour"], birth["minute"],
        utc_offset, lat, lon,
    )
    birth_date = datetime.date(birth["year"], birth["month"], birth["day"])
    dasha = vimshottari_dasha(birth_date, chart["moon_lon"], levels=3)
    return chart, dasha, display_name, tz_name


@app.route("/reading-form")
def reading_form():
    return render_template("index.html")


@app.route("/preview", methods=["POST"])
def preview():
    birth = _parse_birth_form(request.form)
    try:
        chart, dasha, display_name, tz_name = _build_chart_and_dasha(birth)
    except ValueError as e:
        return render_template("index.html", error=str(e)), 400
    teaser = generate_teaser(chart)
    return render_template(
        "preview.html", birth=birth, teaser=teaser,
        display_name=display_name,
        price_display=f"{READING_PRICE_CENTS / 100:.2f}",
        currency=READING_CURRENCY.upper(),
    )


@app.route("/checkout", methods=["POST"])
def checkout():
    birth = _parse_birth_form(request.form)
    sess = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": READING_CURRENCY,
                "product_data": {"name": f"Full Vedic Astrology Reading for {birth['name']}"},
                "unit_amount": READING_PRICE_CENTS,
            },
            "quantity": 1,
        }],
        metadata={
            "name": birth["name"], "year": birth["year"], "month": birth["month"],
            "day": birth["day"], "hour": birth["hour"], "minute": birth["minute"],
            "place": birth["place"],
        },
        success_url=f"{BASE_URL}/reading?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{BASE_URL}/",
    )
    return redirect(sess.url, code=303)


def _verify_and_build(session_id):
    sess = stripe.checkout.Session.retrieve(session_id)
    if sess.payment_status != "paid":
        abort(402, "Payment not completed.")
    m = sess.metadata
    birth = {
        "name": m["name"], "year": int(m["year"]), "month": int(m["month"]),
        "day": int(m["day"]), "hour": int(m["hour"]), "minute": int(m["minute"]),
        "place": m["place"],
    }
    chart, dasha, display_name, tz_name = _build_chart_and_dasha(birth)
    sections = generate_full_reading(chart, dasha, name=birth["name"])
    return birth, sections


@app.route("/reading")
def reading():
    session_id = request.args.get("session_id")
    if not session_id:
        abort(400, "Missing session_id")
    birth, sections = _verify_and_build(session_id)
    return render_template("reading.html", birth=birth, sections=sections, session_id=session_id)


@app.route("/reading.pdf")
def reading_pdf():
    session_id = request.args.get("session_id")
    if not session_id:
        abort(400, "Missing session_id")
    birth, sections = _verify_and_build(session_id)
    pdf_bytes = build_reading_pdf(birth["name"], sections)
    return send_file(
        io.BytesIO(pdf_bytes), mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Vedic_Reading_{birth['name'].replace(' ', '_')}.pdf",
    )


@app.route("/dev-skip-payment")
def dev_skip_payment():
    if not app.debug:
        abort(404)
    birth = {
        "name": request.args.get("name", "Test User"),
        "year": int(request.args.get("year", 1990)),
        "month": int(request.args.get("month", 1)),
        "day": int(request.args.get("day", 1)),
        "hour": int(request.args.get("hour", 12)),
        "minute": int(request.args.get("minute", 0)),
        "place": request.args.get("place", "Delhi, India"),
    }
    chart, dasha, display_name, tz_name = _build_chart_and_dasha(birth)
    sections = generate_full_reading(chart, dasha, name=birth["name"])
    return render_template("reading.html", birth=birth, sections=sections, session_id="dev-mode")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
