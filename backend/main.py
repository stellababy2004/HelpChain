from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    Form,
    Response,
)
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt
from typing import Dict, Optional
import os
import datetime
from fastapi import BackgroundTasks
from dotenv import load_dotenv

# Зареждаме .env преди да четем променливите
load_dotenv(".env")

SECRET = os.environ.get("HELPCHAIN_SECRET", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
templates = Jinja2Templates(directory="templates")

app = FastAPI(title="HelpChain")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_NAME = os.getenv("FROM_NAME", "HelpChain")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)


class RegisterPayload(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    availability: Optional[str] = None  # напр. "9-17"


# in-memory store for now
_users: Dict[str, Dict] = {}
_signals = []  # <--- добавено
_id_seq = 1


def _hash(pw: str) -> str:
    return pwd_ctx.hash(pw)


def _verify(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw, hashed)


def create_token(username: str, role: str):
    to_encode = {
        "sub": username,
        "role": role,
        "exp": datetime.datetime.utcnow()
        + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(to_encode, SECRET, algorithm=ALGORITHM)


def decode_token(token: str):
    return jwt.decode(token, SECRET, algorithms=[ALGORITHM])


@app.get("/register", response_class=HTMLResponse)
def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register_form")
def register_form(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("volunteer"),
):
    global _id_seq
    if username in _users:
        raise HTTPException(status_code=400, detail="username exists")
    user = {
        "id": _id_seq,
        "username": username,
        "email": email,
        "password": _hash(password),
        "role": role,
    }
    _users[username] = user
    _id_seq += 1
    return RedirectResponse("/", status_code=303)


@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = _users.get(form_data.username)
    if not user or not _verify(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_token(user["username"], user["role"])
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}


@app.post("/register")
async def register(request: Request):
    global _id_seq
    content_type = request.headers.get("content-type", "")
    # JSON API client
    if "application/json" in content_type:
        try:
            data = await request.json()
            payload = RegisterPayload.parse_obj(data)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))
        if payload.username in _users:
            raise HTTPException(status_code=400, detail="username exists")
        user = {
            "id": _id_seq,
            "username": payload.username,
            "email": payload.email,
            "password": _hash(payload.password),
            "role": payload.role,
        }
        _users[payload.username] = user
        _id_seq += 1
        return {"id": user["id"], "email": user["email"]}

    # form submitted from browser
    if (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        form = await request.form()
        data = {k: form.get(k) for k in ("username", "email", "password", "role")}
        try:
            payload = RegisterPayload.parse_obj(data)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))
        if payload.username in _users:
            raise HTTPException(status_code=400, detail="username exists")
        user = {
            "id": _id_seq,
            "username": payload.username,
            "email": payload.email,
            "password": _hash(payload.password),
            "role": payload.role,
        }
        _users[payload.username] = user
        _id_seq += 1
        return RedirectResponse("/", status_code=303)

    raise HTTPException(status_code=415, detail="Unsupported Media Type")


# debug route - виж потребителите в паметта
@app.get("/_debug/users")
def _debug_users():
    return {"users": list(_users.values())}


@app.get("/_debug/users_safe")
def _debug_users_safe():
    # връща само безопасни полета от in-memory _users (без username и password)
    safe = []
    for u in list(_users.values()):
        safe.append({"id": u.get("id"), "email": u.get("email"), "role": u.get("role")})
    return {"users": safe}


@app.get("/_debug/app_users_safe")
def _debug_app_users_safe():
    # връща само безопасни полета от app.state.users (формите)
    safe = []
    for u in getattr(app.state, "users", []):
        safe.append({"email": u.get("email"), "role": u.get("role")})
    return {"users": safe}


# удобен form login (алтернатива на OAuth2PasswordRequestForm) - за бързо тестване
@app.post("/login_form")
def login_form(username: str = Form(...), password: str = Form(...)):
    user = _users.get(username)
    if not user or not _verify(password, user["password"]):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_token(user["username"], user["role"])
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}


# helper deps
def get_current_user(request: Request):  # <- опростено
    auth = None
    header = request.headers.get("authorization")
    if header and header.lower().startswith("bearer "):
        auth = header.split(" ", 1)[1]
    elif request.cookies.get("access_token"):
        auth = request.cookies.get("access_token")
    if not auth:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(auth)
        username = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = _users.get(username)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return user


# simple HTML pages
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "user": None})


@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        "profile.html", {"request": request, "user": user}
    )


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, admin=Depends(get_current_admin)):
    try:
        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "admin": admin,
                "signals": _signals,
                "users": list(_users.values()),
            },
        )
    except Exception as e:
        return PlainTextResponse(
            f"DEBUG admin_page exception: {type(e).__name__}: {e}", status_code=500
        )


