from flask import Flask, render_template, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "your_secret_key"


@app.route("/login", methods=["GET", "POST"])
def login():
    # Тук може да добавиш логика за вход
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # Тук може да добавиш логика за регистрация
    return render_template("register.html")


@app.route("/volunteer_dashboard")
def volunteer_dashboard():
    # Проверка за доброволец
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return redirect(url_for("login"))
    return render_template("volunteer_dashboard.html")


@app.route("/admin_dashboard")
def admin_dashboard():
    # Проверка за администратор
    if not session.get("admin_logged_in"):
        flash("Само администратори имат достъп.", "danger")
        return redirect(url_for("login"))
    return render_template("admin_dashboard.html")


if __name__ == "__main__":
    app.run(debug=True)
