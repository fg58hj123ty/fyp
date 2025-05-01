

import pyaudio
import numpy as np
from threading import Event
import time, os, sys, io, re
import wave
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import keyboard  

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# from web_app import Config
from web_app import create_app, db
from web_app.models.models import User, UserVoiceProfile
from web_app.voices.voice_processor import VoiceProcessor

class DoorSystem:
    def __init__(self):
        # Create and configure the app
        self.app = create_app()
        self.app_context = self.app.app_context()
        self.app_context.push()  # Push the application context

        # Initialize database session using Flask-SQLAlchemy
        self.db_session = db.session

        self.db_session.configure(expire_on_commit=True)

        # Initialize voice processor
        self.voice_processor = VoiceProcessor(model_path=self.app.config['MODEL_FOLDER'])
        
        # Initialize audio capture
        self.audio_capture = AudioCapture()
        
        # System state
        self.running = True

        self.verification_in_progress = False


    def cleanup(self):
        try:
            if self.app_context:
                self.app_context.pop()  # Remove the application context when done
        except:
            pass
        
    def run(self):
        try:
            keyboard.on_press_key('space', lambda _: self.handle_verification() if not self.verification_in_progress else None)
            keyboard.on_press_key('q', lambda _: self.stop())
            
            while self.running:
                time.sleep(0.1)

        except KeyboardInterrupt:
            print_styled_banner("Shutting down door system...", 'info')
        finally:
            self.cleanup()


    def handle_verification(self):
        if self.verification_in_progress:
            return
        
        self.verification_in_progress = True
        try:
            with self.app.app_context():
                clear_screen()
                print_styled_banner("Voice Verification System", 'info')
                
                # First ask for access code
                while True:
                    try:
                        access_code = input("Please enter your 3-digit Access Code: ").strip()
                        if not re.match(r'^\d{3}$', access_code):
                            print_styled_banner("Invalid code format. Please enter exactly 3 digits.", 'error')
                            continue
                        
                        # Check if access code exists in database
                        user = User.query.filter_by(access_code=access_code).first()
                        if not user:
                            print_styled_banner("Access code not found. Please try again.", 'error')
                            continue
                        
                        break
                    except Exception as e:
                        print_styled_banner(f"Input error: {str(e)}", 'error')
                        continue

                print_styled_banner(f"Access code recognized\nStarting voice verification...", 'info')
                time.sleep(2)
            
            # Record and process audio
            result = self.audio_capture.record_with_preview()
            if result is None or result.get('status') in ['error', 'cancelled']:
                if result and result['status'] == 'cancelled':
                    self.reset_system()
                else:
                    clear_screen()
                    print_styled_banner("Recording failed!", 'error')
                    self.indicate_failure()
                    self.reset_system()
                return

            clear_screen()
            wav_buffer = result['data']
            print_styled_banner("Processing voice...", 'info')
            wav_buffer.seek(0)
            embedding = self.voice_processor.process_audio(wav_buffer)
            if embedding is None:
                clear_screen()
                print_styled_banner("Voice processing failed!", 'error')
                self.indicate_failure()
                self.reset_system()
                return

            # Verify user
            verified_user = self.verify_user(embedding,access_code)
            time.sleep(3)
            if verified_user:
                clear_screen()
                self.grant_access(verified_user)
            else:
                clear_screen()
                self.deny_access()
            
            # Reset system after completion
            self.reset_system()

        except Exception as e:
            clear_screen()
            print_styled_banner(f"Error: {str(e)}", 'error')
            self.indicate_failure()
            self.reset_system()
        finally:
            self.verification_in_progress = False

    def reset_system(self):
        """Reset the system for next attempt"""
        time.sleep(2)  # Give user time to read messages
        clear_screen()
        print_styled_banner(
            "System ready for verification\n"
            "Press 'space' to start verification\n"
            "Press 'q' to quit",
            'info'
        )

    def verify_user(self, new_embedding, access_code):
        with self.app.app_context():  
            try:
                # Clear any existing session
                self.db_session.remove()
                
                # Create a fresh query
                user = User.query.filter_by(access_code=access_code).first()
                
                if not user:
                    return None
                    
                voice_profiles = UserVoiceProfile.query.filter(
                    UserVoiceProfile.user_id == user.id,
                    UserVoiceProfile.is_complete == True,
                    UserVoiceProfile.profile_embedding.isnot(None)
                ).all()
                
                if not voice_profiles:
                    print_styled_banner("No voice profiles found in database, Please complete the profile first", 'error')
                    return None

                clear_screen()
                print_styled_banner(f"Number of voice profiles: {len(voice_profiles)}", 'info')

                for profile in voice_profiles:
                    # Refresh the profile object to get latest data
                    self.db_session.refresh(profile)
                    stored_embedding = profile.get_profile_embedding()
                    
                    if stored_embedding is not None:
                        similarity = self.voice_processor.compare_embeddings(new_embedding, stored_embedding)[0]
                        
                        # Refresh user object to get latest data
                        user = User.query.filter_by(id=profile.user_id).first()
                        self.db_session.refresh(user)
                        
                        print_styled_banner(
                            f"Similarity: {similarity:.4f}\n",
                            'info'
                        )
                        
                        if similarity >= self.voice_processor.threshold:  
                            return user
                
                return None

            except Exception as e:
                print_styled_banner(f"Database error: {str(e)}", 'error')
                return None
            finally:
                # Ensure session is clean for next use
                self.db_session.close()

    def grant_access(self, user):
        print_styled_banner(
            f"Access Granted!\n"
            f"Welcome, {user.alias}\n"
            f"Door unlocked for 5 seconds...",
            'success'
        )
        time.sleep(5)
        print_styled_banner("Door locked", 'info')

    def deny_access(self):
        print_styled_banner(
            "Access Denied!\n"
            "Voice not recognized",
            'error'
        )
        self.indicate_failure()

    def indicate_failure(self):
        print_styled_banner("* * * FAILED * * *", 'error')

    def stop(self):
        print("\nShutting down...")
        self.running = False

    def __del__(self):
        self.cleanup()


