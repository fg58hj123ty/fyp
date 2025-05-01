
import librosa
from transformers import Wav2Vec2FeatureExtractor, WavLMForXVector
import torch
import numpy as np
import soundfile as sf
from scipy.io import wavfile
import io, os
from scipy import signal
import tempfile
import subprocess

class VoiceProcessor:
    
    def __init__(self, model_path="models"):
        """
        Initialize with local model path
        """
        try:

            
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            print(f"Using device: {self.device}")
            
            # Load feature extractor from local path
            feature_extractor_path = os.path.join(model_path, 'feature_extractor')
            if not os.path.exists(feature_extractor_path):
                raise ValueError(f"Feature extractor not found at {feature_extractor_path}")
            self.feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(feature_extractor_path)
            
            # Load model from local path
            model_path = os.path.join(model_path, 'wavlm')
            if not os.path.exists(model_path):
                raise ValueError(f"Model not found at {model_path}")
            self.model = WavLMForXVector.from_pretrained(model_path).to(self.device)
            
            self.threshold = 0.86

            
        except Exception as e:
            print(f"Error initializing VoiceProcessor: {str(e)}")
            raise

        
    def standardize_audio(self, audio_path):
        """Standardize audio using wave and scipy"""
        try:
            audio_array, _ = librosa.load(audio_path, sr=16000, mono=True)

            if len(audio_array) == 0:
                raise ValueError("audio data is empty！")

            max_val = np.max(np.abs(audio_array))
            if max_val > 0:
                audio_array /= max_val

            audio_array = audio_array.astype(np.float32)

            return audio_array, 16000

        except Exception as e:
            print(f"Detailed error in standardize_audio: {str(e)}")
            print(f"File path: {audio_path}")
            print(f"File exists: {os.path.exists(audio_path)}")
            if os.path.exists(audio_path):
                print(f"File size: {os.path.getsize(audio_path)} bytes")
            raise Exception(f"Audio standardization failed: {str(e)}")
        
    def process_audio(self, audio_file):
        """Process audio file and extract embeddings"""
        try:
            if isinstance(audio_file, str):
                # If audio_file is a path
                print(f"Processing file path: {audio_file}")
                audio_array, sample_rate = self.standardize_audio(audio_file)
            else:
                # If audio_file is a file object
                print("Processing file object")
                audio_data = audio_file.read()
                with io.BytesIO(audio_data) as buf:
                    rate, data = wavfile.read(buf)
                    # Convert to mono if stereo
                    if len(data.shape) > 1:
                        data = np.mean(data, axis=1)
                    # Convert to float32 and normalize
                    data = data.astype(np.float32)
                    data = data / np.max(np.abs(data))
                    # Resample if necessary
                    if rate != 16000:
                        duration = len(data) / rate
                        target_length = int(duration * 16000)
                        data = signal.resample(data, target_length)
                    audio_array = data
                    sample_rate = 16000

            print(f"Audio array shape: {audio_array.shape}")
            print(f"Sample rate: {sample_rate}")
            print(f"Audio array min: {np.min(audio_array)}, max: {np.max(audio_array)}")
                
                

            # Extract features
            inputs = self.feature_extractor(
                audio_array, 
                sampling_rate=sample_rate, 
                return_tensors="pt"
            ).to(self.device)

            # Get embeddings
            with torch.no_grad():
                embeddings = self.model(**inputs).embeddings
                embeddings = torch.nn.functional.normalize(embeddings, dim=-1).cpu()

            return embeddings[0].numpy()

        except Exception as e:
            raise Exception(f"Error processing audio: {str(e)}")
    
    
    
    def compare_embeddings(self, embedding1, embedding2):
        """Compare two embeddings using cosine similarity"""
        embedding1 = torch.tensor(embedding1)
        embedding2 = torch.tensor(embedding2)
        
        cosine_sim = torch.nn.CosineSimilarity(dim=-1)
        similarity = cosine_sim(embedding1, embedding2)
        
        return float(similarity), float(similarity) >= self.threshold
    
