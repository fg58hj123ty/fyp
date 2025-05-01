import sounddevice as sd
from scipy.io.wavfile import write

duration = 5  # 秒
samplerate = 44100
device = "pulse"  # 或 "spdif" 或 "pulse"

try:
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, device=device)
    print(f"Recording with {device}...")
    sd.wait()
    write("test_recording.wav", samplerate, recording)
    print("Saved to test_recording.wav")
except Exception as e:
    print(f"Error: {str(e)}")