from flask import Flask, redirect, url_for, render_template, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
import os

from database_setup import User, engine
from sqlalchemy.orm import scoped_session, sessionmaker
from app.forms import LoginForm, RegistrationForm

template_dir = os.path.abspath('./app/templates')
app = Flask(__name__, template_folder=template_dir)

app.secret_key = 'tajny_klucz'  # Ustaw tajny klucz

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

db_session = scoped_session(sessionmaker(bind=engine))

@login_manager.user_loader
def load_user(user_id):
    return db_session.query(User).get(int(user_id))

@app.route('/')
def index():
    return 'Witaj w aplikacji!'

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db_session.query(User).filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html', form=form)


db_session = scoped_session(sessionmaker(bind=engine))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))  # Przekieruj zalogowanych użytkowników

    form = RegistrationForm()
    if form.validate_on_submit():
        # Sprawdzanie, czy użytkownik z takim emailem już istnieje
        existing_user = db_session.query(User).filter_by(email=form.email.data).first()
        if existing_user is None:
            hashed_password = generate_password_hash(form.password.data, method='sha256')
            new_user = User(
                name=form.name.data,
                surname=form.surname.data,
                email=form.email.data,
                password=hashed_password,
                role='czytelnik'  # Zakładając, że każdy nowy użytkownik ma rolę 'czytelnik'
            )
            db_session.add(new_user)
            db_session.commit()
            flash('Konto zostało pomyślnie utworzone.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Email już istnieje.', 'danger')

    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Zostałeś wylogowany.', 'success')
    return redirect(url_for('login'))


# To powinno być na samym końcu pliku
if __name__ == '__main__':
    app.run(debug=True)
