import os, secrets
from datetime import datetime
from flask import current_app
import librosa
import soundfile as sf
from werkzeug.utils import secure_filename
import numpy as np
from web_app import voice_processor
import tempfile
import subprocess
class VoiceProcessingError(Exception):
    pass

def convert_to_standard_format(input_path, output_path):
    try:
        # use ffmpeg repair
        cmd = [
            'ffmpeg',
            '-y',                # 覆盖输出文件
            '-i', input_path,    # 输入文件
            '-acodec', 'pcm_s16le',  # 16-bit PCM
            '-ar', '16000',      # 16kHz 采样率
            '-ac', '1',          # 单声道
            '-f', 'wav',         # 强制 WAV 格式
            output_path
        ]
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        print(f"conversion failed: {e.stderr.decode()}")
        return False
    
def fix_wav_header(input_path):
    """fix wav file header"""
    try:
        with open(input_path, 'rb') as f:
            data = f.read()
        
        # check wav file header
        if len(data) < 44 or not data.startswith(b'RIFF') or data[8:12] != b'WAVE':
            print("a corrupted wav file header has been detected, attempting to repair it")
            # create a new header
            new_header = b'RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
            audio_data = data[44:]  
            with open(input_path, 'wb') as f:
                f.write(new_header + audio_data)
        return True
    except Exception as e:
        print(f"repair failed: {str(e)}")
        return False
        
def save_voice_sample(file_data, user_id):
    """
    Save voice sample file to filesystem and return file details
    """
    if not file_data:
        raise ValueError("No file provided")

    # print(f"Saving file: {file_data.filename} for user {user_id}")

    try:
        f_ext = ".wav"  # 獲取原始文件擴展名（如 .wav）

        # 生成安全文件名和路径
        filename = secure_filename(file_data.filename)
        relative_path = os.path.join('voice_samples', filename)
        abs_path = os.path.join(current_app.config['STATIC_FOLDER'], relative_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)


        temp_input = os.path.join(current_app.config['STATIC_FOLDER'], f"temp_input_{filename}")
        file_data.save(temp_input)

        temp_output = os.path.join(current_app.config['STATIC_FOLDER'], f"temp_output_{filename}")
        fix_wav_header(temp_input)
        if not convert_to_standard_format(temp_input, temp_output):
            raise ValueError("audio format is not ")

        if not os.path.exists(temp_output):
            raise ValueError("转换后文件未生成")

        os.replace(temp_output, abs_path)

        audio_data, _ = librosa.load(abs_path, sr=16000, mono=True)
        
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data /= max_val
        
        sf.write(abs_path, audio_data, 16000, subtype='PCM_16', format='WAV')
        # ====================================================
        
        # 計算文件大小（字節）
        file_size = os.path.getsize(abs_path)
        

        # Process voice embedding

        try:

            embedding = voice_processor.process_audio(abs_path)

            if embedding is None or not isinstance(embedding, np.ndarray):
                raise ValueError("Failed to generate voice embedding.")
            
            if embedding.shape[0] != 512:
                raise ValueError(f"Invalid embedding size: {embedding.shape[0]}")
        
        except Exception as e:
            print(f"Error processing voice embedding: {str(e)}")
            raise ValueError(f"Failed to process voice embedding: {str(e)}")
        
        print(f"File saved successfully at: {abs_path}")

        return {
            'filename': filename,
            'file_path': relative_path,  
            'file_size': file_size,
            'file_format': f_ext[1:],  # Remove the dot from extension
            'abs_path': abs_path,
            'embedding': embedding
        }

    except Exception as e:
        # Clean up any partially saved file
        try:
            if 'abs_path' in locals() and os.path.exists(abs_path):
                os.remove(abs_path)
        except:
            pass
        
        print(f"Error saving voice sample: {str(e)}")
        raise  # Re-raise the exception after cleanup

def get_file_path(filename):
    """Get the normalized full path for a file in the static directory"""
    if not filename:
        return None
    return os.path.normpath(os.path.join(current_app.root_path, 'static', filename))

def delete_file_if_exists(file_path):
    """Safely delete a file if it exists"""
    if not file_path:
        return False
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception as e:
        print(f"Error deleting file {file_path}: {str(e)}")
    return False

