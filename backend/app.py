import base64
import hashlib
import json
import logging
import os
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock

import jwt
from flask import (
    Flask,
    Response,
    abort,
    flash,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_wtf import CSRFProtect

from .models import User

try:
    from dotenv import load_dotenv  # type: ignore

    # Load .env explicitly from this file's directory (robust against cwd changes)
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_env_path)
except Exception:
    pass  # Fail-open if python-dotenv not installed yet
from flask_babel import gettext as _  # ensure _ available if Babel not auto-injected
from sqlalchemy import func, literal_column, text
from sqlalchemy.exc import OperationalError

# Робустни импорти: позволяват стартиране и в двата режима.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
for _p in (BASE_DIR, PARENT_DIR):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

db = None
HelpRequest = None
PriorityEnum = None
User = None
RoleEnum = None
Volunteer = None
AdminUser = None

from .extensions import babel, db  # type: ignore
from .microsoft_auth import bp as microsoft_bp  # type: ignore
from .models import AdminUser, HelpRequest, PriorityEnum, RoleEnum, User, Volunteer  # type: ignore

app = Flask(__name__)
# Ensure a concrete secret key (Flask-WTF requires app.secret_key not None).
_secret = (
    os.getenv("HELPCHAIN_SECRET_KEY")
    or os.getenv("SECRET_KEY")
    or "dev-insecure-change-me"
)
app.config["SECRET_KEY"] = _secret
app.secret_key = _secret  # explicit assignment for older extension lookups
csrf = CSRFProtect(app)
APP_START_TS = time.time()

