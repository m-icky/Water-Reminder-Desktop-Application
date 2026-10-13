import os
import sys
import math
import time

# Force X11 backend on Linux so floating overlays can freely position and stay on top
if sys.platform.startswith("linux") and os.environ.get("DISPLAY"):
    os.environ["GDK_BACKEND"] = "x11"
if sys.platform != "win32":
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import Gtk, Gdk, GdkPixbuf, GLib
        import cairo
        GTK_AVAILABLE = True
    except Exception:
        GTK_AVAILABLE = False

from config import (
    FRAMES_DIR, SMOKE_DIR, SOUNDS_DIR, AUDIO_FILE, load_config, save_config,
    record_glass_drank, get_audio_file_path, list_available_sounds
)
from audio import SoundPlayer

CSS_STYLE = b"""
window {
    background-color: transparent;
}

.card-content {
    padding: 14px 18px 12px 14px;
}

.title-label {
    font-size: 15px;
    font-weight: 800;
    color: #0b4f9c;
}

.subtitle-label {
    font-size: 12px;
    color: #455a64;
}

.counter-badge {
    background-color: rgba(0, 150, 255, 0.12);
    color: #0277bd;
    font-size: 11px;
    font-weight: 700;
    border-radius: 10px;
    padding: 2px 7px;
}

.btn-gear {
    background: rgba(0, 150, 255, 0.08);
    color: #455a64;
    font-size: 13px;
    border-radius: 8px;
    padding: 2px 7px;
    border: 1px solid rgba(0, 150, 255, 0.22);
}
.btn-gear:hover {
    background: rgba(0, 150, 255, 0.22);
    color: #01579b;
}

.combo-audio {
    background: white;
    font-size: 11px;
    border-radius: 8px;
    border: 1px solid rgba(2, 119, 189, 0.35);
    padding: 2px 4px;
}

.btn-drank {
    background: linear-gradient(to bottom, #00b0ff, #0066fe);
    color: white;
    font-size: 13px;
    font-weight: 700;
    border-radius: 11px;
    padding: 8px 14px;
    border: none;
    box-shadow: 0 4px 12px rgba(0, 102, 254, 0.35);
}
.btn-drank:hover {
    background: linear-gradient(to bottom, #38c5ff, #0050cc);
}

.btn-snooze {
    background: rgba(225, 235, 245, 0.95);
    color: #37474f;
    font-size: 12px;
    font-weight: 600;
    border-radius: 11px;
    padding: 7px 12px;
    border: 1px solid rgba(0, 0, 0, 0.08);
}
.btn-snooze:hover {
    background: rgba(210, 225, 240, 1);
    color: #212121;
}

.btn-pill {
    background: white;
    color: #0277bd;
    font-size: 13px;
    font-weight: 600;
    border-radius: 10px;
    padding: 6px 12px;
    border: 1px solid rgba(2, 119, 189, 0.3);
}
.btn-pill:hover {
    background: #e1f5fe;
}

.btn-pill-active {
    background: #0288d1;
    color: white;
    font-size: 13px;
    font-weight: 700;
    border-radius: 10px;
    padding: 6px 12px;
    border: none;
}

.btn-link {
    background: transparent;
    color: #78909c;
    font-size: 11px;
    font-weight: 600;
    border: none;
    padding: 2px 6px;
}
.btn-link:hover {
    color: #37474f;
}

.feedback-box {
    background: rgba(232, 245, 233, 0.95);
    border: 1px solid rgba(76, 175, 80, 0.4);
    border-radius: 12px;
    padding: 12px;
}
.feedback-label {
    font-size: 14px;
    font-weight: 700;
    color: #2e7d32;
}

spinbutton {
    background: #ffffff;
    color: #0b4f9c;
    border: 1.5px solid rgba(0, 122, 242, 0.35);
    border-radius: 8px;
    padding: 1px 3px;
    font-size: 13px;
    font-weight: 700;
}
spinbutton entry {
    background: transparent;
    color: #0b4f9c;
    font-weight: 700;
    border: none;
    box-shadow: none;
    min-width: 26px;
    padding: 1px 2px;
}
spinbutton button {
    background: rgba(0, 150, 255, 0.12);
    color: #0277bd;
    border: none;
    border-radius: 5px;
    padding: 1px 4px;
}
spinbutton button:hover {
    background: rgba(0, 150, 255, 0.28);
    color: #01579b;
}
"""

