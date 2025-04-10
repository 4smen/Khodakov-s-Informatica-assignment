import sys

import librosa as lbs
import sounddevice as sd
import soundfile as sf
import pyqtgraph as pg
import numpy as np
import pydub as pd

from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QMainWindow, QWidget, QApplication, QPushButton, QLineEdit, QInputDialog, QMenu
from PyQt6.QtWidgets import QLabel, QFileDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QSlider, QProgressBar, QMessageBox
from PyQt6.QtGui import QIcon, QImage, QPixmap, QAction, QKeySequence, QShortcut


class AudioEditor(QMainWindow):
    def __init__(self, file_added): 
        super().__init__()

        #создаём необходимые компоненты
        self.supported_rates = [8000, 11025, 12000, 16000, 22050,
                                24000, 32000, 44100, 48000]
        
        self.current_position = 0
        self.is_playing = False
        self.playback_speed = 1.0
        self.loop = False
        self.stream = None
        
        self.imported = False
        
        self.natural_movement = False

        self.black = False

        self.initUI()

    def initUI(self): #отрисовка интерфейса
        self.setGeometry(300, 140, 1300, 800)
        self.setWindowTitle('AudioEdit')

        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.undo)
        
        ui = QWidget() #компановка элементов в окне
        self.setCentralWidget(ui)

        self.import_button = QPushButton('Импортировать аудио файл', self) #меню действий
        self.import_button.clicked.connect(self.importAudioFile)

        self.export_button = QPushButton('Экспортировать аудио файл', self)
        self.export_button.clicked.connect(self.exportAudioFile)

        self.operations_button = QPushButton('Операции', self)

        operations_menu = QMenu()
        reset = QAction("Откат всех действий", self.operations_button)
        trim = QAction("Обрезка", self.operations_button)
        cut = QAction("Вырезка", self.operations_button)
        fade_in = QAction("Возрастание", self.operations_button)
        fade_out = QAction("Затухание", self.operations_button)
        #reverb = QAction("Ревербация", self.operations_button)
        reverse = QAction("Реверсирование", self.operations_button)
        
        reset.triggered.connect(self.reset)
        trim.triggered.connect(self.trim)
        cut.triggered.connect(self.cut)
        fade_in.triggered.connect(self.fade_in)
        fade_out.triggered.connect(self.fade_out)
        #reverb.triggered.connect(self.reverb)
        reverse.triggered.connect(self.reverse)

        operations_menu.addAction(reset)
        operations_menu.addAction(trim)
        operations_menu.addAction(cut)
        operations_menu.addAction(fade_in)
        operations_menu.addAction(fade_out)
        #operations_menu.addAction(reverb)
        operations_menu.addAction(reverse)
        
        self.operations_button.setMenu(operations_menu)
        
        uph = QHBoxLayout() 
        uph.addWidget(self.import_button)
        uph.addWidget(self.export_button)
        uph.addWidget(self.operations_button)

        self.file_name  = QLabel("Сначала импротируйте аудио файл", self) #название файла и кнопки воспроизведения
        self.file_name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.cur_pos_text  = QLabel("0.00", self) #позиция линии прогресса
        self.cur_pos_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        scale_x = 55
        scale_y = 40

        self.loading_image = QLabel(self)
        pixmap = QPixmap("Images/loading.png")
        self.loading_image.setPixmap(pixmap)
        self.loading_image.resize(60, 60)
        self.loading_image.setHidden(True)

        self.play_button = QPushButton('', self)
        self.play_button.clicked.connect(self.play)
        self.play_button.setMinimumSize(scale_x, scale_y)

        self.pause_button = QPushButton('', self)
        self.pause_button.clicked.connect(self.pause)
        self.pause_button.setMinimumSize(scale_x, scale_y)

        self.rewind_button = QPushButton('', self)
        self.rewind_button.clicked.connect(self.rewind)
        self.rewind_button.setMinimumSize(scale_x, scale_y)

        self.fullrewind_button = QPushButton('', self)
        self.fullrewind_button.clicked.connect(self.rewind_to_start)
        self.fullrewind_button.setMinimumSize(scale_x, scale_y)

        self.fast_forward_button = QPushButton('', self)
        self.fast_forward_button.clicked.connect(self.fast_forward)
        self.fast_forward_button.setMinimumSize(scale_x, scale_y)

        self.fullfast_forward_button = QPushButton('', self)
        self.fullfast_forward_button.clicked.connect(self.fast_forward_to_end)
        self.fullfast_forward_button.setMinimumSize(scale_x, scale_y)

        self.loop_button = QPushButton('', self)
        self.loop_button.clicked.connect(self.toggle_loop)
        self.loop_button.setMinimumSize(scale_x, scale_y)
        
        action_buttons = QHBoxLayout()
        action_buttons.addWidget(self.fullrewind_button)
        action_buttons.addWidget(self.rewind_button)
        action_buttons.addWidget(self.play_button)
        action_buttons.addWidget(self.pause_button)
        action_buttons.addWidget(self.fast_forward_button)
        action_buttons.addWidget(self.fullfast_forward_button)
        action_buttons.addStretch(1)
        action_buttons.addWidget(self.loop_button)

        midh = QHBoxLayout()
        midh.addStretch(1)
        midh.addWidget(self.file_name)
        midh.addStretch(1)
        midh.addLayout(action_buttons)
        midh.addStretch(1)
        midh.addWidget(self.cur_pos_text)
        midh.addStretch(1)
        midh.addWidget(self.loading_image)
        midh.addStretch(1)

        self.volume_sl = QSlider(Qt.Orientation.Vertical, self) #ползунки
        self.volume_sl.setRange(-60, 20) #от -60 до +60 децибел
        self.volume_sl.sliderReleased.connect(self.volume_sl_changed)
        
        self.pitch_sl = QSlider(Qt.Orientation.Vertical, self)
        self.pitch_sl.setRange(-12, 12) #+- 12 полутонов(1 октава)
        self.pitch_sl.sliderReleased.connect(self.pitch_sl_changed)
        
        self.speed_sl = QSlider(Qt.Orientation.Vertical, self)
        self.speed_sl.setRange(50, 200) #от 50% до 200%
        self.speed_sl.setTickInterval(5)
        self.speed_sl.sliderReleased.connect(self.speed_sl_changed)

        self.volume_name  = QLabel("Громкость", self)
        self.volume_name.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        
        self.pitch_name  = QLabel("Высота", self)
        self.pitch_name .setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        
        self.speed_name  = QLabel("Скорость", self)
        self.speed_name.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        self.volume_button = QPushButton("", self)
        self.volume_button.clicked.connect(self.volume_dialog)
        self.volume_button.setMinimumSize(40, 40)

        self.pitch_button = QPushButton("", self)
        self.pitch_button.clicked.connect(self.pitch_dialog)
        self.pitch_button.setMinimumSize(40, 40)

        self.speed_button = QPushButton("", self)
        self.speed_button.clicked.connect(self.speed_dialog)
        self.speed_button.setMinimumSize(40, 40)

        volume_h = QHBoxLayout()
        volume_h.addWidget(self.volume_name)
        volume_h.addWidget(self.volume_button)

        pitch_h = QHBoxLayout()
        pitch_h.addWidget(self.pitch_name)
        pitch_h.addWidget(self.pitch_button)

        speed_h = QHBoxLayout()
        speed_h.addWidget(self.speed_name)
        speed_h.addWidget(self.speed_button)

        volume_layout = QVBoxLayout()
        volume_layout.addLayout(volume_h, Qt.AlignmentFlag.AlignCenter)
        volume_layout.addWidget(self.volume_sl)

        pitch_layout = QVBoxLayout()
        pitch_layout.addLayout(pitch_h, Qt.AlignmentFlag.AlignCenter)
        pitch_layout.addWidget(self.pitch_sl)

        speed_layout = QVBoxLayout()
        speed_layout.addLayout(speed_h, Qt.AlignmentFlag.AlignCenter)
        speed_layout.addWidget(self.speed_sl)

        downh = QHBoxLayout()
        downh.addLayout(volume_layout)
        downh.addLayout(pitch_layout)
        downh.addLayout(speed_layout)

        self.graph_pen = pg.mkPen() #настройка внешнего вида графика
        self.line_pen = pg.mkPen()
        
        self.audio_graph = pg.PlotWidget() #создаём график
        self.audio_graph.setBackground("w") #меняем фон
        self.audio_graph.setLabel('left', 'Decibel')
        self.audio_graph.setLabel('bottom', 'Time')
        self.audio_graph.setClipToView(True) #включаем функцию автоматического изменения размера под размер спектограммы
        self.audio_graph.setMouseEnabled(x=False, y=False) #отключаем перемещение мышкой
        self.audio_graph.setAutoVisible(x=True, y=True)  #включаем автоматический подгон взгляда на новый график
        self.audio_graph.setMenuEnabled(False)
        
        self.graph_pen = pg.mkPen(color=(0, 0, 255), width=5) #настройка внешнего вида графика
        self.line_pen = pg.mkPen(color=(255, 0, 0), width=4) #настройка внешнего вида графика
        
        self.audio_graph.scene().sigMouseClicked.connect(self.mouse_clicked)
        #self.audio_graph.scene().sigMouseMoved.connect(self.mouse_moved)
        #self.audio_graph.scene().sigMouseButtonReleased.connect(self.mouse_released)
        
        self.audio_graph.plot([0], [0])

        self.position_line = pg.InfiniteLine(pos=0, angle=90, pen=self.line_pen, movable=True) #линия прогресса
        self.position_line.sigPositionChangeFinished.connect(self.line_moved)

        if self.black:
            self.play_button.setIcon(self.invert_icon_colors(QIcon("Images/play.png"), scale_x, scale_y))
            self.pause_button.setIcon(self.invert_icon_colors(QIcon("Images/pause.png"), scale_x, scale_y))
            self.rewind_button.setIcon(self.invert_icon_colors(QIcon("Images/rewind.png"), scale_x, scale_y))
            self.fullrewind_button.setIcon(self.invert_icon_colors(QIcon("Images/fullrewind.png"), scale_x, scale_y))
            self.fast_forward_button.setIcon(self.invert_icon_colors(QIcon("Images/fast_forward.png"), scale_x, scale_y))
            self.fullfast_forward_button.setIcon(self.invert_icon_colors(QIcon("Images/fullfast_forward.png"), scale_x, scale_y))
            self.loop_button.setIcon(self.invert_icon_colors(QIcon("Images/loop_unactive.png"), scale_x, scale_y))

            self.volume_button.setIcon(self.invert_icon_colors(QIcon("Images/dots.png"), 40, 40))
            self.pitch_button.setIcon(self.invert_icon_colors(QIcon("Images/dots.png"), 40, 40))
            self.speed_button.setIcon(self.invert_icon_colors(QIcon("Images/dots.png"), 40, 40))
        else:
            self.play_button.setIcon(QIcon("Images/play.png"))
            self.pause_button.setIcon(QIcon("Images/pause.png"))
            self.rewind_button.setIcon(QIcon("Images/rewind.png"))
            self.fullrewind_button.setIcon(QIcon("Images/fullrewind.png"))
            self.fast_forward_button.setIcon(QIcon("Images/fast_forward.png"))
            self.fullfast_forward_button.setIcon(QIcon("Images/fullfast_forward.png"))
            self.loop_button.setIcon(QIcon("Images/loop_unactive.png"))

            self.volume_button.setIcon(QIcon("Images/dots.png"))
            self.pitch_button.setIcon(QIcon("Images/dots.png"))
            self.speed_button.setIcon(QIcon("Images/dots.png"))

        layout = QVBoxLayout() #финальная сборка
        layout.addLayout(uph)
        layout.addStretch(1)
        layout.addLayout(midh)
        layout.addStretch(1)
        layout.addWidget(self.audio_graph)
        layout.addStretch(1)
        layout.addLayout(downh)
        layout.addStretch(1)
        
        ui.setLayout(layout) #конец отрисовки интерфейса


    def execute_warning(self):
        try:
            warning = QMessageBox.warning(self,
                                          "Предупреждение",
                                          "Вы уверены? Вы потеряете весь прогресс в случае согласия!",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if (warning == QMessageBox.StandardButton.Yes):
                return True
            else:
                return False
            print("Warning")
        except Exception as e:
            print(f"=== Warning failed: {e}")


    def invert_icon_colors(self, icon, x=100, y=100):
        pixmap = icon.pixmap(x, y)

        image = pixmap.toImage()

        image.invertPixels(QImage.InvertMode.InvertRgb)

        return QIcon(QPixmap.fromImage(image))


    def undo(self):
        try:
            if not self.imported:
                return
            
            self.audio = self.audio_prev
            self.sr = self.sr_prev

            self.tmp_audio = self.audio_prev
            self.tmp_sr = self.sr

            self.pitch = self.pitch_prev
            self.speed = self.speed_prev

            self.volume_sl.setValue(int(self.get_current_volume(self.audio)))
            self.pitch_sl.setValue(self.pitch_prev)
            self.speed_sl.setValue(self.speed_prev)

            self.update_plot() #обновляем график
            print("Undo")
        except Exception as e:
            print(f"=== Undo failed: {e}")


    def update_plot(self):
        try:
            self.duration = self.get_current_duration()
            self.time_axis = np.linspace(0, self.duration, len(self.audio))
            print(self.duration)

            self.audio_downsampled = self.audio[::60] #даунсемплим аудио файл(чтобы не лагало)
            self.time_axis_downsampled = self.time_axis[::60] #то же самое с временем

            self.audio_graph.setMouseEnabled(x=True, y=True)

            self.audio_graph.enableAutoRange(axis='xy')
            
            self.audio_graph.clear() #чистим график
            self.audio_graph.plot(self.time_axis_downsampled, self.audio_downsampled, pen=self.graph_pen) #порисульки

            self.audio_graph.autoRange(padding=0.1) #скейлим под новый график

            self.audio_graph.addItem(self.position_line) #добавляем линию прогресса

            self.audio_graph.setMouseEnabled(x=False, y=False)
            print("Updated plot")
        except Exception as e:
            print(f"=== Updating plot failed: {e}")


    #===============методы кнопок================

        
    def importAudioFile(self): #импортируем аудиофайл
        try:
            self.audio_name, self.format = QFileDialog.getOpenFileName(self, 'Выбрать аудио файл', 'C:/', '*.mp3;;*.wav;;*.ogg;;*.flac')
            if not self.audio_name:
                return
            
            print(self.audio_name, self.format)
            
            self.audio, self.sr = lbs.load(self.audio_name, sr=None) #sr - sampling_rate
            self.file_name.setText(self.audio_name.split("/")[-1])

            self.audio_prev = self.audio #делаем бэкап, чтобы можно было откатить действие
            self.sr_prev = self.sr
            
            self.audio_singletone = self.audio
            self.sr_singletone = self.sr

            self.tmp_audio = self.audio
            self.tmp_sr = self.sr

            self.pitch = 0
            self.speed = 100

            self.pitch_prev = 0
            self.speed_prev = 100

            self.volume_sl.setValue(int(self.get_current_volume(self.audio)))
            self.pitch_sl.setValue(0)
            self.speed_sl.setValue(100)

            self.update_plot() #обновляем график

            self.setup_timer(20, 300) #включаем обновление шкалы воспроизведения

            self.imported = True
            print("Succesfully imported")
        except Exception as e:
            print(f"=== Audiofile is not picked: {e}")


    def exportAudioFile(self): #экспортируем аудиофайл
        try:
            if not self.imported:
                return
            self.new_audio_name, new_format = QFileDialog.getSaveFileName(self, 'Сохранить аудио файл',
                                                              f'{"/".join(self.audio_name.split("/")[:-1])}',
                                                              '*.mp3;;*.wav;;*.ogg;;*.flac')
            if not self.new_audio_name:
                return
            print(self.new_audio_name, new_format)
            print(self.sr_singletone, self.sr)

            if not self.new_audio_name.endswith(new_format[1:]):
                self.new_audio_name += new_format[1:]

            if (self.format == "*.mp3" or new_format == "*.mp3"):
                target_sr = min(self.supported_rates, key=lambda x: abs(x - self.sr))
            
            sf.write(self.new_audio_name, self.audio, target_sr)
            print(self.new_audio_name)
            print("Succesfully exported")
        except Exception as e:
            print(f"=== Export failed: {e}")


    def mouse_clicked(self, event):
        if (event.button() == Qt.MouseButton.LeftButton):
            view_coords = self.audio_graph.plotItem.vb.mapSceneToView(event.scenePos())
            line_pos = self.position_line.value()
            

    def play(self): #воспроизведение аудиофайла
        try:
            if not self.imported:
                return
            
            sender = self.sender()
            if not self.is_playing:
                self.is_playing = True
                self.stream = sd.OutputStream(
                samplerate=int(self.sr * self.playback_speed),
                channels=1,
                callback=self.audio_callback)
                self.stream.start()
                self.timer.start(self.update_speed)
                
                self.natural_movement = True
                self.position_line.movable = False
                
                sender.setIcon(QIcon("Images/stop.png"))
                print("Started playing")
            else:
                self.stream.stop()
                self.is_playing = False
                self.current_position = 0
                
                self.timer.stop()
                
                self.natural_movement = False
                self.position_line.movable =True

                sender.setIcon(QIcon("Images/play.png"))
                print("Stopped playing")
        except Exception as e:
            print(f"=== Playing failed: {e}")


    def audio_callback(self, outdata, frames, time, status): #обработка аудио файла перед его воспроизведением
        end_pos = self.current_position + frames
        if (end_pos > len(self.audio)):
            if self.loop:
                remaining = len(self.audio) - self.current_position
                outdata[:remaining] = self.audio[self.current_position:].reshape(-1, 1)
                outdata[remaining:] = self.audio[:frames-remaining].reshape(-1, 1)
                self.current_position = frames - remaining
            else:
                remaining = len(self.audio) - self.current_position
                outdata[:remaining] = self.audio[self.current_position:].reshape(-1, 1)
                outdata[remaining:] = 0
                self.current_position = 0
                self.is_playing = False
                self.timer.stop()
                self.play_button.setIcon(QIcon("Images/play.png"))
                self.position_line.setPos(self.get_current_duration())
                raise sd.CallbackStop
        else:
            outdata[:] = self.audio[self.current_position:end_pos].reshape(-1, 1)
            self.current_position = end_pos


    def pause(self): #я думаю тут объяснять не обязательно
        try:
            if not self.imported:
                return
            
            if self.is_playing:
                self.stream.stop()
                self.is_playing = False
                self.timer.stop()

                self.natural_movement = False
                self.position_line.movable = True

                self.play_button.setIcon(QIcon("Images/play.png"))
                print("Paused playing")
        except Exception as e:
            print(f"=== Pausing failed: {e}")


    def seek(self, seconds): #функция для перемотки на заданное в аргументе время
        try:
            position_samples = int(seconds * self.sr)
            self.current_position = np.clip(position_samples, 0, len(self.audio) - 1)
            print(f"rewinded {seconds} seconds")
        except Exception as e:
            print(f"=== rewinding {seconds} seconds failed: {e}")


    def rewind(self): #функция для перемотки на 5 секунд назад
        try:
            if not self.imported:
                return
            
            self.seek(self.current_position/self.sr - 5)
            print("Rewinded 5 seconds backwards")
        except Exception as e:
            print(f"=== Rewinding 5 seconds backwards failed: {e}")


    def rewind_to_start(self): #функция для перемотки в начало трека
        try:
            if not self.imported:
                return
            
            self.current_position = 0
            print("Rewinded to the start of the track")
        except Exception as e:
            print(f"=== Rewinding to the start of the track failed: {e}")


    def fast_forward(self): #функция для перемотки на 5 секунд вперёд
        try:
            if not self.imported:
                return
            
            self.seek(self.current_position/self.sr + 5)
            print("Rewinded 5 seconds forward")
        except Exception as e:
            print(f"=== Rewinding 5 seconds forward failed: {e}")


    def fast_forward_to_end(self): #функция для перемотки в конец трека
        try:
            if not self.imported:
                return
            
            self.current_position = len(self.audio) - 1
            print("Rewinded to the end of the track")
        except Exception as e:
            print(f"=== Rewinding to the end of the track failed: {e}")


    def toggle_loop(self): #переключение опции повторения трека
        try:
            self.loop = not self.loop
        
            sender = self.sender()
            if self.loop:
                sender.setIcon(QIcon("Images/loop_active.png"))
            else:
                sender.setIcon(QIcon("Images/loop_unactive.png"))

            print("loop toggled")
            return self.loop
        except Exception as e:
            print(f"=== loop toggle failed: {e}")
            

    def setup_timer(self, mn=20, mx=300): #таймер для обновления шкалы
        try:
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_progress)

            scale = min(1, self.duration / 250)  # 300s (5min) reaches max interval
            self.update_speed = int(mn + (mx - mn) * scale)
            print(self.update_speed)
            print("calculated an interval for timer")
        except Exception as e:
            print(f"=== calculating an interval for timer failed: {e}")


    def update_progress(self): #обновляем "прогресс" линии
        try:
            self.position_line.setPos(int(self.current_position / self.sr))
            self.cur_pos_text.setText(str(round(self.current_position / self.sr, 2)))
            print("updated pos_line")
        except Exception as e:
            print(f"=== updating pos_line failed: {e}")


    def line_moved(self, line):
        try:
            if not self.natural_movement:
                if (self.position_line.value() < 0):
                    self.current_position = 0
                    self.cur_pos_text.setText("0.00")
                    self.position_line.setPos(0)
                elif (self.position_line.value() > self.get_current_duration()):
                    print(self.position_line.value() * self.sr)
                    self.current_position = len(self.audio) - 1
                    self.cur_pos_text.setText(f"{round(self.get_current_duration(), 2)}")
                    self.position_line.setPos(self.get_current_duration())
                self.current_position = int(self.position_line.value() * self.sr)
                self.cur_pos_text.setText(str(round(self.current_position / self.sr, 2)))
            print("updated current pos")
        except Exception as e:
            print(f"=== updating current pos failed: {e}")


    #===============изменения аудио================


    def get_current_duration(self):
        try:
            print(f"got duration: {len(self.audio) / self.sr}")
            return len(self.audio) / self.sr
        except Exception as e:
            print(f"=== getting duration failed: {e}")


    def get_current_volume(self, audio):
        try:
            #считаем RMS(корень из среднего арифметического квадратов значений)
            rms = np.sqrt(np.mean(audio ** 2))
    
            #конвертируем в dBFS (20 * log10(rms))
            dbfs = 20 * np.log10(rms) #dbfs - decibels relative to full scale(децибел относительно полной шкалы)
            print("got current volume level")
            print(dbfs)
            return dbfs
        except Exception as e:
            print(f"=== getting current volume level failed: {e}")


    def librosa_to_pydub(self, audio_lbs, sr):
        y_int16 = (audio_lbs * (2 ** 15 - 1)).astype(np.int16) #конверируем файл из float32(numpy массив) в int16

        audio_pb = pd.AudioSegment(
            y_int16.tobytes(),
            frame_rate=sr,
            sample_width=2,
            channels=1
            )# 16-bit = 2 bytes per sample
    
        return audio_pb


    def pydub_to_librosa(self, audio_pd):
        samples = audio_pd.get_array_of_samples()
        sr = audio_pd.frame_rate
        channels = audio_pd.channels

        audio_lbs = np.array(samples).astype(np.float32) #конверируем файл в float32
    
        # Reshape for multi-channel if needed
        if (channels > 1):
            audio_lbs = audio_lbs.reshape(-1, channels)
    
        return audio_lbs, sr


    def reset(self):
        try:
            if not self.imported:
                return
            
            if (self.execute_warning()):
                self.audio_prev = self.audio
                self.sr_prev = self.sr

                self.pitch_prev = self.pitch
                self.speed_prev = self.speed
            
        
                self.audio = self.audio_singletone
                self.sr = self.sr_singletone

                self.pitch = 0
                self.speed = 100

                self.volume_sl.setValue(int(self.get_current_volume(self.audio)))
                self.pitch_sl.setValue(0)
                self.speed_sl.setValue(100)

                self.update_plot() #обновляем график
                print("reset")
            else:
                print("resetting cancelled")
                return
        except Exception as e:
            print(f"=== resetting failed: {e}")
    

    def trim(self):
        try:
            if not self.imported:
                return
            
            seconds_first, ok_pressed = QInputDialog.getDouble(self, "Обрезка",
                                                               f"Введите начальную позицию обрезки(в секундах, от 0 до {round(self.get_current_duration(), 2)} секунд)",
                                                               self.current_position / self.sr, 0, self.get_current_duration(), 2)
            if not ok_pressed:
                return
            seconds_second, ok_pressed = QInputDialog.getDouble(self, "Обрезка",
                                                                f"Введите конечную позицию обрезки(в секундах, от {seconds_first} до {round(self.get_current_duration(), 2)} секунд)",
                                                                seconds_first, seconds_first, self.get_current_duration(), 2)
            if not ok_pressed:
                return

            print(seconds_first)
            print(seconds_second)
            
            self.audio_prev = self.audio

            audio_pd = self.librosa_to_pydub(self.audio, self.sr)

            audio_pd = audio_pd[(seconds_first * 1000):(seconds_second * 1000)]

            self.audio, self.sr = self.pydub_to_librosa(audio_pd) #конверируем обратно
            self.change_volume(self.audio, self.volume_sl.value())


            audio_tmp_pd = self.librosa_to_pydub(self.tmp_audio, self.tmp_sr) #те же действия для временного файла

            audio_tmp_pd = audio_tmp_pd[(seconds_first * 1000):(seconds_second * 1000)]

            self.tmp_audio, self.tmp_sr = self.pydub_to_librosa(audio_tmp_pd) #конверируем обратно
            self.change_volume(self.tmp_audio, self.volume_sl.value())

            self.update_plot()
            print("trim")
        except Exception as e:
            print(f"=== trimming failed: {e}")


    def cut(self):
        try:
            if not self.imported:
                return
            
            seconds_first, ok_pressed = QInputDialog.getDouble(self, "Вырезка",
                                                               f"Введите начальную позицию вырезки(в секундах, от 0 до {round(self.get_current_duration(), 2)} секунд)",
                                                               self.current_position / self.sr, 0, self.get_current_duration(), 2)
            if not ok_pressed:
                return
            seconds_second, ok_pressed = QInputDialog.getDouble(self, "Вырезка",
                                                                f"Введите конечную позицию вырезки(в секундах, от {seconds_first} до {round(self.get_current_duration(), 2)} секунд)",
                                                                seconds_first, seconds_first, self.get_current_duration(), 2)
            if not ok_pressed:
                return

            print(seconds_first)
            print(seconds_second)
            
            self.audio_prev = self.audio

            audio_pd = self.librosa_to_pydub(self.audio, self.sr)

            if (seconds_first != 0):
                before = audio_pd[:(seconds_first * 1000)]
            after = audio_pd[(seconds_second * 1000):]

            if (seconds_first != 0):
                audio_pd = before + after
            else:
                audio_pd = after

            self.audio, self.sr = self.pydub_to_librosa(audio_pd) #конверируем обратно
            self.change_volume(self.audio, self.volume_sl.value())


            audio_tmp_pd = self.librosa_to_pydub(self.tmp_audio, self.tmp_sr) #те же действия для временного файла

            if (seconds_first != 0):
                before = audio_tmp_pd[:(seconds_first * 1000)]
            after = audio_tmp_pd[(seconds_second * 1000):]

            if (seconds_first != 0):
                audio_tmp_pd = before + after
            else:
                audio_tmp_pd = after

            self.tmp_audio, self.tmp_sr = self.pydub_to_librosa(audio_tmp_pd) #конверируем обратно
            self.change_volume(self.tmp_audio, self.volume_sl.value())           

            self.update_plot()
            print("cut")
        except Exception as e:
            print(f"=== cutting failed: {e}")


    #def reverb(self):
        #try:
            #if not self.imported:
                #return

            #delay, ok_pressed = QInputDialog.getDouble(self, "Ревербация",
                                                               #f"Введите длину ревербации(в секундах, от 0 до 2 секунд)",
                                                               #0.01, 0.01, 2.00, 2)
            #if not ok_pressed:
                #return
            
            #decay, ok_pressed = QInputDialog.getDouble(self, "Ревербация",
                                                                #f"Введите значение затухания(от 0.01 до 0.99)",
                                                                #0.01, 0.01, 0.99, 2)
            #if not ok_pressed:
                #return
            
            #self.audio_prev = self.audio
            #self.sr_prev = self.sr

            #impulse = np.zeros(max(1, int(self.sr * delay)))
            #impulse[0] = 1.0

            #for i in range(1, len(impulse)):
                #impulse[i] = decay * impulse[i - 1]

            #self.audio = np.convolve(self.audio, impulse, mode='same')
            #self.audio = lbs.util.normalize(self.audio)
            
            #self.change_volume(self.audio, self.volume_sl.value())
            

            #impulse = np.zeros(int(self.tmp_sr * delay))
            #impulse[0] = 1.0

            #for i in range(1, len(impulse)):
                #impulse[i] = decay * impulse[i - 1]

            #self.tmp_audio = np.convolve(self.tmp_audio, impulse, mode='same')
            #self.tmp_audio = lbs.util.normalize(self.tmp_audio)
            
            #self.change_volume(self.tmp_audio, self.volume_sl.value())
            
            #self.update_plot()
            #print("reverbed")
        #except Exception as e:
            #print(f"=== reverbing failed: {e}")


    def reverse(self):
        try:
            if not self.imported:
                return
            
            self.audio_prev = self.audio

            audio_pd = self.librosa_to_pydub(self.audio, self.sr)

            audio_pd = audio_pd.reverse()

            self.audio, self.sr = self.pydub_to_librosa(audio_pd)
            self.change_volume(self.audio, self.volume_sl.value())


            audio_tmp_pd = self.librosa_to_pydub(self.tmp_audio, self.tmp_sr)

            audio_tmp_pd = audio_tmp_pd.reverse()

            self.tmp_audio, self.tmp_sr = self.pydub_to_librosa(audio_tmp_pd)
            self.change_volume(self.tmp_audio, self.volume_sl.value())

            self.update_plot()
            print("reversed")
        except Exception as e:
            print(f"=== reversing failed: {e}")


    def fade_in(self):
        try:
            if not self.imported:
                return
            
            seconds_first, ok_pressed = QInputDialog.getDouble(self, "Возрастание",
                                                               f"Введите начальную позицию возрастания(в секундах, от 0 до {round(self.get_current_duration(), 2)} секунд)",
                                                               0, 0, self.get_current_duration(), 2)
            if not ok_pressed:
                return
            seconds_second, ok_pressed = QInputDialog.getDouble(self, "Возрастание",
                                                                f"Введите конечную позицию возрастания(в секундах, от {seconds_first} до {round(self.get_current_duration(), 2)} секунд)",
                                                                self.current_position / self.sr, seconds_first, self.get_current_duration(), 2)
            if not ok_pressed:
                return
            
            print(seconds_first)
            print(seconds_second)
            
            self.audio_prev = self.audio #делаем бэкап
            
            audio_pd = self.librosa_to_pydub(self.audio, self.sr) #конверируем librosa файл в pydub

            before_fade = audio_pd[:seconds_first]
            after_fade = audio_pd[seconds_first:]

            after_fade = after_fade.fade_in(int(seconds_second - seconds_first) * 1000)

            audio_pd = before_fade + after_fade

            self.audio, self.sr = self.pydub_to_librosa(audio_pd) #конверируем обратно
            self.change_volume(self.audio, self.volume_sl.value())


            audio_tmp_pd = self.librosa_to_pydub(self.tmp_audio, self.tmp_sr) #конверируем librosa файл в pydub

            before_fade_tmp = audio_tmp_pd[:seconds_first]
            after_fade_tmp = audio_tmp_pd[seconds_first:]

            after_fade_tmp= after_fade_tmp.fade_in(int(seconds_second - seconds_first) * 1000)

            audio_tmp_pd = before_fade_tmp + after_fade_tmp

            self.tmp_audio, self.tmp_sr = self.pydub_to_librosa(audio_tmp_pd) #конверируем обратно
            self.change_volume(self.tmp_audio, self.volume_sl.value())

            self.update_plot() #обновляем график
            print("faded in")
        except Exception as e:
            print(f"=== fading in failed: {e}")


    def fade_out(self):
        try:
            if not self.imported:
                return
            
            seconds_first, ok_pressed = QInputDialog.getDouble(self, "Затухание",
                                                               f"Введите начальную позицию затухания(в секундах, от 0 до {round(self.get_current_duration(), 2)} секунд)",
                                                               self.current_position / self.sr, 0, self.get_current_duration(), 2)
            if not ok_pressed:
                return
            seconds_second, ok_pressed = QInputDialog.getDouble(self, "Затухание",
                                                                f"Введите конечную позицию затухания(в секундах, от {seconds_first} до {round(self.get_current_duration(), 2)} секунд)",
                                                                seconds_first, seconds_first, self.get_current_duration(), 2)
            if not ok_pressed:
                return

            self.audio_prev = self.audio #делаем бэкап
            
            audio_pd = self.librosa_to_pydub(self.audio, self.sr) #конверируем librosa файл в pydub

            before_fade = audio_pd[:seconds_first]
            after_fade = audio_pd[seconds_first:]

            after_fade = after_fade.fade_out(int(seconds_second - seconds_first) * 1000)

            audio_pd = before_fade + after_fade

            self.audio, self.sr = self.pydub_to_librosa(audio_pd) #конверируем обратно
            self.change_volume(self.audio, self.volume_sl.value())


            audio_tmp_pd = self.librosa_to_pydub(self.tmp_audio, self.tmp_sr) #конверируем librosa файл в pydub

            before_fade_tmp = audio_tmp_pd[:seconds_first]
            after_fade_tmp = audio_tmp_pd[seconds_first:]

            after_fade_tmp = after_fade_tmp.fade_out(int(seconds_second - seconds_first) * 1000)

            audio_tmp_pd = before_fade_tmp + after_fade_tmp

            self.tmp_audio, self.tmp_sr = self.pydub_to_librosa(audio_tmp_pd) #конверируем обратно
            self.change_volume(self.tmp_audio, self.volume_sl.value())

            self.update_plot() #обновляем график
            print("faded out")
        except Exception as e:
            print(f"=== fading out failed: {e}")


    def change_volume(self, audio, decibels):
        try:    
            current_dbfs = self.get_current_volume(audio) #получаем нынешнюю громкость
            
            gain_db = decibels - current_dbfs #считаем сколько надо добавить
            gain_linear = 10 ** (gain_db / 20)
            audio *= gain_linear #меняем громкость
            
            print("changed volume")
            return audio
        except Exception as e:
            print(f"=== changing volume failed: {e}")


    def apply_audio_effects(self, semitones, speed):
        try:
            if not self.imported:
                return
            
            audio_pd = self.librosa_to_pydub(self.tmp_audio, self.tmp_sr) #конверируем librosa файл в pydub

            print(f"speed {round(speed / 100, 2)}")
            #audio_pd = audio_pd.speedup(playback_speed=round(speed / 100, 2))

            new_sr = int(audio_pd.frame_rate * (2.0 ** (semitones / 12.0))) #высота
            
            new_sr = int(new_sr * round(speed / 100, 2)) #скорость
                    
            audio_pd = audio_pd._spawn(audio_pd.raw_data, overrides={'frame_rate': new_sr})

            self.audio, self.sr = self.pydub_to_librosa(audio_pd) #конверируем обратно
            self.change_volume(self.audio, self.volume_sl.value())

            print("applied audio effects")
        except Exception as e:
            print(f"=== applying audio effects failed: {e}")


    #===============диалоговые окна================


    def volume_sl_changed(self):
        try:
            if not self.imported:
                return
            
            self.pause()

            self.loading_image.setHidden(False)

            self.audio_prev = self.audio #делаем бэкап
            
            self.change_volume(self.audio, self.volume_sl.value())
            
            self.update_plot() #обновляем график

            self.loading_image.setHidden(True)

            print("connected volume slider value")
        except Exception as e:
            print(f"=== connecting volume slider value failed: {e}")


    def volume_dialog(self):
        try:
            if not self.imported:
                return
            
            decibels, ok_pressed = QInputDialog.getInt(self, "Изменение громкости",
                                                       "Введите новое значение громкости(от -60 до 20 дб)", int(self.get_current_volume(self.audio)), -60, 20)

            self.loading_image.setHidden(False)

            self.pause()
                        
            self.audio_prev = self.audio #делаем бэкап
            
            self.change_volume(self.audio, decibels)

            self.volume_sl.setValue(decibels)
            self.update_plot() #обновляем график

            self.loading_image.setHidden(True)
                
            print("opened volume dialog")
        except Exception as e:
            print(f"=== opening volume dialog failed: {e}")


    def pitch_sl_changed(self):
        try:
            if not self.imported:
                return
            
            self.loading_image.setHidden(False)
            
            self.pause()

            self.audio_prev = self.audio #делаем бэкап
            self.sr_prev = self.sr

            self.pitch_prev = self.pitch

            #self.apply_audio_effects(self.pitch, 100, True)
            self.apply_audio_effects(self.pitch_sl.value(), self.speed)
            
            self.pitch = self.pitch_sl.value()
            
            self.update_plot() #обновляем график

            self.loading_image.setHidden(True)
            
            print(self.pitch_sl.value())
            print("connected pitch slider value")
        except Exception as e:
            print(f"=== connecting pitch slider value failed: {e}")


    def pitch_dialog(self):
        try:
            if not self.imported:
                return
            
            if self.pitch != 0:
                semitones, ok_pressed = QInputDialog.getInt(self, "Изменение высоты",
                                                            "Введите, на сколько изменится значение высоты(от -12 до 12 полутонов)", self.pitch, -12, 12)
            else:
                semitones, ok_pressed = QInputDialog.getInt(self, "Изменение высоты",
                                                            "Введите, на сколько изменится значение высоты(от -12 до 12 полутонов)", 0, -12, 12)

            self.loading_image.setHidden(False)

            self.pause()
                        
            self.audio_prev = self.audio #делаем бэкап
            self.sr_prev = self.sr

            self.pitch_prev = self.pitch

            #self.apply_audio_effects(self.pitch, 100, True)
            self.apply_audio_effects(semitones, self.speed)

            self.pitch = semitones

            self.pitch_sl.setValue(semitones)
            self.update_plot() #обновляем график

            self.loading_image.setHidden(True)
            
            print("opened pitch dialog")
        except Exception as e:
            print(f"=== opening pitch dialog failed: {e}")


    def speed_sl_changed(self):
        try:
            if not self.imported:
                return
            
            self.loading_image.setHidden(False)
        
            self.pause()

            self.audio_prev = self.audio #делаем бэкап
            self.sr_prev = self.sr

            self.speed_prev = self.speed
            
            #self.apply_audio_effects(0, self.speed, True)
            self.apply_audio_effects(self.pitch, self.speed_sl.value())
            
            self.speed = self.speed_sl.value()
            
            self.update_plot() #обновляем график

            self.loading_image.setHidden(True)
            
            print(self.speed_sl.value())
            print("connected speed slider value")
        except Exception as e:
            print(f"=== connecting speed slider value failed: {e}")


    def speed_dialog(self):
        try:
            if not self.imported:
                return
            
            if self.speed != 100:
                speed, ok_pressed = QInputDialog.getInt(self, "Изменение скорости",
                                                        "Введите, во сколько раз измениться значение скорости(в процентах, от 50% до 200%)", self.speed, 50, 200)
            else:
                speed, ok_pressed = QInputDialog.getInt(self, "Изменение скорости",
                                                        "Введите, во сколько раз измениться значение скорости(в процентах, от 50% до 200%)", 100, 50, 200)

            self.loading_image.setHidden(False)

            self.pause()
                        
            self.audio_prev = self.audio #делаем бэкап
            self.sr_prev = self.sr
            
            self.speed_prev = self.speed

            #self.apply_audio_effects(0, self.speed, True)
            self.apply_audio_effects(self.pitch, speed)

            self.speed = speed

            self.speed_sl.setValue(speed)
            self.update_plot() #обновляем график

            self.loading_image.setHidden(True)
            
            print(self.speed)
            print("opened speed dialog")
        except Exception as e:
            print(f"=== opening speed dialog failed: {e}")


if (__name__ == '__main__'):
    app = QApplication(sys.argv)
    ex = AudioEditor(False)
    ex.show()
    sys.exit(app.exec())
