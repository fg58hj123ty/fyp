import os
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
import librosa
project_file_dir = os.path.abspath(os.path.dirname(__file__)) 
class AudioRecorder:
    def __init__(self, volume_signal):
        self.duration = 5
        self.target_freq = 16000
        self.frames = []
        self.volume_signal = volume_signal
        self.stream = None  
        self.samplerate = None  

    def callback(self, indata, frames, time, status):
        if status:
            print(status)
        volume_norm = np.linalg.norm(indata)  
        self.volume_signal.emit(volume_norm) 
        self.frames.append(indata.copy())

    def get_supported_samplerate(self, device=None):
        """獲取設備支持的取樣率"""
        common_rates = [44100, 48000, 16000, 22050, 8000]  # 常見取樣率列表
        for rate in common_rates:
            try:
                sd.check_input_settings(device=device, samplerate=rate)
                return rate
            except sd.PortAudioError:
                continue
        raise ValueError("can't find the device rate")

    def start_recording(self):
        try:
            self.samplerate = self.get_supported_samplerate()
            self.frames = []
            self.stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=1,
                callback=self.callback,
                blocksize=1024
            )
            self.stream.start()
            
            print("Recording...")
            sd.sleep(int(self.duration * 1000))

        except Exception as e:
            print(f"Recording error: {str(e)}")
        finally:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            print("Stream closed")

            if self.frames:
                try:
                    recording = np.concatenate(self.frames, axis=0)
                    resampled_recording = librosa.resample(
                        recording.flatten(),  # 轉為一維數組
                        orig_sr=self.samplerate,  # 原始取樣率
                        target_sr=self.target_freq  # 目標取樣率
                    )
                    gain = 5.0
                    amplified_recording = resampled_recording * gain
                    amplified_recording = np.clip(amplified_recording, -1.0, 1.0)
                    output_path = os.path.join(project_file_dir, "recording0.wav")
                    # Ensure the directory exists
                    os.makedirs(project_file_dir, exist_ok=True)
                    write(output_path, self.target_freq, (amplified_recording * 32767).astype(np.int16))
                    print(f"Saved recording to {output_path}")
                except Exception as e:
                    print(f"Saving error: {str(e)}")
            else:
                print("No frames to save")