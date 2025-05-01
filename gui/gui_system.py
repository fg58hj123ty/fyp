import sys

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QDesktopWidget,QHBoxLayout, QLabel, QStackedWidget, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QFrame,QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsTextItem
from PyQt5.QtCore import QObject, pyqtSignal, QThread, Qt, QTimer,QDateTime
from PyQt5.QtGui import *
from PyQt5.QtGui import QFont
import pyaudio
import wave
import numpy as np
from sqlalchemy import create_engine, Column, Integer, String, Sequence, DateTime, Enum, inspect,BLOB,text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func
import speech_recognition as sr
import os
import io
import sounddevice as sd
from scipy.io.wavfile import write
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2FeatureExtractor ,WavLMForXVector
import torch
import librosa
import time
import threading
from datetime import datetime
# Load the feature extractor and model with allowlisted BatchFeature
from transformers.feature_extraction_utils import BatchFeature
from AudioRecorder import AudioRecorder

# Allowlist the BatchFeature class
torch.serialization.add_safe_globals([BatchFeature])
#set path
project_file_dir = os.path.abspath(os.path.dirname(__file__)) 
# db_path = os.path.join(project_file_dir, "instance", "site.db")
parent_dir = os.path.abspath(os.path.join(project_file_dir, ".."))
db_path = os.path.join(parent_dir, "instance","site.db")

feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained('microsoft/wavlm-base-plus-sv')
model = WavLMForXVector.from_pretrained('microsoft/wavlm-base-plus-sv')
engine = create_engine(f"sqlite:///{db_path}", echo=True)
Base = declarative_base()
Base.metadata.create_all(engine)
DBSession = sessionmaker(bind=engine)
session = DBSession()
select_username = None


def bytes_to_tensor(tensor_bytes):
    buffer = io.BytesIO(tensor_bytes)
    # tensor = torch.load(buffer)
    tensor = torch.load(buffer, weights_only=False) 
    return tensor

def load_audio(file_path):
    speech, _ = librosa.load(file_path, sr=16000, mono=True)
    return speech
def change_to_embedding():
    return


def compare2(user):
    with engine.connect() as connection:
        query = text(
            "SELECT profile_embedding FROM user_voice_profile WHERE user_id = :user_id"
        )
        result = connection.execute(
            query,
            {"user_id": user.id}
        )
    user_voice_profile = result.fetchone()

    speech1 = load_audio(os.path.join(project_file_dir, 'recording0.wav') )
    inputs1 = feature_extractor(speech1, sampling_rate=16000, padding=True, return_tensors="pt")
    embeddings1 = model(**inputs1).embeddings
    embeddings1= torch.nn.functional.normalize(embeddings1, dim=-1).cpu()
    embedding =  np.frombuffer(user_voice_profile.profile_embedding, dtype=np.float32) 
    embedding_tensor = torch.tensor(embedding)
    
    cosine_sim = torch.nn.CosineSimilarity(dim=-1)
    similarity = cosine_sim(embeddings1[0], embedding_tensor)

    print("into compare 4")

    del embeddings1  ,inputs1
    torch.cuda.empty_cache()
    threshold = 0.86  # the optimal threshold is dataset-dependent
    print(f"the similarity is {similarity}")
    if similarity > threshold:
        print("Speakers same")
        return "same"
    print("Speakers are not the same!")
    return "Speakers are not the same!"

class CircleButton(QPushButton):
    def __init__(self, number, unlock_screen):
        super().__init__()
        self.setFixedSize(80, 80)
        self.setStyleSheet(
            "QPushButton {background-color:transparent ; border-radius: 40px;}"
            "QPushButton:pressed {background-color: gray; border-radius: 40px;}"
        )
        self.number = number
        self.setText(str(number))
        self.unlock_screen = unlock_screen
        self.clicked.connect(self.button_clicked)  

        font = QFont()
        font.setPointSize(16)  
        self.setFont(font)  


    def button_clicked(self):
        self.unlock_screen.button_clicked(self.number)  

