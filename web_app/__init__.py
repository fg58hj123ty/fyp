from flask import Flask, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from config import Config
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

from web_app.voices.voice_processor import VoiceProcessor

from flask_login import current_user

voice_processor = None

db = SQLAlchemy()
bcrypt = Bcrypt()
csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = 'users.login'
login_manager.login_message_category = 'info'

mail = Mail()

def create_app(config_class=Config, db_reset=False):
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    global voice_processor
    if voice_processor is None and not db_reset:
        try:
            voice_processor = VoiceProcessor(model_path=app.config['MODEL_FOLDER'])
            print("Voice processor initialized successfully!")

        except Exception as e:
            print(f"Error initializing voice processor: {str(e)}")

    from web_app.users.routes import users
    from web_app.main.routes import main
    from web_app.voices.routes import voices
    from web_app.errors.handlers import errors

    app.register_blueprint(users)
    app.register_blueprint(main)
    app.register_blueprint(voices)
    app.register_blueprint(errors)

    @app.context_processor
    def utility_processor():
        def get_username():
            return current_user.username if current_user.is_authenticated else 'Guest'
        return dict(username=get_username())
    
    

    return app

