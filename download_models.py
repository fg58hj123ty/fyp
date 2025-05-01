from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector
from utils.path_manager import PathManager
import os

def download_models():
    """Download and save models locally"""
    # Ensure directories exist
    paths = PathManager.ensure_directories()
    
    # Check if models already exist
    if PathManager.check_models_exist():
        print("Models already exist. Skipping download.")
        return
    
    print("Downloading WavLM models...")
    
    try:
        # Download feature extractor
        print("\nDownloading feature extractor...")
        feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained('microsoft/wavlm-base-plus-sv')
        feature_extractor.save_pretrained(paths['feature_extractor'])
        print("Feature extractor saved successfully!")
        
        # Download model
        print("\nDownloading WavLM model...")
        model = WavLMForXVector.from_pretrained('microsoft/wavlm-base-plus-sv')
        model.save_pretrained(paths['wavlm'])
        print("WavLM model saved successfully!")
        
        # Verify download
        if PathManager.check_models_exist():
            print("\nAll models downloaded and verified successfully!")
        else:
            print("\nWarning: Some model files may be missing!")
        
        # Print final paths for verification
        PathManager.print_paths()
        
    except Exception as e:
        print(f"Error downloading models: {str(e)}")
        raise

if __name__ == "__main__":
    download_models()