class SpeechBubble(Gtk.Box):
    """Custom speech bubble box with Cairo tail pointing towards the character."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_app_paintable(True)
        self.connect("draw", self.on_draw)
        
    def on_draw(self, widget, cr):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        
        # Tail parameters on right edge
        tail_w = 14
        tail_h = 18
        bubble_w = max(10, width - tail_w)
        bubble_h = height
        radius = 16
        tail_y = bubble_h * 0.42
        
        # Clear
        cr.save()
        
        # Draw bubble path
        cr.new_sub_path()
        cr.arc(bubble_w - radius, radius, radius, -math.pi/2, 0)
        # Tail pointing right
        cr.line_to(bubble_w, tail_y)
        cr.line_to(bubble_w + tail_w, tail_y + tail_h / 2)
        cr.line_to(bubble_w, tail_y + tail_h)
        cr.arc(bubble_w - radius, bubble_h - radius, radius, 0, math.pi/2)
        cr.arc(radius, bubble_h - radius, radius, math.pi/2, math.pi)
        cr.arc(radius, radius, radius, math.pi, 3*math.pi/2)
        cr.close_path()
        
        # Fill soft frosted gradient
        pat = cairo.LinearGradient(0, 0, bubble_w, bubble_h)
        pat.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.98)
        pat.add_color_stop_rgba(1.0, 0.93, 0.97, 1.0, 0.96)
        cr.set_source(pat)
        cr.fill_preserve()
        
        # Border stroke
        cr.set_source_rgba(0.0, 0.48, 0.95, 0.28)
        cr.set_line_width(1.8)
        cr.stroke()
        
        cr.restore()
        return False


class WaterReminderOverlay(Gtk.Window):
    def __init__(self, on_action_callback=None):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.on_action_callback = on_action_callback
        self.config = load_config()
        self.sound_player = SoundPlayer(get_audio_file_path(self.config))
        self.combo_audio = None
        self.btn_preview_audio = None
        
        # Window properties
        self.set_title("Water Reminder")
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.stick()  # Visible on all workspaces
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.connect("map", lambda w: self.reposition_bottom_right())
        self.connect("realize", lambda w: self.reposition_bottom_right())
        
        # Visual transparency
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)
        self.set_app_paintable(True)
        self.connect("draw", self.on_window_draw)
        
        # Load CSS
        self.setup_css()
        
        # Animation state
        self.frames = []
        self.smoke_frames = []
        self.current_frame_idx = 0
        self.smoke_frame_idx = 0
        self.anim_timer_id = None
        self.smoke_timer_id = None
        self.feedback_timer_id = None
        self.is_closing = False
        self.load_frames()
        
        # Build UI layout
        self.build_ui()

    def setup_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS_STYLE)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
    def on_window_draw(self, widget, cr):
        # Clear window background so it is 100% transparent
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        return False

    def load_frames(self):
        # Character walk-in and pose frames
        if os.path.exists(FRAMES_DIR):
            files = sorted([f for f in os.listdir(FRAMES_DIR) if f.startswith("f_") and f.endswith(".png")])
            for f in files:
                p = os.path.join(FRAMES_DIR, f)
                try:
                    pb = GdkPixbuf.Pixbuf.new_from_file(p)
                    self.frames.append(pb)
                except Exception as e:
                    print(f"[Overlay] Failed loading frame {f}: {e}")
                    
        # Smoke closing animation frames
        if os.path.exists(SMOKE_DIR):
            smoke_files = sorted([f for f in os.listdir(SMOKE_DIR) if f.startswith("close_anim_") and f.endswith(".png")])
            for f in smoke_files:
                p = os.path.join(SMOKE_DIR, f)
                try:
                    pb = GdkPixbuf.Pixbuf.new_from_file(p)
                    self.smoke_frames.append(pb)
                except Exception as e:
                    print(f"[Overlay] Failed loading smoke frame {f}: {e}")

    def build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)
        
        # Left side: Speech Bubble - compact height, aligned with character's upper body
        self.bubble = SpeechBubble(orientation=Gtk.Orientation.VERTICAL)
        self.bubble.set_valign(Gtk.Align.START)
        self.bubble.set_margin_top(45)
        self.bubble.set_size_request(320, -1)
        
        # Inner content box inside speech bubble
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.content_box.get_style_context().add_class("card-content")
        
        # Stack to switch between different views
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(250)
        
        # View 1: Main Reminder Prompt
        self.view_prompt = self.create_prompt_view()
        self.stack.add_named(self.view_prompt, "prompt")
        
        # View 2: Post-Drink Interval Chooser
        self.view_drank = self.create_drank_view()
        self.stack.add_named(self.view_drank, "drank")
        
        # View 3: Settings View
        self.view_settings = self.create_settings_view()
        self.stack.add_named(self.view_settings, "settings")
        
        # View 4: Feedback Toast
        self.view_feedback = self.create_feedback_view()
        self.stack.add_named(self.view_feedback, "feedback")
        
        self.content_box.pack_start(self.stack, True, True, 0)
        self.bubble.pack_start(self.content_box, True, True, 0)
        main_box.pack_start(self.bubble, False, False, 0)
        
        # Right side: Character Animation Widget
        self.image_widget = Gtk.Image()
        if self.frames:
            self.image_widget.set_from_pixbuf(self.frames[0])
        main_box.pack_start(self.image_widget, False, False, 0)
        
        self.apply_pointer_cursors(main_box)
        self.add(main_box)

    def make_pointer(self, widget):
        widget.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        
        def on_enter(w, event):
            if event.detail == Gdk.NotifyType.INFERIOR:
                return False
            win = w.get_window()
            if win:
                display = win.get_display()
                cursor = Gdk.Cursor.new_from_name(display, "pointer")
                if not cursor:
                    cursor = Gdk.Cursor.new_for_display(display, Gdk.CursorType.HAND2)
                win.set_cursor(cursor)
            return False
            
        def on_leave(w, event):
            if event.detail == Gdk.NotifyType.INFERIOR:
                return False
            win = w.get_window()
            if win:
                win.set_cursor(None)
            return False
            
        widget.connect("enter-notify-event", on_enter)
        widget.connect("leave-notify-event", on_leave)
        return widget

    def apply_pointer_cursors(self, widget):
        if isinstance(widget, Gtk.Button):
            self.make_pointer(widget)
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                self.apply_pointer_cursors(child)

    def create_prompt_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        
        # Header Row with Title, Glasses Badge, and Gear Settings Button
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title = Gtk.Label(label="💧 Drink Water Reminder!")
        title.set_xalign(0)
        title.get_style_context().add_class("title-label")
        header_row.pack_start(title, True, True, 0)
        
        self.badge_label = Gtk.Label(label=f"Today: {self.config.get('glasses_today', 0)} 🥛")
        self.badge_label.get_style_context().add_class("counter-badge")
        header_row.pack_start(self.badge_label, False, False, 0)

        # Dedicated Gear Icon Button for Settings & Audio
        self.btn_gear = Gtk.Button(label="⚙️")
        self.btn_gear.set_tooltip_text("Settings & Audio Customization")
        self.btn_gear.get_style_context().add_class("btn-gear")
        self.btn_gear.connect("clicked", lambda b: self.open_settings_view())
        header_row.pack_end(self.btn_gear, False, False, 0)
        box.pack_start(header_row, False, False, 0)
        
        # Subtitle with bounded width
        sub = Gtk.Label(label="Time to hydrate! Grab a glass of water to keep your body energized and sharp.")
        sub.set_line_wrap(True)
        sub.set_max_width_chars(32)
        sub.set_xalign(0)
        sub.get_style_context().add_class("subtitle-label")
        box.pack_start(sub, False, False, 0)
        
        # Primary Action: Yes, I drank water
        btn_drank = Gtk.Button(label="✅ Yes, I Drank Water")
        btn_drank.get_style_context().add_class("btn-drank")
        btn_drank.connect("clicked", self.on_click_drank)
        box.pack_start(btn_drank, False, False, 2)
        
        # Secondary Action: Snooze
        snooze_mins = self.config.get("snooze_minutes", 10)
        self.btn_snooze = Gtk.Button(label=f"⏰ Snooze ({snooze_mins} mins)")
        self.btn_snooze.get_style_context().add_class("btn-snooze")
        self.btn_snooze.connect("clicked", self.on_click_snooze)
        box.pack_start(self.btn_snooze, False, False, 2)
        
        # Footer Action Row
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        self.btn_interval_settings = Gtk.Button(label="⚙️ Settings & Audio")
        self.btn_interval_settings.get_style_context().add_class("btn-link")
        self.btn_interval_settings.connect("clicked", lambda b: self.open_settings_view())
        footer.pack_start(self.btn_interval_settings, False, False, 0)
        
        btn_dismiss = Gtk.Button(label="✕ Close")
        btn_dismiss.get_style_context().add_class("btn-link")
        btn_dismiss.connect("clicked", self.on_click_dismiss)
        footer.pack_end(btn_dismiss, False, False, 0)
        
        box.pack_start(footer, False, False, 2)
        return box

    def create_drank_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        
        title = Gtk.Label(label="🎉 Great job staying hydrated!")
        title.set_xalign(0)
        title.get_style_context().add_class("title-label")
        box.pack_start(title, False, False, 0)
        
        sub = Gtk.Label(label="When should I remind you to drink water next?")
        sub.set_line_wrap(True)
        sub.set_max_width_chars(32)
        sub.set_xalign(0)
        sub.get_style_context().add_class("subtitle-label")
        box.pack_start(sub, False, False, 0)
        
        # Quick Presets: 30 Mins, 1 Hour, 1.5 Hours, 2 Hours
        presets_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        btn_30 = Gtk.Button(label="30 Mins")
        btn_30.get_style_context().add_class("btn-pill")
        btn_30.connect("clicked", lambda b: self.confirm_next_interval(30))
        presets_box.pack_start(btn_30, True, True, 0)
        
        btn_60 = Gtk.Button(label="1 Hour")
        btn_60.get_style_context().add_class("btn-pill")
        btn_60.connect("clicked", lambda b: self.confirm_next_interval(60))
        presets_box.pack_start(btn_60, True, True, 0)

        btn_90 = Gtk.Button(label="1.5 Hours")
        btn_90.get_style_context().add_class("btn-pill")
        btn_90.connect("clicked", lambda b: self.confirm_next_interval(90))
        presets_box.pack_start(btn_90, True, True, 0)
        
        btn_120 = Gtk.Button(label="2 Hours")
        btn_120.get_style_context().add_class("btn-pill")
        btn_120.connect("clicked", lambda b: self.confirm_next_interval(120))
        presets_box.pack_start(btn_120, True, True, 0)
        
        box.pack_start(presets_box, False, False, 2)
        
        # Custom duration row: Hours and Minutes
        custom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl_custom = Gtk.Label(label="Custom:")
        lbl_custom.get_style_context().add_class("subtitle-label")
        custom_row.pack_start(lbl_custom, False, False, 0)
        
        # Hours spin
        self.spin_hours = Gtk.SpinButton.new_with_range(0, 12, 1)
        self.spin_hours.set_value(1)
        self.spin_hours.set_width_chars(2)
        custom_row.pack_start(self.spin_hours, False, False, 0)
        
        lbl_hr = Gtk.Label(label="hr")
        lbl_hr.get_style_context().add_class("subtitle-label")
        custom_row.pack_start(lbl_hr, False, False, 0)
        
        # Minutes spin
        self.spin_mins = Gtk.SpinButton.new_with_range(0, 55, 5)
        self.spin_mins.set_value(0)
        self.spin_mins.set_width_chars(2)
        custom_row.pack_start(self.spin_mins, False, False, 0)
        
        lbl_min = Gtk.Label(label="min")
        lbl_min.get_style_context().add_class("subtitle-label")
        custom_row.pack_start(lbl_min, False, False, 0)
        
        btn_set_custom = Gtk.Button(label="Set")
        btn_set_custom.get_style_context().add_class("btn-pill")
        btn_set_custom.connect("clicked", self.on_custom_interval_set)
        custom_row.pack_start(btn_set_custom, True, True, 2)
        
        box.pack_start(custom_row, False, False, 2)
        
        # Back Button
        btn_back = Gtk.Button(label="← Back")
        btn_back.get_style_context().add_class("btn-link")
        btn_back.connect("clicked", lambda b: self.stack.set_visible_child_name("prompt"))
        box.pack_start(btn_back, False, False, 0)
        
        return box

    def on_custom_interval_set(self, widget):
        h = int(self.spin_hours.get_value())
        m = int(self.spin_mins.get_value())
        total_mins = (h * 60) + m
        if total_mins <= 0:
            total_mins = 15  # Fallback minimum 15 mins
        self.confirm_next_interval(total_mins)

    def create_settings_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        
        title = Gtk.Label(label="⚙️ Settings & Audio")
        title.set_xalign(0)
        title.get_style_context().add_class("title-label")
        box.pack_start(title, False, False, 0)
        
        # Audio Section
        lbl_audio = Gtk.Label(label="🎵 Reminder Sound Alert:")
        lbl_audio.set_xalign(0)
        lbl_audio.get_style_context().add_class("subtitle-label")
        box.pack_start(lbl_audio, False, False, 0)
        
        audio_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.combo_audio = Gtk.ComboBoxText()
        self.combo_audio.get_style_context().add_class("combo-audio")
        self.populate_sound_options()
        self.combo_audio.connect("changed", self.on_audio_combo_changed)
        audio_row.pack_start(self.combo_audio, True, True, 0)
        
        self.btn_preview_audio = Gtk.Button(label="▶ Play")
        self.btn_preview_audio.get_style_context().add_class("btn-pill")
        self.btn_preview_audio.connect("clicked", self.on_click_preview_audio)
        audio_row.pack_start(self.btn_preview_audio, False, False, 0)
        box.pack_start(audio_row, False, False, 1)
        
        # Audio Actions Row: Add Custom Audio & Sound Toggle
        audio_act_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_add_audio = Gtk.Button(label="📁 Add Audio File...")
        btn_add_audio.get_style_context().add_class("btn-pill")
        btn_add_audio.connect("clicked", self.on_click_add_custom_audio)
        audio_act_row.pack_start(btn_add_audio, True, True, 0)
        
        sound_on = self.config.get("sound_enabled", True)
        self.btn_sound_toggle = Gtk.Button(label=f"🔊 Sound: {'ON' if sound_on else 'OFF'}")
        self.btn_sound_toggle.get_style_context().add_class("btn-snooze")
        self.btn_sound_toggle.connect("clicked", self.toggle_sound)
        audio_act_row.pack_start(self.btn_sound_toggle, False, False, 0)
        box.pack_start(audio_act_row, False, False, 1)

        # Row 2: Default Interval
        lbl_def = Gtk.Label(label="Default Interval:")
        lbl_def.set_xalign(0)
        lbl_def.get_style_context().add_class("subtitle-label")
        box.pack_start(lbl_def, False, False, 0)
        
        intervals_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        for mins in [30, 45, 60, 90, 120]:
            btn = Gtk.Button(label=f"{mins}m")
            btn.get_style_context().add_class("btn-pill")
            btn.connect("clicked", lambda b, m=mins: self.set_default_interval(m))
            intervals_box.pack_start(btn, True, True, 0)
        box.pack_start(intervals_box, False, False, 1)
        
        # Row 3: Default Snooze
        lbl_snz = Gtk.Label(label="Default Snooze:")
        lbl_snz.set_xalign(0)
        lbl_snz.get_style_context().add_class("subtitle-label")
        box.pack_start(lbl_snz, False, False, 0)
        
        snooze_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        for smins in [5, 10, 15, 20, 30]:
            btn = Gtk.Button(label=f"{smins}m")
            btn.get_style_context().add_class("btn-pill")
            btn.connect("clicked", lambda b, m=smins: self.set_snooze_duration(m))
            snooze_box.pack_start(btn, True, True, 0)
        box.pack_start(snooze_box, False, False, 1)
        
        # Back Button
        btn_back = Gtk.Button(label="← Back to Reminder")
        btn_back.get_style_context().add_class("btn-link")
        btn_back.connect("clicked", lambda b: self.stack.set_visible_child_name("prompt"))
        box.pack_start(btn_back, False, False, 1)
        
        return box

    def toggle_sound(self, widget=None):
        self.config = load_config()
        cur = self.config.get("sound_enabled", True)
        self.config["sound_enabled"] = not cur
        save_config(self.config)
        if hasattr(self, "btn_sound_toggle") and self.btn_sound_toggle:
            self.btn_sound_toggle.set_label(f"🔊 Sound: {'ON' if self.config['sound_enabled'] else 'OFF'}")

    def open_settings_view(self):
        self.populate_sound_options()
        sound_on = self.config.get("sound_enabled", True)
        if hasattr(self, "btn_sound_toggle") and self.btn_sound_toggle:
            self.btn_sound_toggle.set_label(f"🔊 Sound: {'ON' if sound_on else 'OFF'}")
        self.stack.set_visible_child_name("settings")

    def populate_sound_options(self):
        if not hasattr(self, "combo_audio") or self.combo_audio is None:
            return
        self.combo_audio.remove_all()
        sounds = list_available_sounds(self.config)
        cur_sound = self.config.get("audio_file", "reminder.wav")
        active_idx = 0
        for idx, s in enumerate(sounds):
            self.combo_audio.append(s["id"], s["name"])
            if s["id"] == cur_sound or os.path.basename(s["path"]) == os.path.basename(cur_sound):
                active_idx = idx
        self.combo_audio.set_active(active_idx)

    def on_audio_combo_changed(self, widget):
        sound_id = self.combo_audio.get_active_id()
        if not sound_id:
            return
        self.config = load_config()
        self.config["audio_file"] = sound_id
        save_config(self.config)
        new_path = get_audio_file_path(self.config)
        self.sound_player.set_audio_file(new_path)

    def on_click_preview_audio(self, widget):
        if self.sound_player.is_playing():
            self.sound_player.stop()
            self.btn_preview_audio.set_label("▶ Play")
        else:
            new_path = get_audio_file_path(self.config)
            self.sound_player.play(new_path)
            self.btn_preview_audio.set_label("■ Stop")
            GLib.timeout_add(3500, self._reset_preview_btn)

    def _reset_preview_btn(self):
        if hasattr(self, "btn_preview_audio") and self.btn_preview_audio:
            if not self.sound_player.is_playing():
                self.btn_preview_audio.set_label("▶ Play")
                return False
        return True

    def on_click_add_custom_audio(self, widget):
        dialog = Gtk.FileChooserDialog(
            title="Select Custom Audio Alert",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Select Audio", Gtk.ResponseType.ACCEPT)
        
        filter_audio = Gtk.FileFilter()
        filter_audio.set_name("Audio Files (*.wav, *.mp3, *.ogg, *.flac)")
        filter_audio.add_pattern("*.wav")
        filter_audio.add_pattern("*.WAV")
        filter_audio.add_pattern("*.mp3")
        filter_audio.add_pattern("*.MP3")
        filter_audio.add_pattern("*.ogg")
        filter_audio.add_pattern("*.OGG")
        filter_audio.add_pattern("*.flac")
        filter_audio.add_pattern("*.FLAC")
        filter_audio.add_pattern("*.m4a")
        dialog.add_filter(filter_audio)
        
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)
        
        response = dialog.run()
        if response == Gtk.ResponseType.ACCEPT:
            filename = dialog.get_filename()
            if filename and os.path.exists(filename):
                os.makedirs(SOUNDS_DIR, exist_ok=True)
                dest_filename = os.path.basename(filename)
                dest_path = os.path.join(SOUNDS_DIR, dest_filename)
                import shutil
                try:
                    if os.path.abspath(filename) != os.path.abspath(dest_path):
                        shutil.copy2(filename, dest_path)
                    chosen_id = dest_filename
                except Exception as e:
                    chosen_id = filename
                    
                self.config = load_config()
                self.config["audio_file"] = chosen_id
                save_config(self.config)
                
                self.populate_sound_options()
                new_p = get_audio_file_path(self.config)
                self.sound_player.set_audio_file(new_p)
                self.sound_player.play()
                
                self.feedback_title.set_text("🎵 Custom Audio Set!")
                self.feedback_sub.set_text(f"Selected: {os.path.basename(filename)}")
                self.stack.set_visible_child_name("feedback")
                self.schedule_auto_hide(1200)
        dialog.destroy()

    def set_snooze_duration(self, minutes):
        self.config = load_config()
        self.config["snooze_minutes"] = minutes
        save_config(self.config)
        self.btn_snooze.set_label(f"⏰ Snooze ({minutes} mins)")
        self.feedback_title.set_text("⚙️ Setting Updated!")
        self.feedback_sub.set_text(f"Default snooze duration set to {minutes}m.")
        self.stack.set_visible_child_name("feedback")
        self.schedule_auto_hide(1000)

    def set_default_interval(self, minutes):
        self.config = load_config()
        self.config["interval_minutes"] = minutes
        save_config(self.config)
        self.btn_interval_settings.set_label(f"⚙️ Interval: {minutes}m")
        self.feedback_title.set_text("⚙️ Setting Updated!")
        self.feedback_sub.set_text(f"Default reminder interval set to {minutes}m.")
        self.stack.set_visible_child_name("feedback")
        self.schedule_auto_hide(1000)

    def create_feedback_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("feedback-box")
        
        self.feedback_title = Gtk.Label(label="✅ Saved!")
        self.feedback_title.get_style_context().add_class("feedback-label")
        box.pack_start(self.feedback_title, True, True, 4)
        
        self.feedback_sub = Gtk.Label(label="Next reminder scheduled.")
        self.feedback_sub.get_style_context().add_class("subtitle-label")
        box.pack_start(self.feedback_sub, True, True, 0)
        
        return box

    def on_click_drank(self, widget):
        # User drank water: record glass count with automatic date check
        glasses = record_glass_drank(1)
        self.config = load_config()
        self.badge_label.set_text(f"Today: {glasses} 🥛")
        
        # Move to interval selection
        self.stack.set_visible_child_name("drank")

    def confirm_next_interval(self, minutes):
        now = int(time.time())
        next_time = now + (minutes * 60)
        self.config = load_config()
        self.config["next_reminder_time"] = next_time
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
            
        self.feedback_title.set_text("🎉 Hydration Recorded!")
        self.feedback_sub.set_text(f"Next reminder set for {dur_str} from now.")
        self.stack.set_visible_child_name("feedback")
        
        if self.on_action_callback:
            self.on_action_callback("drank", minutes)
            
        # Hide after 700ms feedback
        self.schedule_auto_hide(700)

    def on_click_snooze(self, widget):
        snooze_mins = self.config.get("snooze_minutes", 10)
        self.config = load_config()
        self.config["next_reminder_time"] = int(time.time()) + (snooze_mins * 60)
        save_config(self.config)
        
        self.feedback_title.set_text("⏰ Snoozed!")
        self.feedback_sub.set_text(f"Reminding you again in {snooze_mins} minutes.")
        self.stack.set_visible_child_name("feedback")
        
        if self.on_action_callback:
            self.on_action_callback("snooze", snooze_mins)
            
        self.schedule_auto_hide(600)

    def on_click_dismiss(self, widget):
        if self.on_action_callback:
            self.on_action_callback("dismiss", 0)
        self.hide_overlay(animated=True)

    def is_overlay_visible(self):
        return bool(self.get_visible())

    def _on_auto_hide_timeout(self):
        self.feedback_timer_id = None
        self.hide_overlay(animated=True)
        return False

    def schedule_auto_hide(self, delay_ms):
        if self.feedback_timer_id:
            GLib.source_remove(self.feedback_timer_id)
            self.feedback_timer_id = None
        self.feedback_timer_id = GLib.timeout_add(delay_ms, self._on_auto_hide_timeout)

    def reposition_bottom_right(self):
        display = Gdk.Display.get_default()
        if not display:
            return False
        mon = display.get_primary_monitor() or display.get_monitor(0)
        if not mon:
            return False
        geom = mon.get_workarea() if hasattr(mon, "get_workarea") else mon.get_geometry()
        
        alloc = self.get_allocation()
        win_w = max(alloc.width, 616)
        win_h = max(alloc.height, 500)
        pos_x = geom.x + geom.width - win_w - 20
        pos_y = geom.y + geom.height - win_h - 20
        self.move(pos_x, pos_y)
        if self.get_window():
            self.get_window().move(pos_x, pos_y)
            self.get_window().raise_()
        return False

    def show_overlay(self):
        if self.smoke_timer_id:
            GLib.source_remove(self.smoke_timer_id)
            self.smoke_timer_id = None
        if self.feedback_timer_id:
            GLib.source_remove(self.feedback_timer_id)
            self.feedback_timer_id = None
            
        self.is_closing = False
        self.bubble.show()
        self.config = load_config()
        self.badge_label.set_text(f"Today: {self.config.get('glasses_today', 0)} 🥛")
        self.stack.set_visible_child_name("prompt")
        
        # Start sound if enabled using currently configured audio
        self.sound_player.set_audio_file(get_audio_file_path(self.config))
        if self.config.get("sound_enabled", True):
            self.sound_player.play()
            
        # Start animation from beginning
        self.current_frame_idx = 0
        if self.frames:
            self.image_widget.set_from_pixbuf(self.frames[0])
            
        self.show_all()
        self.stick()
        self.set_keep_above(True)
        self.present()
        self.reposition_bottom_right()
        GLib.idle_add(self.reposition_bottom_right)
        GLib.timeout_add(50, self.reposition_bottom_right)
        GLib.timeout_add(150, self.reposition_bottom_right)
        
        if self.anim_timer_id:
            GLib.source_remove(self.anim_timer_id)
        self.anim_timer_id = GLib.timeout_add(50, self.on_anim_tick)

    def on_anim_tick(self):
        if not self.frames or self.is_closing:
            return False
            
        total_frames = len(self.frames)
        self.current_frame_idx += 1
        
        # Loop smile and raised bottle pose
        if self.current_frame_idx >= total_frames:
            loop_start = min(150, total_frames - 20)
            self.current_frame_idx = loop_start
            
        self.image_widget.set_from_pixbuf(self.frames[self.current_frame_idx])
        return True

    def hide_overlay(self, animated=True):
        if self.anim_timer_id:
            GLib.source_remove(self.anim_timer_id)
            self.anim_timer_id = None
        if self.feedback_timer_id:
            GLib.source_remove(self.feedback_timer_id)
            self.feedback_timer_id = None
            
        self.sound_player.stop()
        
        if animated and self.smoke_frames and not self.is_closing:
            self.is_closing = True
            # Hide speech bubble so smoke poof is centered on character
            self.bubble.hide()
            self.smoke_frame_idx = 0
            if self.smoke_timer_id:
                GLib.source_remove(self.smoke_timer_id)
            self.smoke_timer_id = GLib.timeout_add(50, self.on_smoke_tick)
            return False
            
        if self.smoke_timer_id:
            GLib.source_remove(self.smoke_timer_id)
            self.smoke_timer_id = None
            
        self.is_closing = False
        self.hide()
        self.bubble.show()
        return False

    def on_smoke_tick(self):
        if self.smoke_frame_idx < len(self.smoke_frames):
            self.image_widget.set_from_pixbuf(self.smoke_frames[self.smoke_frame_idx])
            self.smoke_frame_idx += 1
            return True
        else:
            self.smoke_timer_id = None
            self.hide_overlay(animated=False)
            return False


def run_standalone():
    overlay = WaterReminderOverlay()
    overlay.show_overlay()
    Gtk.main()


if __name__ == "__main__":
    run_standalone()

