import os
import sys
import math
import time
import shutil

# Qt compatibility layer for PyQt6, PySide6, and PyQt5
QT_AVAILABLE = False
QT_LIB = None

try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
        QStackedWidget, QSpinBox, QComboBox, QFileDialog, QGraphicsDropShadowEffect,
        QDialog, QLineEdit, QMessageBox
    )
    from PyQt6.QtCore import Qt, QTimer, QPoint, QRectF
    from PyQt6.QtGui import (
        QPainter, QPixmap, QColor, QLinearGradient, QPainterPath, QPen, QFont
    )
    QT_AVAILABLE = True
    QT_LIB = "PyQt6"
    
    # Enum aliases for PyQt6
    ALIGN_LEFT = Qt.AlignmentFlag.AlignLeft
    ALIGN_RIGHT = Qt.AlignmentFlag.AlignRight
    ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
    WINDOW_FLAGS = (
        Qt.WindowType.FramelessWindowHint |
        Qt.WindowType.WindowStaysOnTopHint |
        Qt.WindowType.Tool
    )
    WA_TRANSLUCENT = Qt.WidgetAttribute.WA_TranslucentBackground
    ANTIALIASING = QPainter.RenderHint.Antialiasing
    CURSOR_POINTER = Qt.CursorShape.PointingHandCursor

except ImportError:
    try:
        from PySide6.QtWidgets import (
            QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
            QStackedWidget, QSpinBox, QComboBox, QFileDialog, QGraphicsDropShadowEffect,
            QDialog, QLineEdit, QMessageBox
        )
        from PySide6.QtCore import Qt, QTimer, QPoint, QRectF
        from PySide6.QtGui import (
            QPainter, QPixmap, QColor, QLinearGradient, QPainterPath, QPen, QFont
        )
        QT_AVAILABLE = True
        QT_LIB = "PySide6"
        
        ALIGN_LEFT = Qt.AlignmentFlag.AlignLeft
        ALIGN_RIGHT = Qt.AlignmentFlag.AlignRight
        ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
        WINDOW_FLAGS = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        WA_TRANSLUCENT = Qt.WidgetAttribute.WA_TranslucentBackground
        ANTIALIASING = QPainter.RenderHint.Antialiasing
        CURSOR_POINTER = Qt.CursorShape.PointingHandCursor

    except ImportError:
        try:
            from PyQt5.QtWidgets import (
                QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
                QStackedWidget, QSpinBox, QComboBox, QFileDialog, QGraphicsDropShadowEffect,
                QDialog, QLineEdit, QMessageBox
            )
            from PyQt5.QtCore import Qt, QTimer, QPoint, QRectF
            from PyQt5.QtGui import (
                QPainter, QPixmap, QColor, QLinearGradient, QPainterPath, QPen, QFont
            )
            QT_AVAILABLE = True
            QT_LIB = "PyQt5"
            
            ALIGN_LEFT = Qt.AlignLeft
            ALIGN_RIGHT = Qt.AlignRight
            ALIGN_CENTER = Qt.AlignCenter
            WINDOW_FLAGS = (
                Qt.FramelessWindowHint |
                Qt.WindowStaysOnTopHint |
                Qt.Tool
            )
            WA_TRANSLUCENT = Qt.WA_TranslucentBackground
            ANTIALIASING = QPainter.Antialiasing
            CURSOR_POINTER = Qt.PointingHandCursor

        except ImportError:
            QT_AVAILABLE = False
            QT_LIB = None

import threading
from config import (
    FRAMES_DIR, SMOKE_DIR, SOUNDS_DIR, AUDIO_FILE, CHARACTERS_DIR, load_config, save_config,
    record_glass_drank, get_audio_file_path, list_available_sounds,
    list_available_characters, get_active_character_id, get_character_frames_dir,
    get_character_metadata, set_active_character, delete_custom_character
)
from audio import SoundPlayer
from video_processor import process_video_character