class StandbyScreen(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.setFixedSize(stacked_widget.size())

        self.setStyleSheet("""
            StandbyScreen {
                background-color: lightblue;
            }
            QLabel {
                background-color: transparent;
            }
        """)

        
        layout = QVBoxLayout()
        layout.setSpacing(20)  
        layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(layout)

    
        self.time_label = QLabel()
        self.time_label.setFont(QFont("Arial", 36))  
        self.time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.time_label)


        self.date_label = QLabel()
        self.date_label.setFont(QFont("Roboto", 24))
        self.date_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.date_label)

        layout.addStretch(1)

        self.password_label = QLabel("Press anywhere to continue")
        self.password_label.setFont(QFont("Roboto", 18))
        self.password_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.password_label)

        layout.addStretch(1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  
        self.update_time()

    def update_time(self):
        current_time = QDateTime.currentDateTime()
        self.time_label.setText(current_time.toString("hh:mm:ss"))
        self.date_label.setText(current_time.toString("yyyy-MM-dd dddd")) 

    def mousePressEvent(self, event):
        self.stacked_widget.load_page(UnlockScreen)
        self.stacked_widget.unload_page(StandbyScreen)


class UnlockScreen(QWidget):
    def __init__(self,stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.setFixedSize(stacked_widget.size())

        self.setStyleSheet("""
            UnlockScreen {
                background-color: lightblue;
            }
            QLabel {
                background-color: transparent;
            }
            QPushButton {
                background-color: transparent;
                border-radius: 25px;
            }
            QPushButton:pressed {
                background-color: gray;
                border-radius: 25px;
            }
            .dot {
                background-color: gray;
                border-radius: 10px;
            }
            .dot-filled {
                background-color: white;
                border-radius: 10px;
            }
        """)

        self.buttons = []
        self.clicked_numbers = []

        layout = QVBoxLayout()
        layout.setSpacing(10)  
        layout.setContentsMargins(20, 20, 20, 20)  
        self.setLayout(layout)

     
        self.password_label = QLabel("Please Enter access code")
        font = QFont()
        font.setPointSize(18)  # set text size
        self.password_label.setFont(font)
        self.password_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.password_label)

       
        self.dot_layout = QHBoxLayout()
        self.dot_layout.setSpacing(20)
        self.dot_layout.setAlignment(Qt.AlignCenter)
        self.dots = []  
        self.dot_layout.addStretch(1)  

        for _ in range(3):
            dot = QLabel()
            dot.setFixedSize(22, 22)  
            dot.setStyleSheet("background-color: gray; border-radius: 11px;")
            dot.setProperty("class", "dot")  
            self.dot_layout.addWidget(dot)
            self.dots.append(dot)
            self.dot_layout.addStretch(1)  

        layout.addLayout(self.dot_layout)

        for i in range(1, 10):
            button = CircleButton(i, self)
            self.buttons.append(button)

        rows_layout = []
        for i in range(0, 9, 3):
            row_layout = QHBoxLayout()
            row_layout.addWidget(self.buttons[i])
            row_layout.addWidget(self.buttons[i + 1])
            row_layout.addWidget(self.buttons[i + 2])
            rows_layout.append(row_layout)

        for row_layout in rows_layout:
            layout.addLayout(row_layout)

        zero_button_layout = QHBoxLayout()
        zero_button_layout.addStretch(1)
        zero_button = CircleButton(0, self)
        zero_button_layout.addWidget(zero_button)
        zero_button_layout.addStretch(1)
        layout.addLayout(zero_button_layout)

    #change the color when id input
    def update_dots(self):
        for i, dot in enumerate(self.dots):
            if i < len(self.clicked_numbers):
                dot.setStyleSheet("background-color: white; border-radius: 10px;")
            else:
                dot.setStyleSheet("background-color: gray; border-radius: 10px;")
                self.password_label.setText("Please Enter access code")


    def check_password(self):

        access_code = ''.join(map(str, self.clicked_numbers)) 

        with engine.connect() as connection:
            query = text(
                "SELECT username FROM user WHERE access_code = :user_access_code"
            )
            result = connection.execute(
                query,
                {"user_access_code": access_code}
            )
            user = result.fetchone()

        if user:
            global select_username 
            select_username = user.username
            self.stacked_widget.setCurrentIndex(1)
            self.clicked_numbers = []
            self.update_dots()
            self.stacked_widget.load_page(MicrophonePage) # go next page
        else:
            self.password_label.setText("Incorrect Password!")
            for button in self.buttons:
                button.setEnabled(True)
            self.clicked_numbers = []
            QTimer.singleShot(500, self.update_dots)


    def button_clicked(self, number):
        print(f"Button {number} clicked.")
        if len(self.clicked_numbers) < 3:
            self.clicked_numbers.append(number)
            self.update_dots()
            print(f"Clicked numbers: {self.clicked_numbers}")
        if len(self.clicked_numbers) == 3:
            print(f"into password check: {self.clicked_numbers}")
            self.check_password()

        self.stacked_widget.reset_timer()

class MicrophonePage(QWidget):
    switch_to_unlock_screen = pyqtSignal()

    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget

        self.setFixedSize(stacked_widget.size())
        self.setStyleSheet("background-color: transparent;")
        self.setup_initial_ui()  # 初始化 UI
        
    def setup_initial_ui(self):
        self.layout = QVBoxLayout()
        image_layout = QHBoxLayout()
        image_layout.addStretch()

        self.graphics_view = QGraphicsView(self)
        self.scene = QGraphicsScene(self)
        self.graphics_view.setScene(self.scene)


        # self.graphics_view.setStyleSheet("background-color: transparent;")
        self.graphics_view.setFrameStyle(QFrame.NoFrame)

        self.graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        
        self.circle_pixmap = QPixmap(os.path.join(project_file_dir, "ic_fluent_circle_24_filled.png"))
        self.circle_item = QGraphicsPixmapItem(self.circle_pixmap)
        self.scene.addItem(self.circle_item)

        self.mic_pixmap = QPixmap(os.path.join(project_file_dir, "mic_icon_open.png"))
        self.mic_pixmap = self.mic_pixmap.scaled(84, 84)
        self.mic_item = QGraphicsPixmapItem(self.mic_pixmap)
        self.scene.addItem(self.mic_item)

   
        self.circle_item.setZValue(0)  # seting z
        self.mic_item.setZValue(1)  # seting z 

     
        self.center_circle_on_mic()

        image_layout.addWidget(self.graphics_view)
        image_layout.addStretch()
        self.layout.addLayout(image_layout)
        self.setLayout( self.layout)

        self.start_background_task()

    def start_background_task(self):
        if hasattr(self, 'background_task'):
         self.background_task.deleteLater()
        self.background_task = BackgroundTask()
        self.background_task.task_finished.connect(self.on_task_finished)
        self.background_task.change_image_signal.connect(self.change_image)
        self.background_task.volume_signal.connect(self.update_mic_animation)
        self.background_task.error_occurred.connect(self.on_error_occurred)
        self.background_task.start()

    def center_mic_in_view(self):
      
        view_width = self.graphics_view.width()
        view_height = self.graphics_view.height()

        mic_width = self.mic_item.boundingRect().width()
        mic_height = self.mic_item.boundingRect().height()

        offset_x = (view_width - mic_width) / 2
        offset_y = (view_height - mic_height) / 2

        self.mic_item.setPos(offset_x, offset_y)
    
    def center_circle_on_mic(self):
        """將圓形圖標居中於麥克風圖標"""
        mic_rect = self.mic_item.boundingRect()
        circle_rect = self.circle_item.boundingRect()

        circle_x = mic_rect.center().x() - circle_rect.width() / 2
        circle_y = mic_rect.center().y() - circle_rect.height() / 2

        self.circle_item.setPos(circle_x, circle_y)

    def update_mic_animation(self, volume):
        """根據音量大小變更麥克風圖標的大小"""
        alpha = 0.1  
        smoothed_volume = 0  
        volume_gain = 80  
        last_scale_factor = 1.5  
        noise_threshold = 0.5 
        sustained_volume = 0  


        min_scale = 1.5  
        max_scale = 3  

    
        smoothed_volume = (alpha * volume) + ((1 - alpha) * smoothed_volume)

   
        scaled_volume = smoothed_volume * volume_gain

   
        if scaled_volume < noise_threshold:
            sustained_volume = 0  
         
            target_scale_factor = last_scale_factor
        else:
            sustained_volume += scaled_volume  
            if sustained_volume > noise_threshold:
             
                target_scale_factor = min(max(1.3 + (scaled_volume * 0.5), min_scale), max_scale)
            else:
                target_scale_factor = last_scale_factor

   
        scaled_pixmap = self.circle_pixmap.scaled(
            int(64 * target_scale_factor), int(64 * target_scale_factor), Qt.KeepAspectRatio
        )
        self.circle_item.setPixmap(scaled_pixmap)

        last_scale_factor = target_scale_factor

  
        self.center_circle_on_mic()

    def on_task_finished(self, username , unlock_state):
        print("Unlock successful:", unlock_state)
        
        old_layout = self.layout
        if old_layout:
            # remove last layout and release resource
            QWidget().setLayout(old_layout) 
        new_layout = QVBoxLayout(self)
        self.setLayout(new_layout)


        if unlock_state == "success":
            self.stacked_widget.load_page(SuccessScreen, username=username)
        else:
            self.stacked_widget.load_page(FailureScreen)

        self.stacked_widget.unload_page(MicrophonePage)


       




    #update mic image
    def change_image(self):
        self.mic_pixmap = QPixmap(os.path.join(project_file_dir, "mic_icon_close.png"))
        self.mic_pixmap = self.mic_pixmap.scaled(84, 84)

        self.mic_item.setPixmap(self.mic_pixmap)  
        self.scene.removeItem(self.circle_item)

    def on_error_occurred(self, error_message):
        print("Error occurred:", error_message)
        self.go_back()

    def go_back(self):
        self.stacked_widget.set_background_color("")
        self.stacked_widget.load_page(UnlockScreen)
        self.stacked_widget.unload_page(MicrophonePage)

   

class BackgroundTask(QThread):
    task_finished = pyqtSignal(str,str) 
    change_image_signal = pyqtSignal() 
    volume_signal = pyqtSignal(float)  
    error_occurred = pyqtSignal(str)  



    def run(self):
        try:
            recorder = AudioRecorder(self.volume_signal)
            recorder.start_recording()  
            global select_username 
            self.change_image_signal.emit()
            with engine.connect() as connection:
                query = text('SELECT * FROM user WHERE username = :selected_name')
                user = connection.execute(query, {'selected_name': select_username}).fetchone()

            now = datetime.now()
            formatted_now = now.strftime("%Y-%m-%d %H:%M:%S.%f")
            unlock_state = "unsuccess"
            if user:
                text2 = compare2(user)
                if text2 == "same":
                    unlock_state = "success"
                with engine.connect() as connection:
                    query = text(
                        "INSERT INTO activity_log(user_id, timestamp, activity_type, status) "
                        "VALUES (:user_id, :timestamp, :activity_type ,:status)"
                    )
                    connection.execute(
                        query,
                        {
                            "user_id": user.id,
                            "timestamp" :formatted_now,
                            "activity_type": "login",
                            "status": unlock_state
                        },
                    )
                    connection.commit()

            #send finish recording signal
            self.task_finished.emit(select_username,unlock_state)

        except Exception as e:
            # send error signal
            self.error_occurred.emit(str(e))

class SuccessScreen(QWidget):
    def __init__(self, stacked_widget, username):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.setFixedSize(stacked_widget.size())
        self.username = username

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.mic_pixmap = QPixmap(os.path.join(project_file_dir, "checkmark_black.png")).scaled(128, 128)
        self.successful_image = QLabel(self)
        self.successful_image.setPixmap(self.mic_pixmap)
        self.successful_image.setAlignment(Qt.AlignCenter)

        self.mic_text = QLabel(f"Successful\n{username}", self)
        self.mic_text.setFont(QFont("Arial", 24))
        self.mic_text.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.successful_image)
        layout.addWidget(self.mic_text)
        layout.setAlignment(Qt.AlignCenter)

        
        self.stacked_widget.set_background_color("lightgreen")

        QTimer.singleShot(4000, self.go_back)

    def go_back(self):
        self.stacked_widget.set_background_color("")
        self.stacked_widget.load_page(UnlockScreen)  # 假設返回 UnlockScreen
        self.stacked_widget.unload_page(SuccessScreen)        

