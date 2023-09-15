from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from wtforms import StringField, PasswordField, TextAreaField, SelectField
from wtforms.validators import DataRequired, EqualTo, Length


# Set your classes here.


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=6, max=25)])
    email = StringField('Email', validators=[DataRequired(), Length(min=6, max=40)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=40)])
    confirm = PasswordField('Repeat Password', [DataRequired(), EqualTo('password',
                                                                        message='Passwords must match')])


class LoginForm(FlaskForm):
    username = StringField('Username', [DataRequired()])
    password = PasswordField('Password', [DataRequired()])


class ForgotForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Length(min=6, max=40)])


class AddAppForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=1, max=100)])
    url = StringField('URL', validators=[DataRequired(), Length(min=1, max=100)])
    image = FileField(validators=[FileRequired()])
    operating_system = SelectField('Operating System', choices=[('Android', 'Android'), ('iOS', 'iOS')])
    alias = StringField('Alias Tag', validators=[DataRequired(), Length(min=1, max=100)])
    unique_tag = StringField('Unique Tag', validators=[DataRequired(), Length(min=1, max=100)])
    description = TextAreaField('Description', validators=[DataRequired(), Length(min=1, max=1000)])
    status = SelectField('Status',
                         choices=[('Active', 'Active'), ('Inactive', 'Inactive'), ('Suspended', 'Suspended')])

