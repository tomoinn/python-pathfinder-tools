from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FormField, FieldList
from wtforms.validators import DataRequired


class SessionForm(FlaskForm):
    event = StringField('Event')
    event_code = StringField('Event Code')
    date = StringField('Date')
    gm_number = StringField('GM Society #')


class PlayerForm(FlaskForm):
    player_name = StringField('Player Name')
    character_name = StringField('Character Name')


class LoginForm(FlaskForm):
    session = FormField(SessionForm)
    players = FieldList(FormField(PlayerForm), min_entries=6, max_entries=6)