class FailureScreen(QWidget):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.setFixedSize(stacked_widget.size())
        
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.mic_pixmap = QPixmap(os.path.join(project_file_dir, "dismiss_black.png")).scaled(128, 128)
        self.successful_image = QLabel(self)
        self.successful_image.setPixmap(self.mic_pixmap)
        self.successful_image.setAlignment(Qt.AlignCenter)

        self.mic_text = QLabel("Unsuccessful", self)
        self.mic_text.setFont(QFont("Arial", 24))
        self.mic_text.setAlignment(Qt.AlignCenter)

        layout.addStretch(1)  
        layout.addWidget(self.successful_image)
        layout.addWidget(self.mic_text)
        layout.addStretch(1)  

        self.try_again_button = QPushButton("Try Again ?", self)
        self.try_again_button.setFixedSize(150, 50)
        self.try_again_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 10px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.try_again_button.clicked.connect(self.retry_recording)

        layout.addWidget(self.try_again_button, alignment=Qt.AlignCenter)
        layout.addStretch(1)  

        self.stacked_widget.set_background_color("red")

        QTimer.singleShot(4000, self.go_back)

    def retry_recording(self):
        self.stacked_widget.set_background_color("")  
        self.stacked_widget.load_page(MicrophonePage)
        self.stacked_widget.unload_page(FailureScreen)

    def go_back(self):
        self.stacked_widget.set_background_color("")
        self.stacked_widget.load_page(UnlockScreen)  
        self.stacked_widget.unload_page(FailureScreen)

