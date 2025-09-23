from __future__ import annotations
import os
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__, template_folder="templates")
app.secret_key = 'your_secret_key'

@app.route("/", methods=['GET', 'POST'])
def index():
    stats = {"total": 12, "open": 3, "closed": 9}
    recent = [
        {"id": 1, "title": "Помощ с лекарства", "status": "Активна", "created_at": "2025-09-22"},
        {"id": 2, "title": "Транспорт до болница", "status": "Решена", "created_at": "2025-09-21"},
    ]
    user = {"is_authenticated": False, "username": ""}
    return render_template("index.html", stats=stats, recent=recent, user=user)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'POST':
        flash('Профилът е обновен успешно!')
        return redirect(url_for('profile'))
    user = {"name": "Иван", "email": "ivan@abv.bg", "profile_pic": None}
    return render_template('profile.html', user=user)

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        flash('Паролата е сменена успешно!')
        return redirect(url_for('change_password'))
    return render_template('change_password.html')

@app.route('/upload_photo', methods=['GET', 'POST'])
def upload_photo():
    if request.method == 'POST':
        flash('Снимката е качена успешно!')
        return redirect(url_for('upload_photo'))
    return render_template('upload_photo.html')

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        flash('Благодарим за обратната връзка!')
        return redirect(url_for('feedback'))
    return render_template('feedback.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        # Тук добави логика за проверка на потребител
        flash('Успешен вход!')
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        # Тук добави логика за регистрация
        flash('Регистрацията е успешна!')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    # Тук можеш да добавиш логика за изход от профила
    flash('Излязохте успешно от профила!')
    return redirect(url_for('login'))

@app.route('/success_story', methods=['GET', 'POST'])
def success_story():
    if request.method == 'POST':
        flash('Историята е изпратена успешно!')
        return redirect(url_for('success_story'))
    return render_template('success_story.html')

if __name__ == "__main__":
    app.run(debug=True)