from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired


class VolunteerForm(FlaskForm):
    name = StringField("Име", validators=[DataRequired()])
    email = StringField("Имейл", validators=[DataRequired()])
    phone = StringField("Телефон", validators=[DataRequired()])
    skills = TextAreaField("Умения")
    submit = SubmitField("Регистрирай се")
