# --- Imports (strictly alphabetized, flat, no try/except, no blank lines) ---
import base64
import collections
import datetime
import hashlib
import json
import logging
import os
import threading
import time

import jwt
import sqlalchemy
from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from flask_babel import _
from flask_socketio import SocketIO
from flask_wtf import CSRFProtect
from sqlalchemy import literal_column, text
from sqlalchemy.exc import OperationalError

from dependencies import require_role

# --- Flask app init ---
app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True
app.debug = True

# Track app start time for uptime reporting
APP_START_TS = time.time()


@app.route("/set_language/<language>", methods=["POST"])
def set_language_post(language):
    supported = ["fr", "en", "bg"]
    if language not in supported:
        language = "fr"
    session["language"] = language
    resp = redirect(request.referrer or url_for("index"))
    resp.set_cookie("language", language, max_age=60 * 60 * 24 * 30)
    return resp


# Setup logging at the top
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("error.log", encoding="utf-8"),
    ],
)


socketio = SocketIO(app, async_mode="threading")


# Local imports (strictly sorted, all at top-level)
from extensions import babel, db
from models import (
    AdminRole,
    AdminUser,
    HelpRequest,
    PriorityEnum,
    RoleEnum,
    User,
    Volunteer,
)
from models_with_analytics import AnalyticsEvent, Feedback
from permissions import require_admin_login

# Initialize CSRF protection
csrf = CSRFProtect(app)

# --- Define basedir and instance_dir for later use (must be before use) ---
basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, "instance")
os.makedirs(instance_dir, exist_ok=True)


# --- Minimal stub for apply_filters to prevent NameError ---
def apply_filters(query, for_event_type=None, for_language=None):
    # This is a placeholder. Real filtering logic should be implemented as needed.
    if for_event_type:
        query = query.filter(AnalyticsEvent.event_type == for_event_type)
    if for_language:
        query = query.filter(AnalyticsEvent.language == for_language)
    return query


# --- Set secret key for CSRF and sessions (must be before CSRFProtect) ---
app.config["SECRET_KEY"] = os.getenv(
    "HELPCHAIN_SECRET_KEY", os.getenv("SECRET_KEY", "change-me-please")
)
app.secret_key = app.config["SECRET_KEY"]


# --- ADMIN ANALYTICS DASHBOARD ---
@app.route("/admin/analytics", methods=["GET"])
def admin_analytics():
    days = request.args.get("days", 30)
    # TODO: Може да се разшири с реални данни и drilldown
    dashboard_stats = {
        "totals": {
            "requests": 0,
            "volunteers": 0,
            "completed": 0,
            "active": 0,
        },
        "growth": {},
        "recent": [],
    }
    performance_metrics = {
        "success_rate": 0.0,
        "avg_response_time": 0.0,
        "avg_completion_time": 0.0,
    }
    predictions = {"ml_insights": {"anomalies": [], "predictions": {}}}
    trends_data = {"labels": [], "requests": [], "completed": [], "volunteers": []}
    category_stats = {"labels": [], "data": []}
    return render_template(
        "admin_analytics_professional.html",
        dashboard_stats=dashboard_stats,
        performance_metrics=performance_metrics,
        predictions=predictions,
        trends_data=trends_data,
        category_stats=category_stats,
    )


# Setup logging at the top
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("error.log", encoding="utf-8"),
    ],
)


@require_admin_login()
def admin_api_requests():
    # Debug: логни session, claims, username
    logging.debug(f"[admin_api_requests] session: {dict(session)}")
    logging.debug(f"[admin_api_requests] cookies: {request.cookies}")
    logging.debug(f"[admin_api_requests] headers: {dict(request.headers)}")
    claims = getattr(request, "_claims", None)
    logging.debug(f"[admin_api_requests] claims: {claims}")
    admin_username = None
    if session.get("admin_logged_in"):
        try:
            admin = AdminUser.query.filter_by(username="admin").first()
            admin_username = getattr(admin, "username", None)
            # Inject admin claims for downstream API
            request._claims = {"sub": admin_username or "admin", "role": "admin"}
        except Exception:
            pass
    logging.debug(f"[admin_api_requests] admin_username: {admin_username}")
    # Проксито към съществуващия /api/requests, но с админ права
    return api_requests()


@app.route("/admin/api/volunteers")
@require_admin_login()
def admin_api_volunteers():
    # Debug: логни session, claims, username
    logging.debug(f"[admin_api_volunteers] session: {dict(session)}")
    claims = getattr(request, "_claims", None)
    logging.debug(f"[admin_api_volunteers] claims: {claims}")
    admin_username = None
    if session.get("admin_logged_in"):
        try:
            admin = AdminUser.query.filter_by(username="admin").first()
            admin_username = getattr(admin, "username", None)
        except Exception:
            pass
    logging.debug(f"[admin_api_volunteers] admin_username: {admin_username}")
    # Връща списък с доброволци (id, name, email, phone, location)
    volunteers = Volunteer.query.order_by(Volunteer.id.desc()).limit(100).all()

    def serialize_vol(v):
        return {
            "id": v.id,
            "name": v.name,
            "email": v.email,
            "location": getattr(v, "location", None),
        }

    return jsonify({"volunteers": [serialize_vol(v) for v in volunteers]})


