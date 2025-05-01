import os
from pathlib import Path

class PathManager:
    @staticmethod
    def get_project_root():
        """Get the root directory of the project"""
        # Start from the current file's directory
        current_path = Path(os.path.abspath(__file__))
        
        # Go up until we find the project root (where web_app directory exists)
        while current_path.parent != current_path:  # Stop at root to prevent infinite loop
            # Check if this is the project root (contains web_app directory)
            if os.path.exists(os.path.join(str(current_path), 'web_app')):
                return str(current_path)
            current_path = current_path.parent
            
        # If we couldn't find the project root, raise an error
        raise Exception("Could not find project root directory")

    @staticmethod
    def ensure_directories():
        """Ensure all necessary directories exist"""
        root_dir = PathManager.get_project_root()
        
        directories = {
            'models': os.path.join(root_dir, 'models'),
            'feature_extractor': os.path.join(root_dir, 'models', 'feature_extractor'),
            'wavlm': os.path.join(root_dir, 'models', 'wavlm'),
            'voice_samples': os.path.join(root_dir, 'web_app', 'static', 'voice_samples'),
            'recordings': os.path.join(root_dir, 'door_system', 'recordings')
        }

        for directory in directories.values():
            os.makedirs(directory, exist_ok=True)

        return directories

    @staticmethod
    def get_paths():
        """Get all important paths"""
        root_dir = PathManager.get_project_root()
        return {
            'root': root_dir,
            'models': os.path.join(root_dir, 'models'),
            'feature_extractor': os.path.join(root_dir, 'models', 'feature_extractor'),
            'wavlm': os.path.join(root_dir, 'models', 'wavlm'),
            'voice_samples': os.path.join(root_dir, 'web_app', 'static', 'voice_samples'),
            'recordings': os.path.join(root_dir, 'door_system', 'recordings')
        }

    @staticmethod
    def check_models_exist():
        """Check if models are already downloaded"""
        paths = PathManager.get_paths()
        
        # Required model files to check
        required_files = {
            'feature_extractor': ['preprocessor_config.json'],
            'wavlm': ['config.json', 'model.safetensors']  
        }
        
        # Check feature extractor files
        for file in required_files['feature_extractor']:
            file_path = os.path.join(paths['feature_extractor'], file)
            if not os.path.exists(file_path):
                print(f"Missing feature extractor file: {file}")
                print(f"Expected path: {file_path}")
                return False
                
        # Check WavLM model files
        for file in required_files['wavlm']:
            file_path = os.path.join(paths['wavlm'], file)
            if not os.path.exists(file_path):
                print(f"Missing WavLM model file: {file}")
                print(f"Expected path: {file_path}")
                return False
        
        print("All model files exist!")
        return True

    @staticmethod
    def print_paths():
        """Print all important paths for debugging"""
        paths = PathManager.get_paths()
        print("\nCurrent Paths Configuration:")
        for key, path in paths.items():
            exists = os.path.exists(path)
            print(f"{key}: {path} {'[EXISTS]' if exists else '[MISSING]'}")