class StackedWidget(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.pages = {}

        self.timeout_screens = {"UnlockScreen"}
        #set the timer if over 5s no any movement back to StandbyScreen
        self.inactivity_timer = QTimer(self)
        self.inactivity_timer.setInterval(4000)  
        self.inactivity_timer.timeout.connect(self.return_to_standby)
        self.inactivity_timer.start()

    def return_to_standby(self):
        current_page = self.currentWidget().__class__.__name__
        if current_page in self.timeout_screens:
            print(f"Inactivity timeout in {current_page}, returning to StandbyScreen")
            self.load_page(StandbyScreen)

    def reset_timer(self):
        current_page = self.currentWidget().__class__.__name__
        if current_page in self.timeout_screens:
            self.inactivity_timer.stop()
            self.inactivity_timer.setInterval(10000)  
            self.inactivity_timer.start()
            print(f"Timer reset to 10 seconds in {current_page}")
        else:
            self.inactivity_timer.stop()

    #if have mouse click rest timer
    def mousePressEvent(self, event):
        self.reset_timer()
        super().mousePressEvent(event)

    #if have key click rest timer
    def keyPressEvent(self, event):
        self.reset_timer()
        super().keyPressEvent(event)

    def load_page(self, page_class,**kwargs):
        class_name = page_class.__name__

        if class_name not in self.pages:
            page_instance = page_class(self,**kwargs)
            self.pages[class_name] = page_instance
            self.addWidget(page_instance)

        self.setCurrentWidget(self.pages[class_name])
        if class_name == "UnlockScreen":
            self.reset_timer()

    def unload_page(self, page_class):
        class_name = page_class.__name__

        if class_name in self.pages:
            page_instance = self.pages[class_name]
            self.removeWidget(page_instance)
            page_instance.deleteLater()
            del self.pages[class_name]

    def set_background_color(self, color):
        self.setStyleSheet(f"background-color: {color};")  



if __name__ == "__main__":
    app = QApplication(sys.argv)

    screen = QDesktopWidget().screenGeometry()
    screen_width = screen.width()
    screen_height = screen.height()

    stacked_widget = StackedWidget()
    # stacked_widget.setFixedSize(500, 600)
    stacked_widget.showFullScreen()

    stacked_widget.load_page(StandbyScreen)
    stacked_widget.show()

    sys.exit(app.exec_())