# Basic SQLite configuration (reuses pattern from appy.py but simplified)
basedir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(basedir, "instance")
os.makedirs(instance_dir, exist_ok=True)
db_path = os.path.join(instance_dir, "volunteers.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# Secure cookie/session defaults
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

    SUPPORTED_LOCALES = ["fr", "bg", "en"]

    def _detect_country_code() -> str | None:
        """Best-effort country detection from common proxy/CDN headers.

        Returns two-letter ISO country code if available (e.g. 'FR', 'BG').
        This avoids external lookups and works behind providers like Cloudflare
        (CF-IPCountry) or AppEngine (X-AppEngine-Country). Returns None if
        nothing reliable is present.
        """
        # Cloudflare
        cc = (request.headers.get("CF-IPCountry") or "").strip().upper()
        if cc and cc not in {"XX", "T1"}:  # 'XX'/'T1' are unknown/tor
            return cc
        # AppEngine / generic reverse proxies
        for hdr in ("X-AppEngine-Country", "X-Country-Code", "X-Geo-Country"):
            cc = (request.headers.get(hdr) or "").strip().upper()
            if cc:
                return cc
        return None

    def _select_locale() -> str:
        # 1) Explicit cookie wins
        lang_cookie = (request.cookies.get("language") or "").strip().lower()
        if lang_cookie in SUPPORTED_LOCALES:
            return lang_cookie

        # 2) Geo-IP via headers: FR->fr, BG->bg, others->en
        cc = _detect_country_code()
        if cc == "FR":
            return "fr"
        if cc == "BG":
            return "bg"
        if cc:  # any other detected country
            return "en"

        # 3) Accept-Language as a graceful fallback
        best = request.accept_languages.best_match(SUPPORTED_LOCALES)
        if best:
            return best

        # 4) Final fallback to configured default (French)
        return app.config.get("BABEL_DEFAULT_LOCALE", "fr")

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
    @app.context_processor
    def _inject_gettext():
        return dict(_=_)

    # Expose get_locale-like helper for templates expecting it
    @app.context_processor
    def _inject_get_locale():
        return dict(get_locale=_select_locale)

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
                );
                """
            )
        )
        # Triggers to sync FTS with base table
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
        count = db.session.execute(
            text("SELECT count(*) FROM help_requests_fts")
        ).scalar()
        if count is None or int(count) == 0:
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
                func.lower(HelpRequest.title).like(patt)
                | func.lower(HelpRequest.description).like(patt)
                | func.lower(HelpRequest.message).like(patt)
                | func.lower(HelpRequest.city).like(patt)
                | func.lower(HelpRequest.region).like(patt)
                | func.lower(HelpRequest.name).like(patt)
            )
            if privileged:
                cond = cond | func.lower(HelpRequest.email).like(patt)
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
_rate_lock = Lock()
_rate_hits: dict[str, deque] = defaultdict(deque)  # IP -> deque[timestamps]


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
            user = User.query.filter(func.lower(User.email) == email.lower()).first()
        elif username and "@" in username:
            user = User.query.filter(func.lower(User.email) == username.lower()).first()
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
            query = query.filter(func.lower(HelpRequest.status).in_(statuses))

    city = request.args.get("city")
    if city:
        query = query.filter(func.lower(HelpRequest.city) == city.lower())

    category = request.args.get("category")
    if category:
        query = query.filter(func.lower(HelpRequest.title) == category.lower())

    search = request.args.get("q") or request.args.get("search")
    # Apply FTS5 / fallback search only when provided
    query, rank_expr = _apply_text_search(query, search, privileged)

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
    latest_ts = db.session.query(func.max(HelpRequest.updated_at)).scalar() or "0"
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
        total = db.session.query(func.count(HelpRequest.id)).scalar() or 0
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
        try:
            from models import AdminRole as _AdminRole
        except Exception:
            _AdminRole = None
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
                    "message": "Residency paperwork assistance",
                    "status": "pending",
                    "priority": PriorityEnum.normal,
                },
                {
                    "name": "Jean P.",
                    "email": "jean@example.com",
                    "title": "Medical",
                    "city": "Lyon",
                    "description": "Looking for transport to clinic.",
                    "message": "Transport to clinic",
                    "status": "in_progress",
                    "priority": PriorityEnum.low,
                },
                {
                    "name": "Amina K.",
                    "email": "amina@example.com",
                    "title": "Social",
                    "city": "Marseille",
                    "description": "Seeking community meetup information.",
                    "message": "Community meetup info",
                    "status": "completed",
                    "priority": PriorityEnum.normal,
                },
            ]
            for s in samples:
                db.session.add(HelpRequest(**s))
            db.session.commit()


with app.app_context():
    db.create_all()
    _ensure_sqlite_fts()
    _seed_if_empty()
    # Register blueprint after app + db initialized
    try:
        app.register_blueprint(microsoft_bp)
    except Exception:
        pass  # Fail-open if blueprint not available

# ----------------------------
# Public site routes (UX)
# ----------------------------


@app.get("/")
def index():
    return render_template("home_new.html")


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


@app.get("/set_language")
def set_language():
    lang = (request.args.get("language") or "bg").strip().lower()
    nxt = request.args.get("next") or url_for("index")
    resp = make_response(redirect(nxt))
    # 180 days
    resp.set_cookie("language", lang, max_age=60 * 60 * 24 * 180, samesite="Lax")
    return resp


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
        security_logger.info(
            f"admin_login_attempt start username={username!r} ip={remote_ip} password_len={len(password)}"
        )
        if username:
            try:
                admin = AdminUser.query.filter(
                    func.lower(AdminUser.username) == username.lower()
                ).first()
            except Exception:
                admin = None
            if admin is None:
                try:
                    user = User.query.filter(
                        func.lower(User.username) == username.lower()
                    ).first()
                except Exception:
                    user = None

        # If AdminUser exists, apply lockout policy
        if admin is not None:
            now = datetime.utcnow()
            if admin.locked_until and now < admin.locked_until:
                minutes = max(1, int((admin.locked_until - now).total_seconds() // 60))
                flash(
                    f"Акаунтът е временно заключен. Опитайте след ~{minutes} мин.",
                    "error",
                )
                security_logger.warning(
                    f"admin_login_locked username={username!r} ip={remote_ip} locked_until={admin.locked_until}"
                )
                return render_template("admin_login.html"), 423

            if not admin.check_password(password):
                try:
                    admin.failed_login_attempts = (admin.failed_login_attempts or 0) + 1
                    if admin.failed_login_attempts >= 5:
                        admin.locked_until = now + timedelta(minutes=10)
                        admin.failed_login_attempts = 0
                    db.session.add(admin)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                flash("Невалидни данни за вход.", "error")
                security_logger.warning(
                    f"admin_login_failure username={username!r} ip={remote_ip} reason=bad_password attempts={admin.failed_login_attempts}"
                )
                return render_template("admin_login.html"), 401

            try:
                admin.failed_login_attempts = 0
                admin.locked_until = None
                db.session.add(admin)
                db.session.commit()
            except Exception:
                db.session.rollback()
            session["admin_logged_in"] = True
            flash("Успешен вход.", "success")
            security_logger.info(
                f"admin_login_success username={username!r} ip={remote_ip} model=AdminUser"
            )
            return redirect(url_for("admin_dashboard"))

        # Legacy: fallback to User without lockout
        if not user or not user.check_password(password):
            flash("Невалидни данни за вход.", "error")
            security_logger.warning(
                f"admin_login_failure username={username!r} ip={remote_ip} reason=legacy_user_bad_password"
            )
            return render_template("admin_login.html"), 401
        session["admin_logged_in"] = True
        flash("Успешен вход.", "success")
        security_logger.info(
            f"admin_login_success username={username!r} ip={remote_ip} model=User legacy_break_glass=True"
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
                func.lower(User.email) == identifier.lower()
            ).first()
        else:
            user = User.query.filter(
                func.lower(User.username) == identifier.lower()
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
                func.lower(HelpRequest.status) == "pending"
            ).count()
        ),
        "in_progress": _safe_count(
            lambda: HelpRequest.query.filter(
                func.lower(HelpRequest.status) == "in_progress"
            ).count()
        ),
        "completed_requests": _safe_count(
            lambda: HelpRequest.query.filter(
                func.lower(HelpRequest.status) == "completed"
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


if __name__ == "__main__":
    app.run(debug=True)
