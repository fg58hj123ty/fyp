from flask import current_app
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Regexp
from flask_login import current_user
from web_app.models.models import User

class RegistrationForm(FlaskForm):
    username = StringField('Username',
                           validators=[DataRequired(), Length(min=2,max=20)])
    
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    
    password = PasswordField('Password',
                             validators=[DataRequired()])
    
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')])
    
    registration_code = StringField('Registration Code',
                                  validators=[DataRequired()])
    
    
    submit = SubmitField('Sign Up')

    def validate_username(self, username):

        user = User.query.filter_by(username = username.data).first()

        if user:
            raise ValidationError('That username is taken. Please choose a different one.')
        
    def validate_email(self, email):

        user = User.query.filter_by(email = email.data).first()

        if user:
            raise ValidationError('That email is taken. Please choose a different one.')

    def validate_registration_code(self, registration_code):
        
        code = current_app.config['REGISTRATION_CODE']
        
        if code != registration_code.data:
            raise ValidationError('Invalid registration code. Please contact system administrator.')    

class LoginForm(FlaskForm):
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    
    password = PasswordField('Password',
                             validators=[DataRequired()])
    
    remember = BooleanField('Remember Me')

    submit = SubmitField('Login')

class UpdateAccountForm(FlaskForm):
    username = StringField('Username',
                           validators=[DataRequired(), 
                                       Length(min=2, max=20)])
    
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    
    alias = StringField('Alias',
                        validators=[
                            Length(min=1, max=20),
                            Regexp(r'^[a-zA-Z\s]*$', 
                                     message="Voice name can only contain letters and spaces")
                        ])
    
    access_code = StringField('Access Code',
                        validators=[
                            Length(min=3, max=3),
                            Regexp(r'^\d{3}$', 
                                     message="Access code must be exactly 3 digits (000-999)")
                        ])
    
    picture = FileField('Update Profile Picture',
                        validators=[FileAllowed(['jpg','png'])])
    
    
    submit = SubmitField('Update')

    def validate_username(self, username):
        if username.data != current_user.username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('That username is taken. Please choose a different one.')
        
    def validate_email(self, email):
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('That email is taken. Please choose a different one.')
            
    def validate_access_code(self, access_code):
        if access_code.data != current_user.access_code:
            user = User.query.filter_by(access_code=access_code.data).first()
            if user:
                raise ValidationError('That access_code is taken. Please choose a different one.')
            
    def validate_alias(self, alias):
        if alias.data:
            # Clean up extra spaces and convert to title case
            cleaned_alias = ' '.join(alias.data.split()).title()
            
            # Check minimum length (if not empty)
            if len(cleaned_alias) < 2:
                raise ValidationError('Alias must be at least 2 letters long')
            
            # Update the field with cleaned version
            alias.data = cleaned_alias
            
class RequestResetForm(FlaskForm):
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    
    submit = SubmitField('Request Password Reset')

    def validate_email(self, email):

        user = User.query.filter_by(email = email.data).first()

        if user is None:
            raise ValidationError('There is no account with that email. You must register first')
        
class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password',
                             validators=[DataRequired()])
    
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')])
    
    submit = SubmitField('Reset Password')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password',
                                   validators=[DataRequired()])
    new_password = PasswordField('New Password',
                                validators=[DataRequired()])
    confirm_password = PasswordField('Confirm New Password',
                                   validators=[DataRequired(),
                                             EqualTo('new_password', message='Passwords must match')])
    submit = SubmitField('Change Password')

    def validate_new_password(self, new_password):
        if self.current_password.data == new_password.data:
            raise ValidationError('New password must be different from current password')
        