if QT_AVAILABLE:
    class QtSpeechBubble(QWidget):
        """Speech bubble widget with custom QPainter drawing and pointer tail."""
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAttribute(WA_TRANSLUCENT)
            self.tail_w = 14
            self.tail_h = 18
            self.radius = 16

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(ANTIALIASING)

            w = self.width()
            h = self.height()
            bubble_w = max(10, w - self.tail_w)
            bubble_h = h
            tail_y = min(max(30, bubble_h * 0.42), max(30, bubble_h - self.tail_h - 18))

            path = QPainterPath()
            r = self.radius

            # Start top-left
            path.moveTo(r, 0)
            path.lineTo(bubble_w - r, 0)
            path.quadTo(bubble_w, 0, bubble_w, r)

            # Right edge with pointer tail
            path.lineTo(bubble_w, tail_y)
            path.lineTo(bubble_w + self.tail_w, tail_y + self.tail_h / 2.0)
            path.lineTo(bubble_w, tail_y + self.tail_h)

            path.lineTo(bubble_w, bubble_h - r)
            path.quadTo(bubble_w, bubble_h, bubble_w - r, bubble_h)
            path.lineTo(r, bubble_h)
            path.quadTo(0, bubble_h, 0, bubble_h - r)
            path.lineTo(0, r)
            path.quadTo(0, 0, r, 0)
            path.closeSubpath()

            # Frosted glass gradient
            gradient = QLinearGradient(0, 0, bubble_w, bubble_h)
            gradient.setColorAt(0.0, QColor(255, 255, 255, 250))
            gradient.setColorAt(1.0, QColor(238, 246, 255, 245))

            painter.setBrush(gradient)
            pen = QPen(QColor(0, 122, 242, 75))
            pen.setWidthF(1.8)
            painter.setPen(pen)

            painter.drawPath(path)


    class DynamicStackedWidget(QStackedWidget):
        """Stacked widget that dynamically resizes to fit only the current visible widget."""
        def sizeHint(self):
            cur = self.currentWidget()
            if cur:
                return cur.sizeHint()
            return super().sizeHint()

        def minimumSizeHint(self):
            cur = self.currentWidget()
            if cur:
                return cur.minimumSizeHint()
            return super().minimumSizeHint()


    class QtWaterReminderOverlay(QWidget):
        def __init__(self, on_action_callback=None):
            self._app = QApplication.instance()
            if not self._app:
                self._app = QApplication(sys.argv if hasattr(sys, "argv") else [])
            super().__init__()
            self.on_action_callback = on_action_callback
            self.config = load_config()
            self.sound_player = SoundPlayer(get_audio_file_path(self.config))
            self.combo_audio = None
            self.btn_preview_audio = None
            self.preview_reset_timer = None

            # Window configuration
            self.setWindowTitle("Water Reminder")
            self.setWindowFlags(WINDOW_FLAGS)
            self.setAttribute(WA_TRANSLUCENT)

            # Character & UI state
            self.combo_char = None
            self.btn_del_char = None
            self.btn_add_char = None
            self.lbl_char_progress = None
            self.char_meta = None
            self.frame_interval_ms = 50
            self.loop_start = 0

            # Frames & Animation state
            self.char_frames = []
            self.smoke_frames = []
            self.current_frame_idx = 0
            self.smoke_frame_idx = 0
            self.is_closing = False

            # Timers
            self.anim_timer = QTimer(self)
            self.anim_timer.timeout.connect(self.on_anim_tick)

            self.smoke_timer = QTimer(self)
            self.smoke_timer.timeout.connect(self.on_smoke_tick)

            self.auto_hide_timer = QTimer(self)
            self.auto_hide_timer.setSingleShot(True)
            self.auto_hide_timer.timeout.connect(lambda: self.hide_overlay(animated=True))

            self.load_frames()
            self.build_ui()

        def load_frames(self, character_id=None):
            self.char_frames = []
            self.config = load_config()
            self.char_meta = get_character_metadata(character_id, self.config)
            self.frame_interval_ms = self.char_meta.get("frame_interval_ms", 50)
            self.loop_start = self.char_meta.get("loop_start", 0)

            frames_dir = get_character_frames_dir(character_id, self.config)
            if os.path.exists(frames_dir):
                files = sorted([f for f in os.listdir(frames_dir) if f.startswith("f_") and f.endswith(".png")])
                for f in files:
                    p = os.path.join(frames_dir, f)
                    pix = QPixmap(p)
                    if not pix.isNull():
                        self.char_frames.append(pix)

            # Fallback to default Hydro Buddy frames if empty
            if not self.char_frames and frames_dir != FRAMES_DIR and os.path.exists(FRAMES_DIR):
                self.char_meta = get_character_metadata("default", self.config)
                self.loop_start = 150
                self.frame_interval_ms = 50
                files = sorted([f for f in os.listdir(FRAMES_DIR) if f.startswith("f_") and f.endswith(".png")])
                for f in files:
                    pix = QPixmap(os.path.join(FRAMES_DIR, f))
                    if not pix.isNull():
                        self.char_frames.append(pix)

            # Load closing smoke frames
            if not self.smoke_frames and os.path.exists(SMOKE_DIR):
                smoke_files = sorted([f for f in os.listdir(SMOKE_DIR) if f.startswith("close_anim_") and f.endswith(".png")])
                for f in smoke_files:
                    p = os.path.join(SMOKE_DIR, f)
                    pix = QPixmap(p)
                    if not pix.isNull():
                        self.smoke_frames.append(pix)

            if hasattr(self, "char_label") and self.char_frames:
                self.char_label.setPixmap(self.char_frames[0])

        def reload_character(self, character_id=None):
            self.load_frames(character_id)
            self.current_frame_idx = 0
            if self.char_frames and hasattr(self, "char_label"):
                self.char_label.setPixmap(self.char_frames[0])
            if self.anim_timer.isActive():
                self.anim_timer.stop()
                self.anim_timer.start(self.frame_interval_ms)

        def build_ui(self):
            main_layout = QHBoxLayout(self)
            main_layout.setContentsMargins(10, 10, 10, 10)
            main_layout.setSpacing(6)

            # Speech bubble container
            self.bubble = QtSpeechBubble()
            self.bubble.setFixedWidth(330)

            bubble_inner = QVBoxLayout(self.bubble)
            bubble_inner.setContentsMargins(14, 16, 22, 14)
            bubble_inner.setSpacing(8)

            # Stack for prompt, drank selection, settings, and feedback
            self.stack = DynamicStackedWidget()
            self.stack.currentChanged.connect(lambda idx: (self.stack.updateGeometry(), self.bubble.updateGeometry(), self.adjustSize()))

            self.view_prompt = self.create_prompt_view()
            self.stack.addWidget(self.view_prompt)

            self.view_drank = self.create_drank_view()
            self.stack.addWidget(self.view_drank)

            self.view_settings = self.create_settings_view()
            self.stack.addWidget(self.view_settings)

            self.view_feedback = self.create_feedback_view()
            self.stack.addWidget(self.view_feedback)

            bubble_inner.addWidget(self.stack)

            # Character image label
            self.char_label = QLabel()
            self.char_label.setFixedSize(270, 480)
            self.char_label.setAttribute(WA_TRANSLUCENT)
            if self.char_frames:
                self.char_label.setPixmap(self.char_frames[0])

            # Layout: Bubble on left, character on right
            bubble_container = QVBoxLayout()
            bubble_container.addSpacing(45)
            bubble_container.addWidget(self.bubble)
            bubble_container.addStretch()

            main_layout.addLayout(bubble_container)
            main_layout.addWidget(self.char_label)

            # Set pointer cursor for all buttons and action buttons
            for btn in self.findChildren(QPushButton):
                btn.setCursor(CURSOR_POINTER)

        def create_prompt_view(self):
            w = QWidget()
            layout = QVBoxLayout(w)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

            # Header row
            header = QHBoxLayout()
            title = QLabel("💧 Drink Water Reminder!")
            title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0b4f9c;")
            header.addWidget(title)

            self.badge_label = QLabel(f"Today: {self.config.get('glasses_today', 0)} 🥛")
            self.badge_label.setStyleSheet(
                "background-color: rgba(0, 150, 255, 0.12); color: #0277bd; "
                "font-size: 11px; font-weight: 700; border-radius: 8px; padding: 2px 6px;"
            )
            header.addWidget(self.badge_label, 0, ALIGN_RIGHT)

            self.btn_gear = QPushButton("⚙️")
            self.btn_gear.setToolTip("Customize Audio & Settings")
            self.btn_gear.setCursor(CURSOR_POINTER)
            self.btn_gear.setStyleSheet(
                "QPushButton { background: rgba(0, 150, 255, 0.12); color: #0277bd; "
                "font-size: 13px; font-weight: 700; border-radius: 8px; padding: 2px 7px; "
                "border: 1px solid rgba(0, 150, 255, 0.25); } "
                "QPushButton:hover { background: rgba(0, 150, 255, 0.25); color: #01579b; }"
            )
            self.btn_gear.clicked.connect(self.open_settings_view)
            header.addWidget(self.btn_gear, 0, ALIGN_RIGHT)
            layout.addLayout(header)

            sub = QLabel("Time to hydrate! Grab a glass of water to keep your body energized and sharp.")
            sub.setWordWrap(True)
            sub.setStyleSheet("font-size: 12px; color: #455a64;")
            layout.addWidget(sub)

            btn_drank = QPushButton("✅ Yes, I Drank Water")
            btn_drank.setStyleSheet(
                "QPushButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00b0ff, stop:1 #0066fe); "
                "color: white; font-size: 13px; font-weight: 700; border-radius: 11px; padding: 8px 14px; border: none; } "
                "QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #38c5ff, stop:1 #0050cc); }"
            )
            btn_drank.clicked.connect(self.on_click_drank)
            layout.addWidget(btn_drank)

            snooze_mins = self.config.get("snooze_minutes", 10)
            btn_snooze = QPushButton(f"⏰ Snooze ({snooze_mins} mins)")
            btn_snooze.setStyleSheet(
                "QPushButton { background: rgba(225, 235, 245, 0.95); color: #37474f; "
                "font-size: 12px; font-weight: 600; border-radius: 11px; padding: 7px 12px; "
                "border: 1px solid rgba(0, 0, 0, 0.08); } "
                "QPushButton:hover { background: rgba(210, 225, 240, 1); color: #212121; }"
            )
            btn_snooze.clicked.connect(self.on_click_snooze)
            layout.addWidget(btn_snooze)

            footer = QHBoxLayout()
            btn_settings = QPushButton("⚙️ Settings & Audio")
            btn_settings.setStyleSheet("background: transparent; color: #78909c; font-size: 11px; font-weight: 600; border: none;")
            btn_settings.clicked.connect(self.open_settings_view)
            footer.addWidget(btn_settings)

            btn_close = QPushButton("✕ Close")
            btn_close.setStyleSheet("background: transparent; color: #78909c; font-size: 11px; font-weight: 600; border: none;")
            btn_close.clicked.connect(self.on_click_dismiss)
            footer.addWidget(btn_close, 0, ALIGN_RIGHT)

            layout.addLayout(footer)
            return w

        def create_drank_view(self):
            w = QWidget()
            layout = QVBoxLayout(w)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

            title = QLabel("🎉 Great job staying hydrated!")
            title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0b4f9c;")
            layout.addWidget(title)

            sub = QLabel("When should I remind you to drink water next?")
            sub.setWordWrap(True)
            sub.setStyleSheet("font-size: 12px; color: #455a64;")
            layout.addWidget(sub)

            row = QHBoxLayout()
            pill_style = (
                "QPushButton { background: white; color: #0277bd; font-size: 11px; font-weight: 600; "
                "border-radius: 9px; padding: 6px 8px; border: 1px solid rgba(2, 119, 189, 0.3); } "
                "QPushButton:hover { background: #e1f5fe; }"
            )

            for mins, label in [(30, "30 Mins"), (60, "1 Hour"), (90, "1.5 Hours"), (120, "2 Hours")]:
                btn = QPushButton(label)
                btn.setStyleSheet(pill_style)
                btn.clicked.connect(lambda checked, m=mins: self.confirm_next_interval(m))
                row.addWidget(btn)
            layout.addLayout(row)

            # Custom duration row: Hours & Minutes
            custom_row = QHBoxLayout()
            lbl_c = QLabel("Custom:")
            lbl_c.setStyleSheet("font-size: 12px; color: #455a64;")
            custom_row.addWidget(lbl_c)

            self.spin_hours = QSpinBox()
            self.spin_hours.setRange(0, 12)
            self.spin_hours.setValue(1)
            self.spin_hours.setStyleSheet("background: white; color: #0b4f9c; font-weight: 700; border: 1px solid rgba(0, 122, 242, 0.35); border-radius: 6px; padding: 2px;")
            custom_row.addWidget(self.spin_hours)

            lbl_h = QLabel("hr")
            lbl_h.setStyleSheet("font-size: 11px; color: #455a64;")
            custom_row.addWidget(lbl_h)

            self.spin_mins = QSpinBox()
            self.spin_mins.setRange(0, 55)
            self.spin_mins.setSingleStep(5)
            self.spin_mins.setValue(0)
            self.spin_mins.setStyleSheet("background: white; color: #0b4f9c; font-weight: 700; border: 1px solid rgba(0, 122, 242, 0.35); border-radius: 6px; padding: 2px;")
            custom_row.addWidget(self.spin_mins)

            lbl_m = QLabel("min")
            lbl_m.setStyleSheet("font-size: 11px; color: #455a64;")
            custom_row.addWidget(lbl_m)

            btn_set = QPushButton("Set")
            btn_set.setStyleSheet(pill_style)
            btn_set.clicked.connect(self.on_qt_custom_interval_set)
            custom_row.addWidget(btn_set)
            layout.addLayout(custom_row)

            btn_back = QPushButton("← Back")
            btn_back.setStyleSheet("background: transparent; color: #78909c; font-size: 11px; font-weight: 600; border: none;")
            btn_back.clicked.connect(lambda: self.stack.setCurrentWidget(self.view_prompt))
            layout.addWidget(btn_back, 0, ALIGN_LEFT)

            return w

        def on_qt_custom_interval_set(self):
            h = self.spin_hours.value()
            m = self.spin_mins.value()
            total = (h * 60) + m
            if total <= 0:
                total = 15
            self.confirm_next_interval(total)

        def create_settings_view(self):
            w = QWidget()
            layout = QVBoxLayout(w)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)

            title = QLabel("⚙️ Settings & Audio")
            title.setStyleSheet("font-size: 14px; font-weight: 800; color: #0b4f9c;")
            layout.addWidget(title)

            lbl_int = QLabel("Default Interval:")
            lbl_int.setStyleSheet("font-size: 11px; font-weight: 600; color: #455a64;")
            layout.addWidget(lbl_int)

            row = QHBoxLayout()
            pill_style = (
                "QPushButton { background: white; color: #0277bd; font-size: 11px; font-weight: 600; "
                "border-radius: 8px; padding: 4px 6px; border: 1px solid rgba(2, 119, 189, 0.3); } "
                "QPushButton:hover { background: #e1f5fe; }"
            )
            for mins in [30, 45, 60, 90, 120]:
                btn = QPushButton(f"{mins}m")
                btn.setStyleSheet(pill_style)
                btn.clicked.connect(lambda checked, m=mins: self.set_default_interval(m))
                row.addWidget(btn)
            layout.addLayout(row)

            # Row: Startup Delay (after system boot)
            lbl_boot = QLabel("⏱️ Start After System Boot:")
            lbl_boot.setStyleSheet("font-size: 11px; font-weight: 600; color: #455a64; margin-top: 4px;")
            layout.addWidget(lbl_boot)

            boot_row = QHBoxLayout()
            for bmins, blabel in [(0, "0m (Off)"), (15, "15m"), (30, "30m"), (45, "45m"), (60, "60m")]:
                btn = QPushButton(blabel)
                btn.setStyleSheet(pill_style)
                btn.clicked.connect(lambda checked, m=bmins: self.set_startup_delay_duration(m))
                boot_row.addWidget(btn)
            layout.addLayout(boot_row)

            # Audio customization section
            lbl_snd = QLabel("🔔 Reminder Alert Sound:")
            lbl_snd.setStyleSheet("font-size: 11px; font-weight: 600; color: #455a64; margin-top: 4px;")
            layout.addWidget(lbl_snd)

            # Audio dropdown + preview button row
            audio_row = QHBoxLayout()
            self.combo_audio = QComboBox()
            self.combo_audio.setCursor(CURSOR_POINTER)
            self.combo_audio.setStyleSheet(
                "QComboBox { background: white; color: #0b4f9c; font-size: 11px; font-weight: 600; "
                "border: 1px solid rgba(0, 122, 242, 0.35); border-radius: 8px; padding: 4px 8px; } "
                "QComboBox:hover { border-color: #007af2; } "
                "QComboBox QAbstractItemView { background: white; color: #1e293b; "
                "selection-background-color: #e1f5fe; selection-color: #0b4f9c; }"
            )
            self.combo_audio.currentIndexChanged.connect(self.on_qt_audio_combo_changed)
            audio_row.addWidget(self.combo_audio, 1)

            self.btn_preview_audio = QPushButton("▶ Play")
            self.btn_preview_audio.setCursor(CURSOR_POINTER)
            self.btn_preview_audio.setStyleSheet(
                "QPushButton { background: #e0f2fe; color: #0284c7; font-size: 11px; font-weight: 700; "
                "border: 1px solid #7dd3fc; border-radius: 8px; padding: 4px 10px; } "
                "QPushButton:hover { background: #bae6fd; color: #0369a1; }"
            )
            self.btn_preview_audio.clicked.connect(self.on_click_preview_audio)
            audio_row.addWidget(self.btn_preview_audio)
            layout.addLayout(audio_row)

            # Action buttons row: Add Audio File & Sound Toggle
            btn_row = QHBoxLayout()
            self.btn_add_audio = QPushButton("📁 Add Audio...")
            self.btn_add_audio.setCursor(CURSOR_POINTER)
            self.btn_add_audio.setStyleSheet(
                "QPushButton { background: white; color: #0277bd; font-size: 11px; font-weight: 600; "
                "border-radius: 8px; padding: 5px 8px; border: 1px dashed rgba(2, 119, 189, 0.5); } "
                "QPushButton:hover { background: #f0f9ff; border-style: solid; }"
            )
            self.btn_add_audio.clicked.connect(self.on_click_add_custom_audio)
            btn_row.addWidget(self.btn_add_audio, 1)

            sound_on = self.config.get("sound_enabled", True)
            self.btn_sound = QPushButton(f"🔊 Sound: {'ON' if sound_on else 'OFF'}")
            self.btn_sound.setCursor(CURSOR_POINTER)
            self.btn_sound.setStyleSheet(
                "QPushButton { background: rgba(225, 235, 245, 0.95); color: #37474f; "
                "font-size: 11px; font-weight: 600; border-radius: 8px; padding: 5px 8px; "
                "border: 1px solid rgba(0, 0, 0, 0.08); } "
                "QPushButton:hover { background: rgba(210, 225, 240, 1); }"
            )
            self.btn_sound.clicked.connect(self.toggle_sound)
            btn_row.addWidget(self.btn_sound, 1)
            layout.addLayout(btn_row)

            # Character customization section
            lbl_char = QLabel("👤 Animated Character:")
            lbl_char.setStyleSheet("font-size: 11px; font-weight: 600; color: #455a64; margin-top: 4px;")
            layout.addWidget(lbl_char)

            char_row = QHBoxLayout()
            self.combo_char = QComboBox()
            self.combo_char.setCursor(CURSOR_POINTER)
            self.combo_char.setStyleSheet(
                "QComboBox { background: white; color: #0b4f9c; font-size: 11px; font-weight: 600; "
                "border: 1px solid rgba(0, 122, 242, 0.35); border-radius: 8px; padding: 4px 8px; } "
                "QComboBox:hover { border-color: #007af2; } "
                "QComboBox QAbstractItemView { background: white; color: #1e293b; "
                "selection-background-color: #e1f5fe; selection-color: #0b4f9c; }"
            )
            self.combo_char.currentIndexChanged.connect(self.on_qt_char_combo_changed)
            char_row.addWidget(self.combo_char, 1)

            self.btn_del_char = QPushButton("🗑️")
            self.btn_del_char.setToolTip("Delete selected custom character")
            self.btn_del_char.setCursor(CURSOR_POINTER)
            self.btn_del_char.setStyleSheet(
                "QPushButton { background: white; color: #d32f2f; font-size: 11px; font-weight: 600; "
                "border: 1px solid rgba(211, 47, 47, 0.3); border-radius: 8px; padding: 4px 8px; } "
                "QPushButton:hover { background: #ffebee; }"
            )
            self.btn_del_char.clicked.connect(self.on_click_delete_character)
            char_row.addWidget(self.btn_del_char)
            layout.addLayout(char_row)

            # Upload Character Video Button
            char_act_row = QHBoxLayout()
            self.btn_add_char = QPushButton("🎬 Upload Video Character...")
            self.btn_add_char.setCursor(CURSOR_POINTER)
            self.btn_add_char.setStyleSheet(
                "QPushButton { background: white; color: #0277bd; font-size: 11px; font-weight: 600; "
                "border-radius: 8px; padding: 5px 8px; border: 1px dashed rgba(2, 119, 189, 0.5); } "
                "QPushButton:hover { background: #f0f9ff; border-style: solid; }"
            )
            self.btn_add_char.clicked.connect(self.on_click_add_custom_character)
            char_act_row.addWidget(self.btn_add_char)
            layout.addLayout(char_act_row)

            self.lbl_char_progress = QLabel("")
            self.lbl_char_progress.setWordWrap(True)
            self.lbl_char_progress.setStyleSheet("font-size: 10px; color: #0277bd; font-weight: 600;")
            self.lbl_char_progress.hide()
            layout.addWidget(self.lbl_char_progress)

            # Populate combos
            self.populate_sound_options()
            self.populate_character_options()

            btn_back = QPushButton("← Back")
            btn_back.setStyleSheet("background: transparent; color: #78909c; font-size: 11px; font-weight: 600; border: none;")
            btn_back.clicked.connect(lambda: self.stack.setCurrentWidget(self.view_prompt))
            layout.addWidget(btn_back, 0, ALIGN_LEFT)

            return w

        def open_settings_view(self):
            self.config = load_config()
            sound_on = self.config.get("sound_enabled", True)
            if hasattr(self, "btn_sound") and self.btn_sound:
                self.btn_sound.setText(f"🔊 Sound: {'ON' if sound_on else 'OFF'}")
            self.populate_sound_options()
            self.populate_character_options()
            self.stack.setCurrentWidget(self.view_settings)

        def populate_character_options(self):
            if not self.combo_char:
                return
            self.combo_char.blockSignals(True)
            self.combo_char.clear()

            chars = list_available_characters(self.config)
            cur_char = get_active_character_id(self.config)
            active_idx = 0
            for idx, c in enumerate(chars):
                self.combo_char.addItem(c["name"], c["id"])
                if c["id"] == cur_char:
                    active_idx = idx

            self.combo_char.setCurrentIndex(active_idx)
            self.combo_char.blockSignals(False)
            if hasattr(self, "btn_del_char") and self.btn_del_char:
                self.btn_del_char.setEnabled(cur_char != "default")

        def on_qt_char_combo_changed(self, index):
            if index < 0 or not self.combo_char:
                return
            char_id = self.combo_char.itemData(index)
            if not char_id:
                return
            set_active_character(char_id)
            self.config = load_config()
            if hasattr(self, "btn_del_char") and self.btn_del_char:
                self.btn_del_char.setEnabled(char_id != "default")
            self.reload_character(char_id)

        def on_click_delete_character(self):
            char_id = get_active_character_id(self.config)
            if char_id == "default":
                return
            ret = QMessageBox.question(
                self, "Delete Character",
                "Are you sure you want to delete this custom character?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ret == QMessageBox.StandardButton.Yes:
                delete_custom_character(char_id)
                self.config = load_config()
                self.populate_character_options()
                self.reload_character("default")
                self.feedback_title.setText("🗑️ Character Deleted")
                self.feedback_sub.setText("Switched back to Hydro Buddy.")
                self.stack.setCurrentWidget(self.view_feedback)
                self.auto_hide_timer.start(1000)

        def on_click_add_custom_character(self):
            dialog = QFileDialog(self, "Select Character Video", os.path.expanduser("~"))
            dialog.setNameFilter("Video / Animation (*.mp4 *.webm *.mov *.mkv *.avi *.gif);;All Files (*)")
            if dialog.exec():
                selected = dialog.selectedFiles()
                if not selected:
                    return
                video_path = selected[0]
                if not os.path.exists(video_path):
                    return

                # Options dialog
                opt_dlg = QDialog(self)
                opt_dlg.setWindowTitle("Configure Character")
                opt_layout = QVBoxLayout(opt_dlg)

                lbl_n = QLabel("Character Name:")
                opt_layout.addWidget(lbl_n)
                base_name = os.path.splitext(os.path.basename(video_path))[0].replace("_", " ").title()
                line_name = QLineEdit(base_name)
                opt_layout.addWidget(line_name)

                lbl_b = QLabel("Background Removal Mode:")
                opt_layout.addWidget(lbl_b)
                combo_bg = QComboBox()
                combo_bg.addItem("✨ Auto-Detect Background (Smart)", "auto")
                combo_bg.addItem("⚪ White / Light Background", "white")
                combo_bg.addItem("🟢 Green Screen (Chroma Key)", "green")
                combo_bg.addItem("🔵 Blue Screen", "blue")
                combo_bg.addItem("⚫ Black / Dark Background", "black")
                combo_bg.addItem("🎞️ Video Has Transparency (Alpha)", "alpha")
                opt_layout.addWidget(combo_bg)

                lbl_f = QLabel("Animation Smoothness (FPS):")
                opt_layout.addWidget(lbl_f)
                combo_fps = QComboBox()
                combo_fps.addItem("20 FPS (Recommended - Smooth & Light)", "20")
                combo_fps.addItem("24 FPS (Cinematic 24fps)", "24")
                combo_fps.addItem("15 FPS (Resource Saver)", "15")
                opt_layout.addWidget(combo_fps)

                btn_row = QHBoxLayout()
                btn_ok = QPushButton("🚀 Convert & Apply")
                btn_ok.clicked.connect(opt_dlg.accept)
                btn_cancel = QPushButton("Cancel")
                btn_cancel.clicked.connect(opt_dlg.reject)
                btn_row.addWidget(btn_cancel)
                btn_row.addWidget(btn_ok)
                opt_layout.addLayout(btn_row)

                if opt_dlg.exec():
                    char_name = line_name.text().strip() or base_name
                    bg_mode = combo_bg.currentData() or "auto"
                    fps = int(combo_fps.currentData() or "20")

                    if self.btn_add_char:
                        self.btn_add_char.setEnabled(False)
                    if self.lbl_char_progress:
                        self.lbl_char_progress.show()
                        self.lbl_char_progress.setText("⏳ Preparing video extraction...")

                    def worker():
                        try:
                            def on_progress(pct, msg):
                                QTimer.singleShot(0, lambda: self._update_qt_char_progress(pct, msg))

                            meta = process_video_character(
                                video_path=video_path,
                                character_name=char_name,
                                bg_mode=bg_mode,
                                target_fps=fps,
                                progress_callback=on_progress
                            )
                            QTimer.singleShot(0, lambda: self._on_qt_char_done(meta))
                        except Exception as err:
                            QTimer.singleShot(0, lambda: self._on_qt_char_error(str(err)))

                    t = threading.Thread(target=worker, daemon=True)
                    t.start()

        def _update_qt_char_progress(self, pct, msg):
            if hasattr(self, "lbl_char_progress") and self.lbl_char_progress:
                self.lbl_char_progress.setText(f"⏳ {pct}%: {msg}")

        def _on_qt_char_done(self, meta):
            if hasattr(self, "btn_add_char") and self.btn_add_char:
                self.btn_add_char.setEnabled(True)
            set_active_character(meta["id"])
            self.config = load_config()
            self.populate_character_options()
            self.reload_character(meta["id"])

            if hasattr(self, "lbl_char_progress") and self.lbl_char_progress:
                self.lbl_char_progress.setText(f"🎉 Ready! {meta['name']} ({meta['frame_count']} frames)")
                QTimer.singleShot(4000, lambda: self.lbl_char_progress.hide())

            self.feedback_title.setText("🎉 Character Ready!")
            self.feedback_sub.setText(f"Active: {meta['name']}")
            self.stack.setCurrentWidget(self.view_feedback)
            self.auto_hide_timer.start(1200)

        def _on_qt_char_error(self, err_msg):
            if hasattr(self, "btn_add_char") and self.btn_add_char:
                self.btn_add_char.setEnabled(True)
            if hasattr(self, "lbl_char_progress") and self.lbl_char_progress:
                self.lbl_char_progress.setText(f"❌ Error: {err_msg[:60]}")

        def create_feedback_view(self):
            w = QWidget()
            layout = QVBoxLayout(w)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(6)

            self.feedback_title = QLabel("✅ Saved!")
            self.feedback_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #2e7d32;")
            layout.addWidget(self.feedback_title, 0, ALIGN_CENTER)

            self.feedback_sub = QLabel("Next reminder scheduled.")
            self.feedback_sub.setStyleSheet("font-size: 12px; color: #455a64;")
            layout.addWidget(self.feedback_sub, 0, ALIGN_CENTER)

            return w

        def on_click_drank(self):
            glasses = record_glass_drank(1)
            self.config = load_config()
            self.badge_label.setText(f"Today: {glasses} 🥛")
            self.stack.setCurrentWidget(self.view_drank)

        def confirm_next_interval(self, minutes):
            now = int(time.time())
            self.config = load_config()
            self.config["next_reminder_time"] = now + (minutes * 60)
            save_config(self.config)

            if minutes < 60:
                dur_str = f"{minutes} minutes"
            elif minutes % 60 == 0:
                h = minutes // 60
                dur_str = f"{h} hour" if h == 1 else f"{h} hours"
            else:
                h = minutes // 60
                m = minutes % 60
                dur_str = f"{h} hr {m} min"

            self.feedback_title.setText("🎉 Hydration Recorded!")
            self.feedback_sub.setText(f"Next reminder set for {dur_str} from now.")
            self.stack.setCurrentWidget(self.view_feedback)

            if self.on_action_callback:
                self.on_action_callback("drank", minutes)

            self.auto_hide_timer.start(700)

        def on_click_snooze(self):
            snooze_mins = self.config.get("snooze_minutes", 10)
            self.config = load_config()
            self.config["next_reminder_time"] = int(time.time()) + (snooze_mins * 60)
            save_config(self.config)

            self.feedback_title.setText("⏰ Snoozed!")
            self.feedback_sub.setText(f"Reminding you again in {snooze_mins} minutes.")
            self.stack.setCurrentWidget(self.view_feedback)

            if self.on_action_callback:
                self.on_action_callback("snooze", snooze_mins)

            self.auto_hide_timer.start(600)

        def on_click_dismiss(self):
            if self.on_action_callback:
                self.on_action_callback("dismiss", 0)
            self.hide_overlay(animated=True)

        def set_default_interval(self, minutes):
            self.config = load_config()
            self.config["interval_minutes"] = minutes
            save_config(self.config)
            self.feedback_title.setText("⚙️ Setting Updated!")
            self.feedback_sub.setText(f"Default reminder interval set to {minutes}m.")
            self.stack.setCurrentWidget(self.view_feedback)
            self.auto_hide_timer.start(700)

        def set_startup_delay_duration(self, minutes):
            self.config = load_config()
            self.config["startup_delay_minutes"] = minutes
            save_config(self.config)
            self.feedback_title.setText("⚙️ Setting Updated!")
            if minutes == 0:
                self.feedback_sub.setText("Startup delay turned off (starts immediately on boot).")
            else:
                self.feedback_sub.setText(f"First reminder will start {minutes}m after system turn-on.")
            self.stack.setCurrentWidget(self.view_feedback)
            self.auto_hide_timer.start(1200)

        def open_settings_view(self):
            self.config = load_config()
            sound_on = self.config.get("sound_enabled", True)
            if hasattr(self, "btn_sound") and self.btn_sound:
                self.btn_sound.setText(f"🔊 Sound: {'ON' if sound_on else 'OFF'}")
            self.populate_sound_options()
            self.stack.setCurrentWidget(self.view_settings)

        def populate_sound_options(self):
            if not self.combo_audio:
                return
            self.combo_audio.blockSignals(True)
            self.combo_audio.clear()

            sounds = list_available_sounds(self.config)
            current_audio = self.config.get("audio_file", "reminder.wav")
            curr_base = os.path.basename(current_audio)

            active_idx = 0
            for idx, s in enumerate(sounds):
                snd_id = s["id"] if isinstance(s, dict) else s[1]
                snd_name = s["name"] if isinstance(s, dict) else s[0]
                self.combo_audio.addItem(snd_name, snd_id)
                if snd_id == current_audio or os.path.basename(snd_id) == curr_base:
                    active_idx = idx

            self.combo_audio.setCurrentIndex(active_idx)
            self.combo_audio.blockSignals(False)

        def on_qt_audio_combo_changed(self, index):
            if index < 0 or not self.combo_audio:
                return
            selected_key = self.combo_audio.itemData(index)
            if not selected_key:
                return

            self.config = load_config()
            self.config["audio_file"] = selected_key
            save_config(self.config)

            resolved_path = get_audio_file_path(self.config)
            self.sound_player.set_audio_file(resolved_path)

        def on_click_preview_audio(self):
            if self.sound_player.is_playing():
                self.sound_player.stop()
                self._reset_qt_preview_btn()
                return

            audio_path = get_audio_file_path(self.config)
            if not os.path.exists(audio_path):
                return

            self.sound_player.play(custom_path=audio_path)
            self.btn_preview_audio.setText("■ Stop")

            if self.preview_reset_timer:
                self.preview_reset_timer.stop()
            self.preview_reset_timer = QTimer(self)
            self.preview_reset_timer.setSingleShot(True)
            self.preview_reset_timer.timeout.connect(self._reset_qt_preview_btn)
            self.preview_reset_timer.start(3000)

        def _reset_qt_preview_btn(self):
            if hasattr(self, "btn_preview_audio") and self.btn_preview_audio:
                self.btn_preview_audio.setText("▶ Play")

        def on_click_add_custom_audio(self):
            dialog = QFileDialog(self, "Select Audio File", os.path.expanduser("~"))
            dialog.setNameFilter("Audio Files (*.wav *.mp3 *.ogg *.flac *.m4a *.aac);;All Files (*)")
            if hasattr(QFileDialog, "ViewMode"):
                dialog.setViewMode(QFileDialog.ViewMode.Detail)
            if dialog.exec():
                selected_files = dialog.selectedFiles()
                if not selected_files:
                    return
                src_path = selected_files[0]
                if not os.path.isfile(src_path):
                    return

                os.makedirs(SOUNDS_DIR, exist_ok=True)
                dest_filename = os.path.basename(src_path)
                dest_path = os.path.join(SOUNDS_DIR, dest_filename)

                try:
                    if os.path.abspath(src_path) != os.path.abspath(dest_path):
                        shutil.copy2(src_path, dest_path)
                except Exception as e:
                    print(f"[Warning] Failed to copy audio to sounds dir: {e}")
                    dest_path = src_path

                self.config = load_config()
                self.config["audio_file"] = dest_filename
                save_config(self.config)

                self.sound_player.set_audio_file(get_audio_file_path(self.config))
                self.populate_sound_options()

                # Preview newly added audio
                self.on_click_preview_audio()

        def toggle_sound(self):
            self.config = load_config()
            cur = self.config.get("sound_enabled", True)
            self.config["sound_enabled"] = not cur
            save_config(self.config)
            self.btn_sound.setText(f"🔊 Sound: {'ON' if self.config['sound_enabled'] else 'OFF'}")

        def is_overlay_visible(self):
            return bool(self.isVisible())

        def reposition_bottom_right(self):
            screen = QApplication.primaryScreen()
            if not screen:
                return
            geom = screen.availableGeometry() if hasattr(screen, "availableGeometry") else screen.geometry()
            self.adjustSize()
            w = max(self.width(), 616)
            h = max(self.height(), 500)
            pos_x = geom.x() + geom.width() - w - 20
            pos_y = geom.y() + geom.height() - h - 20
            self.move(pos_x, pos_y)

        def show_overlay(self):
            if self.smoke_timer.isActive():
                self.smoke_timer.stop()
            if self.auto_hide_timer.isActive():
                self.auto_hide_timer.stop()

            self.is_closing = False
            self.bubble.show()
            self.config = load_config()
            self.sound_player.set_audio_file(get_audio_file_path(self.config))
            self.badge_label.setText(f"Today: {self.config.get('glasses_today', 0)} 🥛")
            self.stack.setCurrentWidget(self.view_prompt)

            if self.config.get("sound_enabled", True):
                self.sound_player.play()

            self.current_frame_idx = 0
            if self.char_frames:
                self.char_label.setPixmap(self.char_frames[0])

            self.show()
            self.raise_()
            self.reposition_bottom_right()
            QTimer.singleShot(50, self.reposition_bottom_right)
            QTimer.singleShot(150, self.reposition_bottom_right)
            interval = getattr(self, "frame_interval_ms", 50)
            self.anim_timer.start(interval)

        def on_anim_tick(self):
            if not self.char_frames or self.is_closing:
                return
            total = len(self.char_frames)
            self.current_frame_idx += 1
            if self.current_frame_idx >= total:
                loop_start = getattr(self, "loop_start", 0)
                if loop_start >= total:
                    loop_start = 0
                self.current_frame_idx = loop_start
            self.char_label.setPixmap(self.char_frames[self.current_frame_idx])

        def hide_overlay(self, animated=True):
            if self.anim_timer.isActive():
                self.anim_timer.stop()
            if self.auto_hide_timer.isActive():
                self.auto_hide_timer.stop()

            self.sound_player.stop()

            if animated and self.smoke_frames and not self.is_closing:
                self.is_closing = True
                self.bubble.hide()
                self.smoke_frame_idx = 0
                self.smoke_timer.start(50)
                return

            if self.smoke_timer.isActive():
                self.smoke_timer.stop()

            self.is_closing = False
            self.hide()
            self.bubble.show()

        def on_smoke_tick(self):
            if self.smoke_frame_idx < len(self.smoke_frames):
                self.char_label.setPixmap(self.smoke_frames[self.smoke_frame_idx])
                self.smoke_frame_idx += 1
            else:
                self.smoke_timer.stop()
                self.hide_overlay(animated=False)


def run_standalone():
    if not QT_AVAILABLE:
        print("[Error] No Qt bindings available (PyQt6, PySide6, or PyQt5).")
        print("Please install PyQt6: pip install PyQt6")
        return
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    overlay = QtWaterReminderOverlay()
    overlay.show_overlay()
    exec_func = getattr(app, "exec", getattr(app, "exec_", None))
    if exec_func:
        sys.exit(exec_func())


if __name__ == "__main__":
    run_standalone()

