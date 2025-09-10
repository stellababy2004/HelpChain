from .models import db, Volunteer, HelpRequest, SuccessStory, User
from .forms import VolunteerForm
from .appy import app  # Ако app е в appy.py
from flask import render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

login_manager = LoginManager()
login_manager.init_app(app)

@app.route('/stories')
def stories():
    stories = SuccessStory.query.order_by(SuccessStory.timestamp.desc()).all()
    return render_template('stories.html', stories=stories)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    type_filter = request.args.get('type', '')
    location_filter = request.args.get('location', '')
    
    # Филтриране на заявки
    requests_query = HelpRequest.query
    if query:
        requests_query = requests_query.filter(HelpRequest.message.contains(query))
    if type_filter:
        requests_query = requests_query.filter(HelpRequest.help_type == type_filter)
    if location_filter:
        requests_query = requests_query.filter(HelpRequest.location.contains(location_filter))
    requests = requests_query.all()
    
    # Филтриране на доброволци
    volunteers_query = Volunteer.query
    if query:
        volunteers_query = volunteers_query.filter(Volunteer.name.contains(query))
    if location_filter:
        volunteers_query = volunteers_query.filter(Volunteer.location.contains(location_filter))
    volunteers = volunteers_query.all()
    
    return render_template('search.html', requests=requests, volunteers=volunteers, query=query, type=type_filter, location=location_filter)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        hashed_password = generate_password_hash(password, method='sha256')
        new_user = User(username=username, email=email, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрацията е успешна!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Грешни данни', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