@app.on_event("startup")
def startup_data():
    # прост in-memory store за demo (замени с DB)
    app.state.users = []  # всеки user: {"username","email","password","role"}
    app.state.signals = (
        []
    )  # всяка заявка: {"id","title","description","category","status","requester_email"}


# helper: намира потребител
def find_user(username: str):
    for u in app.state.users:
        if u.get("username") == username:
            return u
    return None


# Регистрация (HTML форма)
@app.get("/register")
async def register_get(request: Request):
    return templates.TemplateResponse(
        "register.html", {"request": request, "message": None}
    )


@app.post("/register")
async def register_post(
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("volunteer"),
):
    if find_user(username):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "message": "Потребителското име вече съществува."},
        )
    user = {"username": username, "email": email, "password": password, "role": role}
    app.state.users.append(user)

    # изпращане на welcome имейл ако имаш send_email_sync helper
    try:
        html = templates.env.get_template("emails/registration.html").render(
            username=username
        )
        text = f"Здравей {username}, добре дошли в HelpChain."
        background_tasks.add_task(
            send_email_sync, email, "Добре дошли в HelpChain", html, text
        )
    except Exception:
        pass

    return templates.TemplateResponse(
        "register.html",
        {"request": request, "message": "Регистрацията е успешна. Провери имейла."},
    )


# Вход (login)
@app.get("/login")
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login_post(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    user = find_user(username)
    if not user or user.get("password") != password:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Невалидно потребителско име или парола."},
        )
    # поставяме cookie (демо). За production използвай secure session.
    response = RedirectResponse(url="/profile", status_code=303)
    response.set_cookie("user", username, httponly=True)
    return response


# Профил
@app.get("/profile")
async def profile(request: Request):
    username = request.cookies.get("user")
    if not username:
        return RedirectResponse(url="/login", status_code=303)
    user = find_user(username)
    return templates.TemplateResponse(
        "profile.html", {"request": request, "user": user, "signals": app.state.signals}
    )


# Подаване на заявка (за нуждаещи се)
@app.get("/submit_request")
async def submit_get(request: Request):
    return templates.TemplateResponse(
        "submit_request.html", {"request": request, "message": None}
    )


@app.post("/submit_request")
async def submit_post(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    email: str = Form(None),
):
    # ако email не е подаден, опитваме да вземем от cookie
    requester = request.cookies.get("user")
    requester_email = email
    if requester and not requester_email:
        u = find_user(requester)
        requester_email = u.get("email") if u else None
    signal = {
        "id": len(app.state.signals) + 1,
        "title": title,
        "description": description,
        "category": category,
        "status": "pending",
        "requester_email": requester_email,
    }
    app.state.signals.append(signal)
    return templates.TemplateResponse(
        "submit_request.html", {"request": request, "message": "Заявката е подадена."}
    )


# Регистрация за доброволец (лесен shortcut)
@app.get("/volunteer_register")
async def vol_get(request: Request):
    return templates.TemplateResponse(
        "volunteer_register.html", {"request": request, "message": None}
    )


@app.post("/volunteer_register")
async def vol_post(
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    if find_user(username):
        return templates.TemplateResponse(
            "volunteer_register.html",
            {"request": request, "message": "Потребителското име вече съществува."},
        )
    user = {
        "username": username,
        "email": email,
        "password": password,
        "role": "volunteer",
    }
    app.state.users.append(user)
    try:
        html = templates.env.get_template("emails/registration.html").render(
            username=username
        )
        text = f"Здравей {username}, добре дошли в HelpChain."
        background_tasks.add_task(
            send_email_sync, email, "Добре дошли в HelpChain", html, text
        )
    except Exception:
        pass
    return templates.TemplateResponse(
        "volunteer_register.html",
        {"request": request, "message": "Регистрацията за доброволец е успешна."},
    )


@app.get("/_debug/users_public")
def _debug_users_public():
    safe = []
    # от _users (API регистр.)
    for u in list(_users.values()):
        safe.append(
            {
                "username": u.get("username"),
                "email": u.get("email"),
                "role": u.get("role"),
            }
        )
    # от app.state.users (HTML регистр.)
    for u in getattr(app.state, "users", []):
        safe.append(
            {
                "username": u.get("username"),
                "email": u.get("email"),
                "role": u.get("role"),
            }
        )
    return {"users": safe}


# DEBUG endpoints removed for security (do not keep in production)
# # @app.get("/_debug/decode_token")
# # def _debug_decode_token(...):
# #     ...
#
# # @app.post("/_debug/mint_token")
# # def _debug_mint_token(...):
# #     ...