@app.route("/admin/requests-table.json")
@require_role("admin", "superadmin", "moderator")
def admin_requests_table():
    # Филтри от заявката (drilldown)
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    channel = request.args.get("channel")
    status_f = request.args.get("status")
    category = request.args.get("category")
    city = request.args.get("city")
    # Пагинация
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(int(request.args.get("page_size", 20)), 100)
    q = HelpRequest.query
    if date_from:
        try:
            from datetime import datetime

            dt = datetime.strptime(date_from, "%Y-%m-%d")
            q = q.filter(HelpRequest.created_at >= dt)
        except Exception:
            pass
    if date_to:
        try:
            from datetime import datetime, timedelta

            dt = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            q = q.filter(HelpRequest.created_at < dt)
        except Exception:
            pass
    if channel:
        q = q.filter(sqlalchemy.func.lower(HelpRequest.channel) == channel.lower())
    if status_f:
        q = q.filter(sqlalchemy.func.lower(HelpRequest.status) == status_f.lower())
    if category:
        q = q.filter(sqlalchemy.func.lower(HelpRequest.title) == category.lower())
    if city:
        q = q.filter(sqlalchemy.func.lower(HelpRequest.city) == city.lower())
    total = q.count()
    items = (
        q.order_by(HelpRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    def serialize_req(r):
        return {
            "id": r.id,
            "title": r.title,
            "category": getattr(r, "category", r.title),
            "city": r.city,
            "status": r.status,
            "priority": getattr(r, "priority", ""),
            "created_at": (
                r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""
            ),
        }

    return jsonify(
        {
            "items": [serialize_req(r) for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@app.route("/admin/feedback-filters.json")
@require_role("admin", "superadmin", "moderator")
def feedback_filters_json():
    # Връща примерни филтри за feedback таба (може да се разшири по нужда)
    return jsonify(
        {
            "categories": ["Общи", "Транспорт", "Здраве", "Друго"],
            "models": ["gpt-4", "gpt-3.5", "local-llm"],
            "languages": ["bg", "en", "uk"],
            "rating_min": 1,
            "rating_max": 5,
        }
    )


def get_locale():
    supported_locales = ["fr", "en", "bg"]
    # 1. Cookie
    lang = request.cookies.get("language")
    if lang in supported_locales:
        return lang
    # 2. Session (fallback)
    lang = session.get("language")
    if lang in supported_locales:
        return lang
    # 3. Browser
    browser_lang = request.accept_languages.best_match(supported_locales)
    if browser_lang:
        return browser_lang
    # 4. Default: French
    return "fr"


babel.locale_selector_func = get_locale
instance_dir = os.path.join(basedir, "instance")
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.join(instance_dir, "volunteers.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# Secure cookie/session defaults
if app.debug:
    app.config["SESSION_COOKIE_SECURE"] = False
else:
    app.config.setdefault("SESSION_COOKIE_SECURE", True)
app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
app.config.setdefault("PERMANENT_SESSION_LIFETIME", 60 * 60 * 8)
# Security headers toggles
app.config.setdefault("SECURITY_HEADERS", True)
app.config.setdefault("CSP_REPORT_ONLY", True)
app.config.setdefault(
    "CSP_POLICY",
    "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'",
)
# Microsoft OIDC placeholders (configure via env or config override)
app.config.setdefault("MICROSOFT_TENANT_ID", os.getenv("MICROSOFT_TENANT_ID", "common"))
app.config.setdefault(
    "MICROSOFT_CLIENT_ID", os.getenv("MICROSOFT_CLIENT_ID", "CHANGE-ME-CLIENT-ID")
)
basedir = os.path.abspath(os.path.dirname(__file__))

# ----------------------------
# i18n (Flask-Babel) setup
# ----------------------------
try:
    # Configure default locale and translation directories
    basedir = os.path.abspath(os.path.dirname(__file__))
    # Default език: френски (FR)
    app.config.setdefault("BABEL_DEFAULT_LOCALE", "fr")
    app.config.setdefault(
        "BABEL_TRANSLATION_DIRECTORIES", os.path.join(basedir, "translations")
    )

    SUPPORTED_LOCALES = ["fr", "en", "bg"]

    def _detect_country_code() -> str | None:
        """Best-effort country detection from common proxy/CDN headers.

        Returns two-letter ISO country code if available (e.g. 'FR', 'EN').
        This avoids external lookups and works behind providers like Cloudflare
        (CF-IPCountry) or AppEngine (X-AppEngine-Country). Returns None if
        nothing reliable is present.
        """
        # Cloudflare
        cc = (request.headers.get("CF-IPCountry") or "").strip().upper()
        if cc:
            return cc
            # AppEngine
            # Inject csrf_token for all templates (for Flask-WTF forms and manual forms)
            from flask_wtf.csrf import generate_csrf
        cc = (request.headers.get("X-AppEngine-Country") or "").strip().upper()
        if cc:
            return cc
        return None

    def _select_locale() -> str:
        # 1) Explicit cookie wins
        lang_cookie = (request.cookies.get("language") or "").strip().lower()
        if lang_cookie in SUPPORTED_LOCALES:
            return lang_cookie

        # 2) Geo-IP via headers: FR->fr, други игнорирай
        cc = _detect_country_code()
        if cc == "FR":
            return "fr"

        # 3) Accept-Language като fallback, но само ако е fr, en или bg
        best = request.accept_languages.best_match(SUPPORTED_LOCALES)
        if best in SUPPORTED_LOCALES:
            return best

        # 4) Винаги връщай френски по подразбиране
        return "fr"

    # Support both Flask-Babel v2 and v3+ init styles
    try:
        babel.init_app(app, locale_selector=_select_locale)  # type: ignore[arg-type]
    except TypeError:
        # Older versions expect setting the selector attribute
        babel.init_app(app)
        try:
            babel.locale_selector_func = _select_locale  # type: ignore[attr-defined]
        except Exception:
            pass

    # Ensure _ is available in templates even if extension doesn't auto-inject


except Exception:
    # If Babel isn't available, continue without i18n (templates still get _ from import)
    pass

# --- Full-Text Search (SQLite FTS5) ---
FTS_ENABLED = False


def _ensure_sqlite_fts():
    """Create FTS5 virtual table and triggers if using SQLite.

    The FTS index covers: title, description, message, city, region, name, email.
    Email is included for privileged-only searching (we restrict query columns by role).
    """
    global FTS_ENABLED
    try:
        if db.engine.name != "sqlite":
            FTS_ENABLED = False
            return
            # Create virtual table (external content)
            db.session.execute(
                text(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS help_requests_fts USING fts5(
                        title, description, message, city, region, name, email,
                        content='help_requests', content_rowid='id'
                    )
                    """
                )
            )
            db.session.execute(
                text(
                    """
                    CREATE TRIGGER IF NOT EXISTS help_requests_ai AFTER INSERT ON help_requests BEGIN
                      INSERT INTO help_requests_fts(rowid,title,description,message,city,region,name,email)
                      VALUES (new.id, new.title, new.description, new.message, new.city, new.region, new.name, new.email);
                    END;
                    """
                )
            )
        db.session.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS help_requests_ad AFTER DELETE ON help_requests BEGIN
                  INSERT INTO help_requests_fts(help_requests_fts, rowid) VALUES('delete', old.id);
                END;
                """
            )
        )
        db.session.execute(
            text(
                """
                CREATE TRIGGER IF NOT EXISTS help_requests_au AFTER UPDATE ON help_requests BEGIN
                  INSERT INTO help_requests_fts(help_requests_fts, rowid) VALUES('delete', old.id);
                  INSERT INTO help_requests_fts(rowid,title,description,message,city,region,name,email)
                  VALUES (new.id, new.title, new.description, new.message, new.city, new.region, new.name, new.email);
                END;
                """
            )
        )
        # Initial (re)build only if empty
        fts_row_count = db.session.execute(
            text("SELECT count(*) FROM help_requests_fts")
        ).scalar()
        if fts_row_count is None or int(fts_row_count) == 0:
            db.session.execute(
                text(
                    "INSERT INTO help_requests_fts(help_requests_fts) VALUES('rebuild')"
                )
            )
        db.session.commit()
        FTS_ENABLED = True
    except OperationalError:
        # Likely FTS5 not compiled in this SQLite build
        db.session.rollback()
        FTS_ENABLED = False
    except Exception:
        db.session.rollback()
        FTS_ENABLED = False


def _fts_build_match_query(q: str, privileged: bool) -> str:
    """Build a restricted FTS5 MATCH expression.

    For non-privileged roles, email is excluded from columns.
    Each token is applied as (col:token*) across allowed columns, ANDed between tokens.
    """
    # Allowed columns
    cols = ["title", "description", "message", "city", "region", "name"]
    if privileged:
        cols.append("email")

    # Normalize tokens, add prefix wildcard
    tokens = [t for t in (q or "").strip().split() if t]
    parts = []

    # Basic sanitation: remove problematic characters for MATCH
    def _escape(tok: str) -> str:
        tok = tok.replace('"', '""')
        return tok

    for tok in tokens:
        tok = _escape(tok)
        col_parts = [f"{c}:{tok}*" for c in cols]
        parts.append("(" + " OR ".join(col_parts) + ")")
    return " AND ".join(parts) if parts else ""


def _apply_text_search(query, q: str, privileged: bool):
    """Apply text search to the SQLAlchemy query depending on backend.

    - SQLite with FTS5: filter by MATCH using help_requests_fts, restricted columns.
    - Other DBs or FTS unavailable: fallback to LIKE/ILIKE across allowed columns.
    """
    if not q:
        return query
    try:
        if db.engine.name == "sqlite" and FTS_ENABLED:
            match_expr = _fts_build_match_query(q, privileged)
            if not match_expr:
                return query, None
            # Join to FTS table for ranking (bm25) and filtering
            query = (
                query.join(
                    text(
                        "help_requests_fts ON help_requests_fts.rowid = help_requests.id"
                    )
                )
                .filter(text("help_requests_fts MATCH :m"))
                .params(m=match_expr)
            )
            rank_expr = literal_column("bm25(help_requests_fts)")
            return query, rank_expr
        else:
            # Fallback: case-insensitive LIKE across allowed columns
            patt = f"%{q.lower()}%"
            cond = (
                sqlalchemy.func.lower(HelpRequest.title).like(patt)
                | sqlalchemy.func.lower(HelpRequest.description).like(patt)
                | sqlalchemy.func.lower(HelpRequest.message).like(patt)
                | sqlalchemy.func.lower(HelpRequest.city).like(patt)
                | sqlalchemy.func.lower(HelpRequest.region).like(patt)
                | sqlalchemy.func.lower(HelpRequest.name).like(patt)
            )
            if privileged:
                cond = cond | sqlalchemy.func.lower(HelpRequest.email).like(patt)
            return query.filter(cond), None
    except Exception:
        # On any unexpected error, return original query (fail open)
        return query, None


# Basic serializer for HelpRequest items used by API responses
def _serialize_request(r):
    try:
        priority_val = getattr(r.priority, "value", None)
    except Exception:
        priority_val = None
    return {
        "id": getattr(r, "id", None),
        "title": getattr(r, "title", None),
        "status": getattr(r, "status", None),
        "priority": priority_val
        or (str(r.priority) if getattr(r, "priority", None) else None),
        "name": getattr(r, "name", None),
        "city": getattr(r, "city", None),
        "region": getattr(r, "region", None),
        "created_at": (
            r.created_at.isoformat() if getattr(r, "created_at", None) else None
        ),
        "updated_at": (
            r.updated_at.isoformat() if getattr(r, "updated_at", None) else None
        ),
    }


# Rate limiting (simple in-memory sliding window)
RATE_LIMIT = int(os.getenv("HELPCHAIN_RATE_LIMIT", "60"))  # requests
RATE_WINDOW = int(os.getenv("HELPCHAIN_RATE_WINDOW", "60"))  # seconds
_rate_lock = threading.Lock()
_rate_hits: dict[str, collections.deque] = collections.defaultdict(
    collections.deque
)  # IP -> deque[timestamps]


def _prune_and_count(ip: str, now: float):
    dq = _rate_hits[ip]
    # Remove timestamps older than window
    while dq and now - dq[0] > RATE_WINDOW:
        dq.popleft()
    return len(dq)


def _register_hit(ip: str, now: float):
    dq = _rate_hits[ip]
    dq.append(now)
    return len(dq)


@app.before_request
def _rate_limit_guard():
    path = request.path or ""
    # Expanded: rate limit all /api/* except health probe
    if path.startswith("/api/") and path != "/api/_health":
        pass
    else:
        return
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "anon"
    now = time.time()
    with _rate_lock:
        current = _prune_and_count(ip, now)
        if current >= RATE_LIMIT:
            retry_after = 1  # suggest short wait
            remaining = max(0, RATE_LIMIT - current)
            resp = jsonify(
                error="rate_limit_exceeded", limit=RATE_LIMIT, window=RATE_WINDOW
            )
            resp.status_code = 429
            resp.headers.update(
                {
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(RATE_LIMIT),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Window": str(RATE_WINDOW),
                }
            )
            return resp
        new_total = _register_hit(ip, now)
        g._rate_remaining = max(0, RATE_LIMIT - new_total)


@app.after_request
def _rate_limit_headers(resp):
    if hasattr(g, "_rate_remaining"):
        resp.headers.setdefault("X-RateLimit-Limit", str(RATE_LIMIT))
        resp.headers.setdefault("X-RateLimit-Remaining", str(g._rate_remaining))
        resp.headers.setdefault("X-RateLimit-Window", str(RATE_WINDOW))
    return resp


@app.after_request
def _security_headers(resp):
    if not app.config.get("SECURITY_HEADERS", True):
        return resp
    # Core security headers
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # Conservative Permissions-Policy baseline
    resp.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    # Content Security Policy (report-only by default to avoid breakage)
    csp = app.config.get("CSP_POLICY") or "default-src 'self'"
    if app.config.get("CSP_REPORT_ONLY", True):
        resp.headers.setdefault("Content-Security-Policy-Report-Only", csp)
    else:
        resp.headers.setdefault("Content-Security-Policy", csp)
    return resp


JWT_SECRET = os.getenv("HELPCHAIN_JWT_SECRET", os.getenv("SECRET_KEY", "change-me"))
JWT_ALG = "HS256"
PRIVILEGED_ROLES = {"admin", "superadmin", "moderator"}
JWT_ISSUER = os.getenv("HELPCHAIN_JWT_ISSUER", "helpchain")
JWT_AUDIENCE = os.getenv("HELPCHAIN_JWT_AUDIENCE", "helpchain-users")
JWT_EXP_SECONDS = int(os.getenv("HELPCHAIN_JWT_EXP", "3600"))  # default 1h


def _create_jwt_secure(user):
    now = int(time.time())
    payload = {
        "sub": user.username,
        "role": getattr(user.role, "value", str(user.role)),
        "iat": now,
        "exp": now + JWT_EXP_SECONDS,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def _decode_jwt_strict(token: str):
    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALG],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "iss", "aud"]},
        )
    except Exception:
        return None


def _create_jwt(user):
    payload = {
        "sub": user.username,
        "role": getattr(user.role, "value", str(user.role)),
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,  # 1h expiry
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def _decode_jwt(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except Exception:
        return None


def _require_auth():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        abort(401)
    token = auth.split(" ", 1)[1].strip()
    # Try strict decode first (issuer/audience); fall back to legacy for older tokens.
    claims = _decode_jwt_strict(token) or _decode_jwt(token)
    if not claims:
        abort(401)
    request._claims = claims
    return claims


@csrf.exempt  # JWT-based JSON login endpoint (no CSRF token expected)
@app.post("/api/login")
def api_login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    if (not username and not email) or not password:
        return jsonify(error="Missing credentials"), 400

    # Accept either username or email; also treat username that looks like email as email
    user = None
    try:
        if email:
            user = User.query.filter(
                sqlalchemy.func.lower(User.email) == email.lower()
            ).first()
        elif username and "@" in username:
            user = User.query.filter(
                sqlalchemy.func.lower(User.email) == username.lower()
            ).first()
        else:
            user = User.query.filter_by(username=username).first()
    except Exception:
        user = None

    if not user or not user.check_password(password):
        return jsonify(error="Invalid credentials"), 401
    token = _create_jwt_secure(user)
    return jsonify(
        access_token=token,
        token_type="Bearer",
        expires_in=3600,
        role=getattr(user.role, "value", str(user.role)),
    )


@app.get("/api")
def api():
    return jsonify(message="Volunteer API ready")


@app.get("/api/requests")
def api_requests():
    # Allow admin session proxy to inject claims
    if not getattr(request, "_claims", None):
        _require_auth()
    page = max(int(request.args.get("page", 1)), 1)
    page_size = int(request.args.get("page_size", 20))
    if page_size > 100:
        page_size = 100

    query = HelpRequest.query
    # Determine role privileges for search (email access)
    claims = getattr(request, "_claims", {}) or {}
    role = (claims.get("role") or "").lower()
    privileged = role in PRIVILEGED_ROLES

    # Filters
    status_param = request.args.get("status")
    if status_param:
        statuses = [s.strip().lower() for s in status_param.split(",") if s.strip()]

        if statuses:
            query = query.filter(
                sqlalchemy.func.lower(HelpRequest.status).in_(statuses)
            )

    city = request.args.get("city")

    if city:
        query = query.filter(sqlalchemy.func.lower(HelpRequest.city) == city.lower())

    category = request.args.get("category")

    if category:
        query = query.filter(
            sqlalchemy.func.lower(HelpRequest.title) == category.lower()
        )

    search = request.args.get("q") or request.args.get("search")
    # Apply FTS5 / fallback search only when provided
    result = _apply_text_search(query, search, privileged)
    if isinstance(result, tuple) and len(result) == 2:
        query, rank_expr = result
    else:
        query, rank_expr = result, None

    # Multi-column sorting: ?sort=created_at,-priority,city
    raw_sort = request.args.get("sort") or "created_at"
    columns_map = {
        "created_at": HelpRequest.created_at,
        "priority": HelpRequest.priority,
        "city": HelpRequest.city,
        "status": HelpRequest.status,
        "category": HelpRequest.title,
        "title": HelpRequest.title,
        "id": HelpRequest.id,
    }
    order_by = []
    # If ranked search is active, order by rank first (lower is better)
    if rank_expr is not None:
        order_by.append(rank_expr.asc())
    for part in [p.strip() for p in raw_sort.split(",") if p.strip()]:
        direction = "asc"
        name = part
        if part.startswith("-"):
            direction = "desc"
            name = part[1:]
        col = columns_map.get(name.lower())
        if not col:
            continue
        order_by.append(col.desc() if direction == "desc" else col.asc())
    if not order_by:
        order_by = [HelpRequest.created_at.desc()]

    total = query.count()
    items = (
        query.order_by(*order_by).offset((page - 1) * page_size).limit(page_size).all()
    )

    # ETag for caching
    latest_ts = (
        db.session.query(sqlalchemy.func.max(HelpRequest.updated_at)).scalar() or "0"
    )
    etag_payload = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "sort": raw_sort,
        "status": status_param,
        "city": city,
        "category": category,
        "search": search,
        "latest": str(latest_ts),
    }
    etag_val = hashlib.sha256(
        json.dumps(etag_payload, sort_keys=True).encode()
    ).hexdigest()
    client_etag = request.headers.get("If-None-Match")
    if client_etag == etag_val:
        return Response(status=304, headers={"ETag": etag_val})

    data = [_serialize_request(r) for r in items]
    resp = jsonify(
        {
            "data": data,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size,
            "etag": etag_val,
        }
    )
    resp.headers["ETag"] = etag_val
    return resp


@app.get("/api/requests/<int:request_id>")
def api_request_detail(request_id: int):
    _require_auth()
    req = HelpRequest.query.get_or_404(request_id)
    detail = _serialize_request(req)

    # Mask email & phone for privacy
    def _mask_email(email: str | None) -> str | None:
        if not email or "@" not in email:
            return None
        name, domain = email.split("@", 1)
        if not name:
            return "***@" + domain
        return name[0] + "***@" + domain

    def _mask_phone(phone: str | None) -> str | None:
        if not phone:
            return None
        digits = "".join(ch for ch in phone if ch.isdigit())
        if len(digits) <= 2:
            return "*" * len(digits)
        return "*" * (len(digits) - 2) + digits[-2:]

    claims = getattr(request, "_claims", {}) or {}
    role = (claims.get("role") or "").lower()
    privileged = role in PRIVILEGED_ROLES
    detail.update(
        {
            "description": req.description,
            "message": req.message,
            "email_masked": _mask_email(req.email),
            "phone_masked": _mask_phone(req.phone),
            "email": req.email if privileged else None,
            "phone": req.phone if privileged else None,
        }
    )
    return jsonify(detail)


@app.get("/demo/volunteers")
def demo_volunteers():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(base_dir, "volunteer_dashboard.html")


@app.get("/demo/request")
def demo_request_page():
    """Serve a simple request detail page that fetches info from the API."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(base_dir, "request_detail.html")


@app.route("/volunteer_login", methods=["GET", "POST"])
def volunteer_login_redirect():
    """Backward-compatible route that redirects to the demo dashboard.

    Uses 303 See Other for correctness: when a form POSTs here the client is
    explicitly instructed to perform a GET to the target, avoiding any chance
    of the POST body being re-sent.
    """
    return redirect(url_for("demo_volunteers"), code=303)


@app.route("/volunteer_register", methods=["GET", "POST"])
def volunteer_register():
    """Register a volunteer and show the volunteer registration form.

    Mirrors the logic found in legacy app variants (appy.py) but kept minimal.
    """
    if request.method == "POST":
        try:
            v = Volunteer(
                name=request.form.get("name"),
                email=request.form.get("email"),
                phone=request.form.get("phone"),
                skills=request.form.get("skills"),
                location=request.form.get("location"),
            )
            db.session.add(v)
            db.session.commit()
            flash("Благодарим ви! Регистрацията като доброволец е успешна.", "success")
            return redirect(url_for("index"))
        except Exception as e:
            db.session.rollback()
            flash(f"Грешка при записване: {e}", "error")
    return render_template("volunteer_register.html")


@app.route("/submit_request", methods=["GET", "POST"])
def submit_request():
    """Create a help request; mirrors simplified logic from modular app variant."""
    if request.method == "POST":
        data = request.form
        try:
            r = HelpRequest(
                name=data.get("name"),
                email=data.get("email"),
                title=data.get("title") or data.get("category"),
                city=data.get("location"),
                description=data.get("description") or data.get("problem"),
                message=data.get("message") or data.get("description"),
                status="pending",
                priority=(
                    PriorityEnum.normal if hasattr(PriorityEnum, "normal") else None
                ),
            )
            db.session.add(r)
            db.session.commit()
            flash("Заявката е изпратена успешно!", "success")
            return redirect(url_for("index"))
        except Exception as e:
            db.session.rollback()
            flash(f"Грешка при подаване на заявката: {e}", "error")
    return render_template("submit_request.html")


@app.get("/privacy")
def privacy():
    """Serve privacy policy page referenced in footer."""
    return render_template("privacy.html")


@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    """Handle feedback form submission and display."""
    if request.method == "POST":
        try:
            feedback_entry = Feedback(
                name=request.form.get("name"),
                email=request.form.get("email"),
                message=request.form.get("message"),
                user_type="guest",
            )
            db.session.add(feedback_entry)
            db.session.commit()
            flash("Благодарим ви за обратната връзка!", "success")
            return redirect(url_for("index"))
        except Exception as e:
            db.session.rollback()
            flash(f"Грешка при изпращане: {e}", "error")
    return render_template("feedback.html")


@app.get("/favicon.ico")
def favicon():
    """Serve favicon; prefer static file, fallback to tiny PNG to avoid 404."""
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    ico_path = os.path.join(static_dir, "favicon.ico")
    if os.path.exists(ico_path):
        return send_from_directory(static_dir, "favicon.ico")

    # 1x1 transparent PNG (base64)
    tiny_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAF/wKz0m4zxwAAAABJRU5ErkJggg=="
    data = base64.b64decode(tiny_png_b64)
    return Response(data, mimetype="image/png")


@app.get("/api/_fts_status")
def api_fts_status():
    """Diagnostic endpoint: engine, FTS status, counts, triggers (auth required)."""
    _require_auth()
    info = {}
    try:
        engine_name = getattr(db.engine, "name", "unknown")
    except Exception:
        engine_name = "unknown"
    info["engine"] = engine_name
    info["fts_enabled"] = bool(FTS_ENABLED)

    # Basic counts
    try:
        total = (
            db.session.query(sqlalchemy.func.count.label("count"))
            .select_from(HelpRequest)
            .scalar()
            or 0
        )
        info["help_requests_count"] = int(total)
    except Exception:
        info["help_requests_count"] = None

    if engine_name == "sqlite":
        # SQLite version
        try:
            info["sqlite_version"] = db.session.execute(
                text("select sqlite_version()")
            ).scalar()
        except Exception:
            pass

        # Trigger presence
        try:
            rows = db.session.execute(
                text(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='trigger' AND tbl_name='help_requests'
                """
                )
            ).fetchall()
            names = {r[0] for r in rows}
            info["fts_triggers_present"] = {
                "help_requests_ai": "help_requests_ai" in names,
                "help_requests_au": "help_requests_au" in names,
                "help_requests_ad": "help_requests_ad" in names,
            }
        except Exception:
            pass

        # FTS row count
        if FTS_ENABLED:
            try:
                fts_count = db.session.execute(
                    text("SELECT count(*) FROM help_requests_fts")
                ).scalar()
                info["fts_rows"] = int(fts_count or 0)
            except Exception:
                info["fts_rows"] = None

    return jsonify(info)


@app.get("/api/_health")
def api_health():
    """Minimal health endpoint: unauthenticated OK + uptime."""
    uptime = max(0, int(time.time() - APP_START_TS))
    return jsonify(status="ok", ok=True, uptime_seconds=uptime)


def _seed_if_empty():
    with app.app_context():
        # Ensure a default admin user exists for local testing
        if User.query.filter_by(username="admin").first() is None:
            try:
                u = User(
                    username="admin", email="admin@example.com", role=RoleEnum.admin
                )
                # Seed с силна парола (>=10, главна, малка, цифри, специален знак)
                try:
                    u.set_password("Admin12345!")
                except Exception:
                    # Ако политиката се промени и хвърли грешка – fallback към друга валидна парола
                    try:
                        u.set_password("Admin123456!")
                    except Exception:
                        pass
                db.session.add(u)
                db.session.commit()
            except Exception:
                db.session.rollback()
        # Ensure an AdminUser account exists for admin console (lockout-enabled)
        _AdminRole = None
        try:
            _AdminRole = AdminRole
        except Exception:
            pass
        if AdminUser.query.filter_by(username="admin").first() is None:
            try:
                au = AdminUser(
                    username="admin",
                    email="admin@example.com",
                    role=_AdminRole.ADMIN if _AdminRole else None,
                )
                try:
                    au.set_password("Admin12345!")
                except Exception:
                    try:
                        au.set_password("Admin123456!")
                    except Exception:
                        pass
                au.failed_login_attempts = 0
                au.locked_until = None
                db.session.add(au)
                db.session.commit()
            except Exception:
                db.session.rollback()
        # Ensure a default non-privileged user exists
        if User.query.filter_by(username="testuser").first() is None:
            try:
                u2 = User(
                    username="testuser", email="user@example.com", role=RoleEnum.user
                )
                u2.set_password("secret123")
                db.session.add(u2)
                db.session.commit()
            except Exception:
                db.session.rollback()
        if HelpRequest.query.count() == 0:
            samples = [
                {
                    "name": "Marie D.",
                    "email": "marie@example.com",
                    "title": "Administrative",
                    "city": "Paris",
                    "description": "Need help with residency paperwork.",
                    "status": "pending",
                    "priority": PriorityEnum.MEDIUM.value,
                },
                {
                    "name": "Jean P.",
                    "email": "jean@example.com",
                    "title": "Medical",
                    "city": "Lyon",
                    "description": "Looking for transport to clinic.",
                    "status": "in_progress",
                    "priority": PriorityEnum.LOW.value,
                },
                {
                    "name": "Amina K.",
                    "email": "amina@example.com",
                    "title": "Social",
                    "city": "Marseille",
                    "description": "Seeking community meetup information.",
                    "status": "completed",
                    "priority": PriorityEnum.MEDIUM.value,
                },
            ]
            for s in samples:
                db.session.add(HelpRequest(**s))
            db.session.commit()


# ----------------------------
# Public site routes (UX)
# ----------------------------


@app.get("/")
def index():
    from flask import request

    lang_cookie = (request.cookies.get("language") or "fr").strip().lower()
    current_locale = lang_cookie if lang_cookie in ["fr", "en", "bg"] else "fr"
    return render_template("index.html", current_locale=current_locale)


# Redirect legacy static preview URL към новата начална страница
@app.get("/static/previews/new-page.html")
def legacy_preview_redirect():
    return redirect(url_for("index"), code=301)


@app.get("/robots.txt")
def robots_txt():
    # Disallow admin paths from indexing even if they exist elsewhere
    lines = [
        "User-agent: *",
        "Disallow: /admin",
        "Disallow: /admin/",
        "Disallow: /admin_login",
        "Disallow: /admin/*",
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@app.get("/sw.js")
def service_worker():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Serve the service worker from the app root path
    return send_from_directory(base_dir, "sw.js", mimetype="application/javascript")


@app.get("/static/previews/new-page.html")
def legacy_preview_redirect_root():
    """Redirect old static preview URL to the new homepage."""
    return redirect(url_for("index"), code=301)


@app.errorhandler(400)
def csrf_error_handler(err):
    # Provide friendlier message if it's a CSRF failure.
    description = getattr(err, "description", "Bad request")
    if "CSRF" in str(description):
        return (
            render_template(
                "csrf_error.html", message="CSRF validation failed. Please retry."
            ),
            400,
        )
    return err


# ---------------------------------
# Minimal admin routes (login + dashboard) for CSRF enforcement testing.
# These are a lightweight subset to allow verifying hidden token rejection.
# ---------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        admin = None
        user = None
        security_logger = logging.getLogger("security")
        remote_ip = request.remote_addr or "?"
        logging.debug(
            f"[admin_login] POST: username={username!r}, password_len={len(password)}"
        )
        security_logger.info(
            f"admin_login_attempt start username={username!r} ip={remote_ip} password_len={len(password)}"
        )
        if username:
            try:
                admin = AdminUser.query.filter(
                    sqlalchemy.func.lower(AdminUser.username) == username.lower()
                ).first()
                logging.debug(f"[admin_login] AdminUser found: {admin is not None}")
            except Exception as e:
                logging.warning(f"[admin_login] Exception in AdminUser.query: {e}")
                admin = None
            if admin is None:
                try:
                    user = User.query.filter(
                        sqlalchemy.func.lower(User.username) == username.lower()
                    ).first()
                    logging.debug(
                        f"[admin_login] User fallback found: {user is not None}"
                    )
                except Exception as e:
                    logging.warning(f"[admin_login] Exception in User.query: {e}")
                    user = None

        # If AdminUser exists, check password only (lockout policy DISABLED for dev)
        if admin is not None:
            pw_ok = admin.check_password(password)
            logging.debug(f"[admin_login] AdminUser.check_password: {pw_ok}")
            if not pw_ok:
                try:
                    admin.failed_login_attempts = (admin.failed_login_attempts or 0) + 1
                    db.session.add(admin)
                    db.session.commit()
                except Exception as e:
                    logging.warning(
                        f"[admin_login] Exception updating failed_login_attempts: {e}"
                    )
                    db.session.rollback()
                flash("Невалидни данни за вход.", "error")
                security_logger.warning(
                    f"admin_login_failure username={username!r} ip={remote_ip} reason=bad_password attempts={getattr(admin, 'failed_login_attempts', '?')}"
                )
                logging.debug(
                    f"[admin_login] Session after failed login: {dict(session)}"
                )
                return render_template("admin_login.html"), 401

            try:
                admin.failed_login_attempts = 0
                db.session.add(admin)
                db.session.commit()
            except Exception as e:
                logging.warning(
                    f"[admin_login] Exception resetting failed_login_attempts: {e}"
                )
                db.session.rollback()
            session["admin_logged_in"] = True
            logging.info(
                f"[admin_login] Set session['admin_logged_in']=True for {username!r}"
            )
            logging.debug(
                f"[admin_login] Session after successful login: {dict(session)}"
            )
            flash("Успешен вход.", "success")
            security_logger.info(
                f"admin_login_success username={username!r} ip={remote_ip} model=AdminUser"
            )
            logging.info(
                f"[admin_login] Redirecting to admin_dashboard for {username!r}"
            )
            return redirect(url_for("admin_dashboard"))

        # Legacy: fallback to User without lockout
        if not user or not user.check_password(password):
            flash("Невалидни данни за вход.", "error")
            security_logger.warning(
                f"admin_login_failure username={username!r} ip={remote_ip} reason=legacy_user_bad_password"
            )
            logging.debug(
                f"[admin_login] Session after legacy user failed login: {dict(session)}"
            )
            return render_template("admin_login.html"), 401
        session["admin_logged_in"] = True
        logging.info(
            f"[admin_login] Set session['admin_logged_in']=True for legacy user {username!r}"
        )
        logging.debug(
            f"[admin_login] Session after legacy user successful login: {dict(session)}"
        )
        flash("Успешен вход.", "success")
        security_logger.info(
            f"admin_login_success username={username!r} ip={remote_ip} model=User legacy_break_glass=True"
        )
        logging.info(
            f"[admin_login] Redirecting to admin_dashboard for legacy user {username!r}"
        )
        return redirect(url_for("admin_dashboard"))
    return render_template("admin_login.html")


@app.route("/login", methods=["POST"])
def user_login():
    """HTML form login for regular users (username or email + password).

    Form fields expected: username/email, password. If checkbox `is_admin` is set,
    delegate to admin login route logic (redirect POST).
    """
    # If admin checkbox toggled, forward to admin login logic to reuse lockout
    if request.form.get("is_admin") == "1":
        # Reuse admin login by calling its logic directly
        return admin_login()
    identifier = (
        request.form.get("username") or request.form.get("email") or ""
    ).strip()
    password = request.form.get("password") or ""
    if not identifier or not password:
        flash("Липсват данни за вход.", "error")
        return redirect(url_for("index"))
    user = None
    try:
        if "@" in identifier:
            user = User.query.filter(
                sqlalchemy.func.lower(User.email) == identifier.lower()
            ).first()
        else:
            user = User.query.filter(
                sqlalchemy.func.lower(User.username) == identifier.lower()
            ).first()
    except Exception:
        user = None
    if not user or not user.check_password(password):
        flash("Невалидни данни за вход.", "error")
        return redirect(url_for("index"))
    # Basic active check
    if hasattr(user, "is_active") and not user.is_active:
        flash("Акаунтът не е активиран.", "error")
        return redirect(url_for("index"))
    session["user_logged_in"] = True
    session["user_id"] = user.id
    session["user_role"] = getattr(user.role, "value", str(user.role))
    flash("Успешен вход.", "success")
    return redirect(url_for("index"))


@app.route("/logout", methods=["POST"])
def logout():
    """Unified logout for user/admin sessions via POST with CSRF protection."""
    session.pop("user_logged_in", None)
    session.pop("admin_logged_in", None)
    session.pop("user_id", None)
    session.pop("user_role", None)
    flash("Излязохте от системата.", "success")
    return redirect(url_for("index"))


@app.route("/admin_dashboard", methods=["GET"])
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    # Basic data queries (defensive: ignore failures individually)
    try:
        requests_page = (
            HelpRequest.query.order_by(HelpRequest.created_at.desc()).limit(50).all()
        )
    except Exception:
        requests_page = []
    try:
        volunteers_page = (
            Volunteer.query.order_by(Volunteer.created_at.desc()).limit(50).all()
        )
    except Exception:
        volunteers_page = []

    # Stats expected by enhanced admin_dashboard template
    def _safe_count(query_fn):
        try:
            return int(query_fn())
        except Exception:
            return 0

    stats = {
        "total_requests": _safe_count(lambda: HelpRequest.query.count()),
        "pending_requests": _safe_count(
            lambda: HelpRequest.query.filter(
                sqlalchemy.func.lower(HelpRequest.status) == "pending"
            ).count()
        ),
        "in_progress": _safe_count(
            lambda: HelpRequest.query.filter(
                sqlalchemy.func.lower(HelpRequest.status) == "in_progress"
            ).count()
        ),
        "completed_requests": _safe_count(
            lambda: HelpRequest.query.filter(
                sqlalchemy.func.lower(HelpRequest.status) == "completed"
            ).count()
        ),
    }

    # Wrapper object that supports both .items and .get('items') for template variants
    class RequestsWrapper:
        def __init__(self, items):
            self.items = items

        def get(self, key, default=None):
            return self.items if key == "items" else default

    current_admin = User.query.filter_by(username="admin").first()
    return render_template(
        "admin_dashboard.html",
        requests=RequestsWrapper(requests_page),
        volunteers=volunteers_page,
        stats=stats,
        current_user=current_admin,
    )


@app.route("/admin/2fa/disable", methods=["POST"])
def admin_2fa_disable():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    # Placeholder: In full implementation we'd alter a two_factor_enabled flag.
    flash("2FA деактивиране (демо).", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/2fa/setup", methods=["GET", "POST"])
def admin_2fa_setup():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        # Accept token field (demo only); CSRF will enforce hidden token.
        flash("2FA настройка (демо) завършена.", "success")
        return redirect(url_for("admin_dashboard"))
    # Minimal inline template keeps dependency surface small.
    return (
        render_template("admin_2fa_setup.html")
        if app.jinja_env.list_templates().count("admin_2fa_setup.html")
        else Response(
            "<h1>2FA Setup</h1><p>Demo страница. POST с валиден CSRF ще завърши.</p>"
        )
    )


# ---------------------------------
# Dev-only admin password reset helper (local debug convenience)
# GET /admin/dev_reset -> resets admin password to a strong default if in debug.
# ---------------------------------
@app.get("/admin/dev_reset")
def admin_dev_reset():
    # Allow only in debug / development to prevent accidental exposure.
    if not app.debug:
        abort(404)
    from sqlalchemy import func as _func

    admin = AdminUser.query.filter(_func.lower(AdminUser.username) == "admin").first()
    created = False
    if admin is None:
        admin = AdminUser(username="admin", email="admin@example.com")
        created = True
    try:
        # Strong password meeting policy: >=10 chars, upper, lower, digits, special
        admin.set_password("Admin12345!")
        admin.failed_login_attempts = 0
        admin.locked_until = None
        db.session.add(admin)
        db.session.commit()
        flash("Админ паролата е нулирана на Admin12345!", "success")
        if created:
            flash("Създаден е нов админ акаунт (admin).", "info")
    except Exception as e:
        db.session.rollback()
        flash(f"Грешка при нулиране: {e}", "error")

    return redirect(url_for("admin_login"))


# --- ADMIN AI DASHBOARD ---
@app.route("/admin/ai-dashboard")
def ai_dashboard():
    return render_template("ai_dashboard.html")


# --- KPI JSON API for dashboard ---
@app.route("/admin/kpi.json")
def kpi_json():
    # (imports moved to top)
    now = datetime.datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - datetime.timedelta(days=1)
    week_start = today_start - datetime.timedelta(days=now.weekday())
    # Requests today, yesterday, week
    today_count = AnalyticsEvent.query.filter(
        AnalyticsEvent.created_at >= today_start
    ).count()
    yesterday_count = AnalyticsEvent.query.filter(
        AnalyticsEvent.created_at >= yesterday_start,
        AnalyticsEvent.created_at < today_start,
    ).count()
    week_count = AnalyticsEvent.query.filter(
        AnalyticsEvent.created_at >= week_start
    ).count()
    # % change vs yesterday
    today_delta = 0
    if yesterday_count:
        today_delta = round((today_count - yesterday_count) / yesterday_count * 100, 1)
    # Weekly trend (vs previous week)
    prev_week_start = week_start - datetime.timedelta(days=7)
    prev_week_count = AnalyticsEvent.query.filter(
        AnalyticsEvent.created_at >= prev_week_start,
        AnalyticsEvent.created_at < week_start,
    ).count()
    week_trend = 0
    if prev_week_count:
        week_trend = round((week_count - prev_week_count) / prev_week_count * 100, 1)
    # Latency (AI only)
    ai_q = AnalyticsEvent.query.filter(
        AnalyticsEvent.event_type == "AI", AnalyticsEvent.created_at >= today_start
    )
    latency_sec = round(
        (
            ai_q.with_entities(sqlalchemy.func.avg(AnalyticsEvent.load_time)).scalar()
            or 0
        ),
        2,
    )
    # Success % (label == 'success')
    total_ai = ai_q.count() or 1
    success_count = ai_q.filter(AnalyticsEvent.event_label == "success").count()
    success_pct = round(success_count / total_ai * 100, 1)
    # AI status (dummy logic)
    ai_status = "OK" if latency_sec < 2 else "SLOW" if latency_sec < 5 else "ERROR"
    # AI latency ms (for badge coloring)
    ai_latency_ms = int(latency_sec * 1000)
    return jsonify(
        {
            "today": today_count,
            "today_delta": today_delta,
            "week": week_count,
            "week_trend": week_trend,
            "latency_sec": latency_sec,
            "success_pct": success_pct,
            "ai_status": ai_status,
            "ai_latency_ms": ai_latency_ms,
        }
    )


@app.route("/admin/ai-stats.json")
def ai_stats():
    # (imports moved to top)
    now = datetime.datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - datetime.timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    # --- Филтри от заявката ---
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    channel = request.args.get("channel")
    language = request.args.get("language")
    status_f = request.args.get("status")

    # Total requests
    requests_today = apply_filters(
        AnalyticsEvent.query.filter(AnalyticsEvent.created_at >= today_start)
    ).count()
    requests_week = apply_filters(
        AnalyticsEvent.query.filter(AnalyticsEvent.created_at >= week_start)
    ).count()
    requests_month = apply_filters(
        AnalyticsEvent.query.filter(AnalyticsEvent.created_at >= month_start)
    ).count()

    # By channel
    total = apply_filters(AnalyticsEvent.query).count() or 1
    ai_count = apply_filters(AnalyticsEvent.query, for_event_type="AI").count()
    faq_count = apply_filters(AnalyticsEvent.query, for_event_type="FAQ").count()
    human_count = apply_filters(AnalyticsEvent.query, for_event_type="Human").count()
    percent_ai = round(ai_count / total * 100)
    percent_faq = round(faq_count / total * 100)
    percent_human = round(human_count / total * 100)

    # Average latency (AI only)
    avg_latency = (
        apply_filters(
            AnalyticsEvent.query.with_entities(
                sqlalchemy.func.avg(AnalyticsEvent.load_time)
            ),
            for_event_type="AI",
        ).scalar()
        or 0
    )
    avg_latency = int(avg_latency * 1000)  # ms

    # Success rate (AI only, event_label == 'success')
    ai_total = apply_filters(AnalyticsEvent.query, for_event_type="AI").count() or 1
    ai_success = (
        apply_filters(AnalyticsEvent.query, for_event_type="AI")
        .filter(AnalyticsEvent.event_label == "success")
        .count()
    )
    success_rate = round(ai_success / ai_total * 100)

    # Status (dummy: online if avg_latency < 3000ms)
    status = (
        "online"
        if avg_latency < 3000
        else ("degraded" if avg_latency < 7000 else "offline")
    )

    # Line chart: requests per day (last 7 days)
    days = [(today_start - datetime.timedelta(days=i)) for i in range(6, -1, -1)]
    labels = [d.strftime("%d.%m") for d in days]
    data = []
    for d in days:
        d2 = d + datetime.timedelta(days=1)
        data.append(
            apply_filters(
                AnalyticsEvent.query.filter(
                    AnalyticsEvent.created_at >= d, AnalyticsEvent.created_at < d2
                )
            ).count()
        )

    # Средно време за отговор по канал
    avg_faq = (
        apply_filters(
            AnalyticsEvent.query.with_entities(
                sqlalchemy.func.avg(AnalyticsEvent.load_time)
            ),
            for_event_type="FAQ",
        ).scalar()
        or 0
    )
    avg_ai = (
        apply_filters(
            AnalyticsEvent.query.with_entities(
                sqlalchemy.func.avg(AnalyticsEvent.load_time)
            ),
            for_event_type="AI",
        ).scalar()
        or 0
    )
    avg_human = (
        apply_filters(
            AnalyticsEvent.query.with_entities(
                sqlalchemy.func.avg(AnalyticsEvent.load_time)
            ),
            for_event_type="Human",
        ).scalar()
        or 0
    )
    avg_by_channel = {
        "faq": int(avg_faq * 1000),
        "ai": int(avg_ai * 1000),
        "human": int(avg_human * 1000),
    }
    return jsonify(
        {
            "requests_today": requests_today,
            "requests_week": requests_week,
            "requests_month": requests_month,
            "percent_ai": percent_ai,
            "percent_faq": percent_faq,
            "percent_human": percent_human,
            "avg_latency": avg_latency,
            "success_rate": success_rate,
            "status": status,
            "avg_by_channel": avg_by_channel,
            "chart": {"labels": labels, "data": data},
        }
    )


### --- FEEDBACK QUALITY PANEL ---


@app.route("/admin/feedback-stats.json")
def feedback_stats():
    # (imports moved to top)
    # Филтри
    category = request.args.get("category")
    model = request.args.get("model")
    language = request.args.get("language")
    rating_min = request.args.get("rating_min", type=float)
    rating_max = request.args.get("rating_max", type=float)
    q = Feedback.query
    if category:
        q = q.filter(Feedback.page_url.like(f"%{category}%"))
    if model:
        q = q.filter(Feedback.ai_provider == model)
    if language:
        q = q.filter(Feedback.user_type == language)
    if rating_min is not None:
        q = q.filter(Feedback.sentiment_score >= rating_min)
    if rating_max is not None:
        q = q.filter(Feedback.sentiment_score <= rating_max)

    # Среден рейтинг (sentiment_score)
    avg_rating = (
        q.with_entities(sqlalchemy.func.avg(Feedback.sentiment_score)).scalar() or 0
    )

    # Breakdown по език
    avg_by_lang = (
        Feedback.query.with_entities(
            Feedback.user_type, sqlalchemy.func.avg(Feedback.sentiment_score)
        )
        .group_by(Feedback.user_type)
        .all()
    )
    avg_by_lang = [
        {
            "language": str(t) if t is not None and t != "None" else "Unknown",
            "avg_rating": float(round(r, 2)) if r is not None else 0.0,
        }
        for t, r in avg_by_lang
    ]

    # Breakdown по категория
    avg_by_cat = (
        Feedback.query.with_entities(
            Feedback.page_url, sqlalchemy.func.avg(Feedback.sentiment_score)
        )
        .group_by(Feedback.page_url)
        .all()
    )
    avg_by_cat = [
        {
            "category": (
                str((cat or "").split("/")[-1])
                if cat is not None and str(cat).lower() != "none"
                else "Unknown"
            ),
            "avg_rating": float(round(r, 2)) if r is not None else 0.0,
        }
        for cat, r in avg_by_cat
    ]

    # Breakdown по модел
    avg_by_model = (
        Feedback.query.with_entities(
            Feedback.ai_provider, sqlalchemy.func.avg(Feedback.sentiment_score)
        )
        .group_by(Feedback.ai_provider)
        .all()
    )
    avg_by_model = [
        {
            "model": str(mod) if mod is not None and mod != "None" else "Unknown",
            "avg_rating": float(round(r, 2)) if r is not None else 0.0,
        }
        for mod, r in avg_by_model
    ]

    # Breakdown по sentiment_label
    avg_by_label = (
        Feedback.query.with_entities(
            Feedback.sentiment_label, sqlalchemy.func.count.label("count")
        )
        .group_by(Feedback.sentiment_label)
        .all()
    )
    avg_by_label = [
        {"label": str(lbl) if lbl not in (None, "None") else "", "count": int(cnt)}
        for lbl, cnt in avg_by_label
    ]

    # Проблемни категории (avg < 3.0)
    problematic_categories = [
        (
            str(cat["category"])
            if cat.get("category") not in (None, "", "None")
            else "Unknown"
        )
        for cat in avg_by_cat
        if cat.get("avg_rating", 0) < 3.0
    ]
    problematic_categories = sorted(
        [c for c in problematic_categories if c not in (None, "", "None")], key=str
    )

    # Най-високо/ниско оценени отговори (top 10, bottom 10)
    best = q.order_by(Feedback.sentiment_score.desc()).limit(10).all()
    worst = q.order_by(Feedback.sentiment_score.asc()).limit(10).all()

    def fb_to_dict(fb):
        preview = (fb.message or "")[:50] + (
            "..." if fb.message and len(fb.message) > 50 else ""
        )
        highlight = False
        # Highlight ако категорията е проблемна
        cat = (
            str(getattr(fb, "page_url", "") or "Unknown").split("/")[-1]
            if getattr(fb, "page_url", None) is not None
            else "Unknown"
        )
        if cat in problematic_categories:
            highlight = True
        return {
            "id": fb.id if fb.id is not None else 0,
            "score": (
                float(fb.sentiment_score) if fb.sentiment_score is not None else 0.0
            ),
            "label": (
                str(fb.sentiment_label)
                if fb.sentiment_label not in (None, "None")
                else ""
            ),
            "message": fb.message or "",
            "preview": preview,
            "language": str(getattr(fb, "user_type", "") or "Unknown"),
            "category": cat,
            "user_type": str(getattr(fb, "user_type", "") or "Unknown"),
            "model": str(getattr(fb, "ai_provider", "") or "Unknown"),
            "timestamp": (
                fb.timestamp.strftime("%Y-%m-%d %H:%M")
                if getattr(fb, "timestamp", None)
                else ""
            ),
            "highlight": highlight,
        }

    # Tooltip причини за нисък рейтинг (примерно sentiment_label)
    tooltip_map = {
        "negative": "Отговорът не беше полезен",
        "neutral": "Неутрален/неясен отговор",
        "positive": "Положителен отговор",
        "": "",
    }

    return jsonify(
        {
            "avg_rating": round(avg_rating, 2) if avg_rating else 0,
            "avg_by_lang": avg_by_lang,
            "avg_by_cat": avg_by_cat,
            "avg_by_model": avg_by_model,
            "avg_by_label": avg_by_label,
            "problematic_categories": problematic_categories,
            "best": [fb_to_dict(fb) for fb in best],
            "worst": [fb_to_dict(fb) for fb in worst],
            "tooltip_map": tooltip_map,
        }
    )


@app.route("/analytics/api/analytics/export")
def analytics_export():
    format = request.args.get("format", "json")
    # TODO: Добави логика за генериране на файл/данни
    if format == "csv":
        # Пример: връщане на CSV файл
        return send_file("path/to/your.csv", as_attachment=True)
    else:
        # Пример: връщане на JSON
        data = {"example": 123}
        return jsonify(data)


@app.route("/analytics/api/analytics/live")
def analytics_live():
    # TODO: Добави логика за live данни
    return jsonify({"live": True})


# --- Flask entrypoint ---
@app.route("/set_language")
def set_language():
    lang = request.args.get("language", "fr")
    next_url = request.args.get("next", url_for("index"))
    resp = redirect(next_url)
    # Поддържани езици
    supported = ["fr", "en", "bg"]
    if lang not in supported:
        lang = "fr"
    resp.set_cookie("language", lang, max_age=60 * 60 * 24 * 30)  # 30 дни
    session["language"] = lang
    return resp


app.config["PROPAGATE_EXCEPTIONS"] = True
app.debug = True


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)

logging.basicConfig(level=logging.DEBUG)
