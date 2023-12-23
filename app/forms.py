from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, ValidationError, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional


# Walidator, który sprawdza, czy dane pole składa się wyłącznie z wielkich liter
def uppercase_check(form, field):
    # Sprawdź, czy pierwsza litera każdego słowa jest wielką literą
    if field.data and not all(word[0].isupper() for word in field.data.split()):
        raise ValidationError('Każde słowo musi zaczynać się od wielkiej litery.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Hasło', validators=[DataRequired()])
    submit = SubmitField('Zaloguj')


class RegistrationForm(FlaskForm):
    name = StringField('Imię', validators=[DataRequired(), Length(min=2, max=50), uppercase_check])
    surname = StringField('Nazwisko', validators=[DataRequired(), Length(min=2, max=50), uppercase_check])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Hasło', validators=[
        DataRequired(),
        Length(min=6, message='Hasło musi mieć przynajmniej 6 znaków.')
    ])
    submit = SubmitField('Zarejestruj')


class EditUserForm(FlaskForm):
    name = StringField('Imię', validators=[DataRequired()])
    surname = StringField('Nazwisko', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    wants_notifications = BooleanField('Chcę otrzymywać powiadomienia', default=True)
    change_password = BooleanField('Zmień hasło')
    password = PasswordField('Nowe hasło', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Potwierdź nowe hasło', validators=[EqualTo('password', message='Hasła muszą się zgadzać')])
    submit = SubmitField('Zaktualizuj')


class EditUserFormByStaff(FlaskForm):
    name = StringField('Imię', validators=[DataRequired()])
    surname = StringField('Nazwisko', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Zaktualizuj')


class EditUserEmployee(FlaskForm):
    name = StringField('Imię', validators=[DataRequired()])
    surname = StringField('Nazwisko', validators=[DataRequired()])
    change_password = BooleanField('Zmień hasło')
    password = PasswordField('Nowe hasło', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Potwierdź nowe hasło',validators=[EqualTo('password', message='Hasła muszą się zgadzać')])
    submit = SubmitField('Zaktualizuj')

class SendNotificationForm(FlaskForm):
    user_id = SelectField('Użytkownik', coerce=int, validators=[DataRequired()])
    content = TextAreaField('Treść powiadomienia', validators=[DataRequired()])
    submit = SubmitField('Wyślij powiadomienie')
