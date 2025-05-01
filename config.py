import os
from utils.path_manager import PathManager





class Config:

    paths = PathManager.get_paths()

    

    SECRET_KEY='6e896dc94473524159c7ecf4afe3817c'
    REGISTRATION_CODE='2024FYP'
    SQLALCHEMY_DATABASE_URI='sqlite:///site.db'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    MIN_RECORD_DURATION = 5

    # BASE_DIR = os.path.abspath(os.path.dirname(__file__)) # Base directory of the project

    # APP_FOLDER = os.path.join(BASE_DIR, 'web_app')
    # STATIC_FOLDER = os.path.join(APP_FOLDER, 'static')
    # VOICE_SAMPLES_ROOT = os.path.join(STATIC_FOLDER, 'voice_samples')  #  directory for voice samples

    # MODEL_FOLDER = os.path.join(BASE_DIR, 'models')
    # FEATURE_EXTRACTION_PATH = os.path.join(MODEL_FOLDER, 'feature_extractor')
    # WAVLM_MODEL_PATH = os.path.join(MODEL_FOLDER, 'wavlm')

    # Use PathManager for consistent paths
    BASE_DIR = paths['root']
    APP_FOLDER = os.path.join(BASE_DIR, 'web_app')
    STATIC_FOLDER = os.path.join(APP_FOLDER, 'static')
    VOICE_SAMPLES_ROOT = paths['voice_samples']
    MODEL_FOLDER = paths['models']
    FEATURE_EXTRACTION_PATH = paths['feature_extractor']
    WAVLM_MODEL_PATH = paths['wavlm']