class AudioCapture:
    def __init__(self, sample_rate=16000, channels=1, chunk_size=1024, record_seconds=10):
        """Initialize with model-compatible settings
        sample_rate: 16000Hz (required for the voice model)
        channels: 1 for mono (clearer for voice)
        chunk_size: 1024 for better buffer handling
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.record_seconds = record_seconds
        self.format = pyaudio.paInt16  # Using paInt16 for better quality than paFloat32
        self.audio = pyaudio.PyAudio()
        self.frames = []
        self.stream = None

    def start_recording(self):
        """Start recording audio from microphone with quality optimizations"""
        clear_screen()
        print_styled_banner("Available Input Devices:", 'info')
        self.print_devices()
        
        try:
            self.frames = []
            
            if hasattr(self, 'stream'):
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except:
                    pass
            
            # Create a new stream with optimized settings
            stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=None,  # Use default input device
                stream_callback=None
            )
            
            # Warm up the microphone and allow levels to settle
            print_styled_banner("Calibrating microphone...", 'info')
            for _ in range(3):
                stream.read(self.chunk_size, exception_on_overflow=False)
                time.sleep(0.1)
            
            # Countdown before recording
            clear_screen()
            print_styled_banner("Recording will start in:", 'info')
            for i in range(3, 0, -1):
                clear_screen()
                print_styled_banner(f"{i}...", 'info')
                stream.read(self.chunk_size, exception_on_overflow=False)
                time.sleep(1.0)
            
            clear_screen()
            print_styled_banner("Recording Started", 'info')
            
            chunks_needed = int((self.record_seconds * self.sample_rate) / self.chunk_size)
            chunks_recorded = 0

            # Record with volume level monitoring
            while chunks_recorded < chunks_needed:
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                self.frames.append(data)
                chunks_recorded += 1
                elapsed_time = (chunks_recorded * self.chunk_size) / self.sample_rate
                remaining_time = max(0, self.record_seconds - elapsed_time)
                
                # Show recording progress with volume level
                audio_data = np.frombuffer(data, dtype=np.int16)
                volume_norm = np.linalg.norm(audio_data) / len(audio_data)
                self.print_recording_progress(elapsed_time, remaining_time, self.record_seconds, volume_norm)

            print("\n")
            clear_screen()
            print_styled_banner("Recording Complete", 'success')
            
            stream.stop_stream()
            stream.close()

            # Create WAV buffer
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b''.join(self.frames))
            
            wav_buffer.seek(0)
            return wav_buffer

        except Exception as e:
            print_styled_banner(f"Recording Error: {str(e)}", 'error')
            return None
        finally:
            if 'stream' in locals():
                try:
                    stream.stop_stream()
                    stream.close()
                except:
                    pass
    
        
    def play_audio(self, wav_buffer):
        """Play the recorded audio"""
        try:
            # Reset buffer position
            wav_buffer.seek(0)
            
            # Open the WAV file for reading
            with wave.open(wav_buffer, 'rb') as wf:
                # Create an output stream
                stream = self.audio.open(
                    format=self.audio.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True
                )

                print("\nPlaying recording...")
                
                # Read and play chunks of data
                data = wf.readframes(self.chunk_size)
                while data:
                    stream.write(data)
                    data = wf.readframes(self.chunk_size)

                stream.stop_stream()
                stream.close()

        except Exception as e:
            print(f"\nError playing audio: {str(e)}")

    def record_with_preview(self):
        """Record audio and offer preview with options"""
        while True:
            audio_data = self.start_recording()
            if audio_data is None:
                clear_screen()
                print_styled_banner("Recording failed!", 'error')
                return {'status': 'error'}

            while True:
                clear_screen()
                # Clear any buffered input based on OS
                import platform
                if platform.system() == 'Windows':
                    import msvcrt
                    while msvcrt.kbhit():
                        msvcrt.getch()
                else:  # Linux/Unix
                    import sys, termios, tty
                    termios.tcflush(sys.stdin, termios.TCIOFLUSH)

                print_styled_banner(
                    "Options:\n"
                    "1. Play recording\n"
                    "2. Use recording\n"
                    "3. Record again\n"
                    "4. Save recording\n"
                    "5. Back (cancel recording)",
                    'info'
                )
                
                try:
                    time.sleep(0.1)
                    choice = input("Enter your choice (1-5): ").strip()
                    
                    if choice == '1':
                        clear_screen()
                        print_styled_banner("Playing recording...", 'info')
                        self.play_audio(audio_data)
                    elif choice == '2':
                        clear_screen()
                        return {'status': 'success', 'data': audio_data}
                    elif choice == '3':
                        clear_screen()
                        print_styled_banner("Starting new recording...", 'info')
                        break
                    elif choice == '4':
                        clear_screen()
                        self.save_recording(audio_data)
                    elif choice == '5':
                        clear_screen()
                        print_styled_banner("Recording cancelled", 'info')
                        return {'status': 'cancelled'}
                    else:
                        clear_screen()
                        print_styled_banner("Invalid choice! Please try again.", 'error')
                except Exception as e:
                    clear_screen()
                    print_styled_banner(f"Input error: {str(e)}", 'error')
                    continue

    def __del__(self):
        self.audio.terminate()

    def save_recording(self, wav_buffer):
        """Save the recorded audio"""
        try:
            # Create recordings directory if it doesn't exist
            recordings_dir = os.path.join(current_dir, 'recordings')
            if not os.path.exists(recordings_dir):
                os.makedirs(recordings_dir)

            # Generate timestamp for filename
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            filename = os.path.join(recordings_dir, f'recording_{timestamp}.wav')

            # Reset buffer position
            wav_buffer.seek(0)

            # Read and save the audio data
            with wave.open(wav_buffer, 'rb') as wf:
                params = wf.getparams()
                frames = wf.readframes(wf.getnframes())

            with wave.open(filename, 'wb') as wf:
                wf.setparams(params)
                wf.writeframes(frames)

            print_styled_banner(
                f"Recording saved successfully!\n"
                f"Location: {filename}",
                'success'
            )
            time.sleep(2)

        except Exception as e:
            print_styled_banner(f"Error saving recording: {str(e)}", 'error')
            time.sleep(2)


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

    def print_recording_progress(self, elapsed_time, remaining_time, total_time, volume_norm):
        """Print recording progress bar with volume level indicator"""
        width = 40
        filled = min(width, int(width * elapsed_time / total_time))
        bar = '█' * filled + '▒' * (width - filled)
        
        # Add volume level indicator
        volume_bar_width = 10
        volume_level = min(volume_bar_width, int(volume_norm / 500 * volume_bar_width))
        volume_bar = '█' * volume_level + '▒' * (volume_bar_width - volume_level)
        
        print(f'\rRecording: [{bar}] {min(elapsed_time, total_time):.1f}s / {total_time:.1f}s  Volume: [{volume_bar}]', 
              end='', flush=True)

def clear_screen():
    """Clear the console screen"""
    # os.system('cls' if os.name == 'nt' else 'clear')
    pass

def print_main_banner():
    print_styled_banner(
        "Voice Recognition System\n"
        "────────────────────────\n"
        "Space - Start Voice Verification\n"
        "Q     - Quit System",
        'normal'
    )

def print_styled_banner(message, style='normal'):
    """Print messages in banner style"""
    width = 42  # Fixed width for consistent look
    
    styles = {
        'normal': ('╔', '║', '╚', '═'),
        'success': ('┏', '┃', '┗', '━'),
        'error': ('▄', '█', '▀', '▀'),
        'info': ('┌', '│', '└', '─')
    }
    
    top, side, bottom, line = styles.get(style, styles['normal'])
    
    # Split message into lines and ensure each line fits within width
    lines = []
    for text in message.split('\n'):
        while len(text) > width - 4:  # -4 for side margins
            # Split at the last space before width limit
            split_point = text[:width-4].rfind(' ')
            if split_point == -1:
                split_point = width - 4
            lines.append(text[:split_point])
            text = text[split_point:].lstrip()
        if text:
            lines.append(text)

    # Print top border
    print(f"{top}{'═' * (width-2)}╗")
    
    # Print message
    for line in lines:
        padding = ' ' * (width - 4 - len(line))
        print(f"{side}  {line}{padding}  {side}")
    
    # Print bottom border
    print(f"{bottom}{'═' * (width-2)}╝")
    print()  # Add empty line for spacing

    

if __name__ == "__main__":
    clear_screen()
    print_styled_banner(
        "Voice Recognition System\n"
        "────────────────────────\n"
        "System ready for verification\n"
        "Press 'space' to start verification\n"
        "Press 'q' to quit",
        'normal'
    )
    door_system = DoorSystem()
    door_system.run()
    