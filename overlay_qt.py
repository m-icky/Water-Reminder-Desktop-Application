import os
import sys
import math
import time

# Qt compatibility layer for PyQt6, PySide6, and PyQt5
QT_AVAILABLE = False
QT_LIB = None

try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
        QStackedWidget, QSpinBox, QGraphicsDropShadowEffect
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

except ImportError:
    try:
        from PySide6.QtWidgets import (
            QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
            QStackedWidget, QSpinBox, QGraphicsDropShadowEffect
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

    except ImportError:
        try:
            from PyQt5.QtWidgets import (
                QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
                QStackedWidget, QSpinBox, QGraphicsDropShadowEffect
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

        except ImportError:
            QT_AVAILABLE = False
            QT_LIB = None

from config import (
    FRAMES_DIR, SMOKE_DIR, AUDIO_FILE, load_config, save_config, record_glass_drank
)
from audio import SoundPlayer


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
            tail_y = bubble_h * 0.42

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


    class QtWaterReminderOverlay(QWidget):
        def __init__(self, on_action_callback=None):
            self._app = QApplication.instance()
            if not self._app:
                self._app = QApplication(sys.argv if hasattr(sys, "argv") else [])
            super().__init__()
            self.on_action_callback = on_action_callback
            self.config = load_config()
            self.sound_player = SoundPlayer(AUDIO_FILE)

            # Window configuration
            self.setWindowTitle("Water Reminder")
            self.setWindowFlags(WINDOW_FLAGS)
            self.setAttribute(WA_TRANSLUCENT)

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

        def load_frames(self):
            # Load character frames
            if os.path.exists(FRAMES_DIR):
                files = sorted([f for f in os.listdir(FRAMES_DIR) if f.startswith("f_") and f.endswith(".png")])
                for f in files:
                    p = os.path.join(FRAMES_DIR, f)
                    pix = QPixmap(p)
                    if not pix.isNull():
                        self.char_frames.append(pix)

            # Load closing smoke frames
            if os.path.exists(SMOKE_DIR):
                smoke_files = sorted([f for f in os.listdir(SMOKE_DIR) if f.startswith("close_anim_") and f.endswith(".png")])
                for f in smoke_files:
                    p = os.path.join(SMOKE_DIR, f)
                    pix = QPixmap(p)
                    if not pix.isNull():
                        self.smoke_frames.append(pix)

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
            self.stack = QStackedWidget()

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
            btn_settings = QPushButton(f"⚙️ Interval: {self.config.get('interval_minutes', 60)}m")
            btn_settings.setStyleSheet("background: transparent; color: #78909c; font-size: 11px; font-weight: 600; border: none;")
            btn_settings.clicked.connect(lambda: self.stack.setCurrentWidget(self.view_settings))
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
                "QPushButton { background: white; color: #0277bd; font-size: 12px; font-weight: 600; "
                "border-radius: 9px; padding: 6px 10px; border: 1px solid rgba(2, 119, 189, 0.3); } "
                "QPushButton:hover { background: #e1f5fe; }"
            )

            for mins, label in [(30, "30 Mins"), (60, "1 Hour"), (120, "2 Hours")]:
                btn = QPushButton(label)
                btn.setStyleSheet(pill_style)
                btn.clicked.connect(lambda checked, m=mins: self.confirm_next_interval(m))
                row.addWidget(btn)
            layout.addLayout(row)

            # Custom spin
            custom_row = QHBoxLayout()
            lbl_c = QLabel("Custom:")
            lbl_c.setStyleSheet("font-size: 12px; color: #455a64;")
            custom_row.addWidget(lbl_c)

            self.spin_custom = QSpinBox()
            self.spin_custom.setRange(5, 300)
            self.spin_custom.setSingleStep(5)
            self.spin_custom.setValue(self.config.get("interval_minutes", 60))
            custom_row.addWidget(self.spin_custom)

            btn_set = QPushButton("Set")
            btn_set.setStyleSheet(pill_style)
            btn_set.clicked.connect(lambda: self.confirm_next_interval(self.spin_custom.value()))
            custom_row.addWidget(btn_set)
            layout.addLayout(custom_row)

            btn_back = QPushButton("← Back")
            btn_back.setStyleSheet("background: transparent; color: #78909c; font-size: 11px; font-weight: 600; border: none;")
            btn_back.clicked.connect(lambda: self.stack.setCurrentWidget(self.view_prompt))
            layout.addWidget(btn_back, 0, ALIGN_LEFT)

            return w

        def create_settings_view(self):
            w = QWidget()
            layout = QVBoxLayout(w)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

            title = QLabel("⚙️ Reminder Settings")
            title.setStyleSheet("font-size: 15px; font-weight: 800; color: #0b4f9c;")
            layout.addWidget(title)

            lbl = QLabel("Default Interval:")
            lbl.setStyleSheet("font-size: 12px; color: #455a64;")
            layout.addWidget(lbl)

            row = QHBoxLayout()
            pill_style = (
                "QPushButton { background: white; color: #0277bd; font-size: 11px; font-weight: 600; "
                "border-radius: 8px; padding: 5px 8px; border: 1px solid rgba(2, 119, 189, 0.3); } "
                "QPushButton:hover { background: #e1f5fe; }"
            )
            for mins in [30, 45, 60, 90, 120]:
                btn = QPushButton(f"{mins}m")
                btn.setStyleSheet(pill_style)
                btn.clicked.connect(lambda checked, m=mins: self.set_default_interval(m))
                row.addWidget(btn)
            layout.addLayout(row)

            sound_on = self.config.get("sound_enabled", True)
            self.btn_sound = QPushButton(f"🔊 Sound: {'ON' if sound_on else 'OFF'}")
            self.btn_sound.setStyleSheet(
                "background: rgba(225, 235, 245, 0.95); color: #37474f; "
                "font-size: 12px; font-weight: 600; border-radius: 11px; padding: 7px 12px; "
                "border: 1px solid rgba(0, 0, 0, 0.08);"
            )
            self.btn_sound.clicked.connect(self.toggle_sound)
            layout.addWidget(self.btn_sound)

            btn_back = QPushButton("← Back")
            btn_back.setStyleSheet("background: transparent; color: #78909c; font-size: 11px; font-weight: 600; border: none;")
            btn_back.clicked.connect(lambda: self.stack.setCurrentWidget(self.view_prompt))
            layout.addWidget(btn_back, 0, ALIGN_LEFT)

            return w

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
            self.config = load_config()
            self.config["interval_minutes"] = minutes
            self.config["next_reminder_time"] = int(time.time()) + (minutes * 60)
            save_config(self.config)

            dur_str = f"{minutes} minutes" if minutes < 60 else (f"{minutes // 60} hour" if minutes == 60 else f"{minutes / 60:.1f} hours")
            self.feedback_title.setText("🎉 Hydration Recorded!")
            self.feedback_sub.setText(f"Next reminder set for {dur_str} from now.")
            self.stack.setCurrentWidget(self.view_feedback)

            if self.on_action_callback:
                self.on_action_callback("drank", minutes)

            self.auto_hide_timer.start(1200)

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

            self.auto_hide_timer.start(800)

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
            self.auto_hide_timer.start(1000)

        def toggle_sound(self):
            self.config = load_config()
            cur = self.config.get("sound_enabled", True)
            self.config["sound_enabled"] = not cur
            save_config(self.config)
            self.btn_sound.setText(f"🔊 Sound: {'ON' if self.config['sound_enabled'] else 'OFF'}")

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

            self.is_closing = False
            self.bubble.show()
            self.config = load_config()
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
            self.anim_timer.start(50)

        def on_anim_tick(self):
            if not self.char_frames or self.is_closing:
                return
            total = len(self.char_frames)
            self.current_frame_idx += 1
            if self.current_frame_idx >= total:
                self.current_frame_idx = min(150, total - 20)
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

