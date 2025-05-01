
from flask import render_template, url_for, flash, redirect, request, Blueprint
from web_app import db, bcrypt
from web_app.models.models import User
from web_app.users.forms import RegistrationForm, LoginForm, UpdateAccountForm, RequestResetForm, ResetPasswordForm, ChangePasswordForm
from flask_login import login_user, current_user, logout_user, login_required
from web_app.users.utils import save_picture, send_reset_email



users = Blueprint('users', __name__)

@users.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    form = RegistrationForm()

    if form.validate_on_submit():
        
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username = form.username.data,
                    email = form.email.data,
                    password = hashed_password)
        
        db.session.add(user)
        db.session.commit()

        # Log the first admin activity
        user.log_activity(
            activity_type='account_creation',
            status='success',
            details='User account created'
        )

        flash('Your account has been created! You are now able to log in.', 'success')

        return redirect(url_for('users.login'))
    
    return render_template('users/register.html',
                            title = 'Register',
                            form = form)

@users.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email = form.email.data).first()

        if user and bcrypt.check_password_hash(user.password,
                                               form.password.data):
            login_user(user, remember=form.remember.data)
            user.log_activity(
            activity_type='login',
            status='success',
            details='logged in'
        )
            next_page = request.args.get('next')
            if user.is_admin:
                return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
            else:

                return redirect(next_page) if next_page else redirect(url_for('main.home'))
        
        else:
            flash('Login unsuccessful. Please check email and password', 
                  'danger')
            
    return render_template('users/login.html',
                            title = 'Log in',
                              form = form)

@users.route("/logout")
def logout():
    if current_user.is_authenticated:
        # Log the activity before logging out
        current_user.log_activity(
            'logout',
            'success',
            'logged out'
        )
        logout_user()
    return redirect(url_for('main.home'))


@users.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
    
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file

        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.alias = form.alias.data
        current_user.access_code = form.access_code.data
        current_user.log_activity(
            activity_type='account_update',
            status='success',
            details='Account updated'
        )
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('users.account'))
    
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.alias.data = current_user.alias
        form.access_code.data = current_user.access_code
    
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)

    return render_template('users/account.html',
                         title='Account',
                         image_file=image_file,
                         form=form)


@users.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email = form.email.data).first()
        send_reset_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect(url_for('users.login'))
    
    return render_template('users/reset_request.html', 
                           title='Reset Password', 
                           form=form)


@users.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    user = User.verify_reset_token(token)

    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('users.reset_request'))
    

    form = ResetPasswordForm()

    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Your password has been updated! Please log in with new password', 'success')
        return redirect(url_for('users.login'))
    
    return render_template('users/reset_token.html', 
                           title='Reset Password', 
                           form=form)


@users.route("/change_password", methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        # Verify current password
        if bcrypt.check_password_hash(current_user.password, form.current_password.data):
            # Update password
            hashed_password = bcrypt.generate_password_hash(form.new_password.data).decode('utf-8')
            current_user.password = hashed_password
            db.session.commit()
            
            # Log password change
            current_user.log_activity(
                activity_type='password_change',
                status='success',
                details='Password successfully changed'
            )
            
            flash('Your password has been updated!', 'success')
            return redirect(url_for('users.account'))
        else:
            flash('Current password is incorrect', 'danger')
    
    return render_template('users/change_password.html', 
                         title='Change Password',
                         form=form)