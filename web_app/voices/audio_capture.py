import pyaudio
import numpy as np
from threading import Event
import time
from web_app import voice_processor



class AudioCapture:
    def __init__(self, sample_rate=16000, channels=1, chunk_size=1024, record_seconds=5):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.record_seconds = record_seconds
        self.format = pyaudio.paFloat32
        self.audio = pyaudio.PyAudio()
        self.frames = []
        self._stop_recording = Event()

    def start_recording(self):
        """Start recording audio from microphone"""
        try:
            self.frames = []
            self._stop_recording.clear()
            
            stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )

            print("Started recording...")
            
            for _ in range(0, int(self.sample_rate / self.chunk_size * self.record_seconds)):
                if self._stop_recording.is_set():
                    break
                data = stream.read(self.chunk_size)
                self.frames.append(np.frombuffer(data, dtype=np.float32))

            stream.stop_stream()
            stream.close()
            print("Recording finished.")
            
            return np.concatenate(self.frames) if self.frames else None

        except Exception as e:
            print(f"Error recording audio: {str(e)}")
            return None

    def play_audio(self, audio_data=None):
        """Play recorded audio"""
        if audio_data is None:
            audio_data = self.get_audio_data()
            
        if audio_data is None:
            print("No audio data to play")
            return

        try:
            # Create output stream
            stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                output=True
            )

            print("Playing audio...")
            
            # Play audio in chunks
            chunk_size = self.chunk_size * 4  # Larger chunks for smoother playback
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                stream.write(chunk.tobytes())

            stream.stop_stream()
            stream.close()
            print("Playback finished.")

        except Exception as e:
            print(f"Error playing audio: {str(e)}")

    def record_with_preview(self):
        """Record audio and offer preview with options"""
        while True:
            # Record audio
            audio_data = self.start_recording()
            if audio_data is None:
                print("Recording failed")
                return None

            # Ask user what to do
            while True:
                choice = input("\nOptions:\n1. Play recording\n2. Keep recording\n3. Record again\nChoice (1-3): ")
                
                if choice == '1':
                    self.play_audio(audio_data)
                elif choice == '2':
                    embedding = voice_processor.process_audio(audio_data)
                    print(embedding)
                elif choice == '3':
                    print("\nStarting new recording...")
                    break
                else:
                    print("Invalid choice. Please try again.")

    def stop_recording(self):
        """Stop recording"""
        self._stop_recording.set()

    def get_audio_data(self):
        """Get the recorded audio data as numpy array"""
        if not self.frames:
            return None
        return np.concatenate(self.frames)

    def __del__(self):
        """Cleanup"""
        self.audio.terminate()

    def print_devices(self):
        audio = pyaudio.PyAudio()
        # List available input devices
        info = audio.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        for i in range(0, numdevices):
            if (audio.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                print("Input Device id ", i, " - ", audio.get_device_info_by_host_api_device_index(0, i).get('name'))

        # Get the default input device index
        default_input = audio.get_default_input_device_info()['index']
        print(f"Default input device index: {default_input}")

# Example usage:
if __name__ == "__main__":
    audio_capture = AudioCapture(record_seconds=3)  # 3 seconds recording
    audio_capture.print_devices()
    
    
    
    print("Testing audio capture with preview...")
    audio_data = audio_capture.record_with_preview()
    
    if audio_data is not None:
        print(f"Final recording length: {len(audio_data)} samples")