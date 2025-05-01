import os, secrets

from PIL import Image
from flask import url_for, current_app
from flask_mail import Message


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.root_path, 'static/profile_pics', picture_fn)

    # Open the image
    i = Image.open(form_picture)
    # Get original aspect ratio
    width, height = i.size
    ratio = width / height
    
    # Set desired max width
    max_width = 250
    # Calculate height maintaining aspect ratio
    new_height = int(max_width / ratio)
    
    output_size = (max_width, new_height)
    i.thumbnail(output_size, Image.LANCZOS)
    i.save(picture_path)

    return picture_fn

def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender = 'noreply@demo.com',
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
    {url_for('users.reset_token',token = token, _external = True)}
    If you did not make this request then simply ignore this email and no change would be made.
    '''

    # sending email 
    print(msg)