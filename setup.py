

from utils.path_manager import PathManager
from download_models import download_models
import os

def setup_application():
    """Setup the application for first use"""
    try:
        # Ensure all directories exist
        print("Creating necessary directories...")
        PathManager.ensure_directories()
        
        # Download models if they don't exist
        print("Checking and downloading models...")
        download_models()
        
        print("Setup completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during setup: {str(e)}")
        return False

if __name__ == "__main__":
    setup_application()