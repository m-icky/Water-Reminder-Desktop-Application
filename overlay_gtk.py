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

from config import FRAMES_DIR, SMOKE_DIR, AUDIO_FILE, load_config, save_config, record_glass_drank
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
        self.sound_player = SoundPlayer(AUDIO_FILE)
        
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
        
        self.add(main_box)

    def create_prompt_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        
        # Header Row with Title and Glasses Badge
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title = Gtk.Label(label="💧 Drink Water Reminder!")
        title.set_xalign(0)
        title.get_style_context().add_class("title-label")
        header_row.pack_start(title, True, True, 0)
        
        self.badge_label = Gtk.Label(label=f"Today: {self.config.get('glasses_today', 0)} 🥛")
        self.badge_label.get_style_context().add_class("counter-badge")
        header_row.pack_end(self.badge_label, False, False, 0)
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
        btn_snooze = Gtk.Button(label=f"⏰ Snooze ({snooze_mins} mins)")
        btn_snooze.get_style_context().add_class("btn-snooze")
        btn_snooze.connect("clicked", self.on_click_snooze)
        box.pack_start(btn_snooze, False, False, 2)
        
        # Footer Action Row
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        
        btn_settings = Gtk.Button(label=f"⚙️ Interval: {self.config.get('interval_minutes', 60)}m")
        btn_settings.get_style_context().add_class("btn-link")
        btn_settings.connect("clicked", lambda b: self.stack.set_visible_child_name("settings"))
        footer.pack_start(btn_settings, False, False, 0)
        
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
        
        # Preset Pill Buttons
        presets_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        btn_30 = Gtk.Button(label="30 Mins")
        btn_30.get_style_context().add_class("btn-pill")
        btn_30.connect("clicked", lambda b: self.confirm_next_interval(30))
        presets_box.pack_start(btn_30, True, True, 0)
        
        btn_60 = Gtk.Button(label="1 Hour")
        btn_60.get_style_context().add_class("btn-pill")
        btn_60.connect("clicked", lambda b: self.confirm_next_interval(60))
        presets_box.pack_start(btn_60, True, True, 0)
        
        btn_120 = Gtk.Button(label="2 Hours")
        btn_120.get_style_context().add_class("btn-pill")
        btn_120.connect("clicked", lambda b: self.confirm_next_interval(120))
        presets_box.pack_start(btn_120, True, True, 0)
        
        box.pack_start(presets_box, False, False, 4)
        
        # Custom duration row
        custom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_custom = Gtk.Label(label="Custom:")
        lbl_custom.get_style_context().add_class("subtitle-label")
        custom_row.pack_start(lbl_custom, False, False, 0)
        
        self.spin_custom = Gtk.SpinButton.new_with_range(5, 300, 5)
        self.spin_custom.set_value(float(self.config.get("interval_minutes", 60)))
        custom_row.pack_start(self.spin_custom, True, True, 0)
        
        lbl_m = Gtk.Label(label="mins")
        lbl_m.get_style_context().add_class("subtitle-label")
        custom_row.pack_start(lbl_m, False, False, 0)
        
        btn_set_custom = Gtk.Button(label="Set")
        btn_set_custom.get_style_context().add_class("btn-pill")
        btn_set_custom.connect("clicked", lambda b: self.confirm_next_interval(int(self.spin_custom.get_value())))
        custom_row.pack_start(btn_set_custom, False, False, 0)
        
        box.pack_start(custom_row, False, False, 2)
        
        # Back Button
        btn_back = Gtk.Button(label="← Back")
        btn_back.get_style_context().add_class("btn-link")
        btn_back.connect("clicked", lambda b: self.stack.set_visible_child_name("prompt"))
        box.pack_start(btn_back, False, False, 0)
        
        return box

    def create_settings_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        
        title = Gtk.Label(label="⚙️ Reminder Settings")
        title.set_xalign(0)
        title.get_style_context().add_class("title-label")
        box.pack_start(title, False, False, 0)
        
        lbl_def = Gtk.Label(label="Default Interval:")
        lbl_def.set_xalign(0)
        lbl_def.get_style_context().add_class("subtitle-label")
        box.pack_start(lbl_def, False, False, 0)
        
        # Row of interval options
        intervals_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        for mins in [30, 45, 60, 90, 120]:
            btn = Gtk.Button(label=f"{mins}m")
            btn.get_style_context().add_class("btn-pill")
            btn.connect("clicked", lambda b, m=mins: self.set_default_interval(m))
            intervals_box.pack_start(btn, True, True, 0)
        box.pack_start(intervals_box, False, False, 2)
        
        # Sound Toggle
        sound_on = self.config.get("sound_enabled", True)
        self.btn_sound_toggle = Gtk.Button(label=f"🔊 Sound: {'ON' if sound_on else 'OFF'}")
        self.btn_sound_toggle.get_style_context().add_class("btn-snooze")
        self.btn_sound_toggle.connect("clicked", self.toggle_sound)
        box.pack_start(self.btn_sound_toggle, False, False, 4)
        
        # Back Button
        btn_back = Gtk.Button(label="← Back")
        btn_back.get_style_context().add_class("btn-link")
        btn_back.connect("clicked", lambda b: self.stack.set_visible_child_name("prompt"))
        box.pack_start(btn_back, False, False, 2)
        
        return box

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
        self.config = load_config()
        self.config["interval_minutes"] = minutes
        self.config["next_reminder_time"] = int(time.time()) + (minutes * 60)
        save_config(self.config)
        
        dur_str = f"{minutes} minutes" if minutes < 60 else (f"{minutes // 60} hour" if minutes == 60 else f"{minutes / 60:.1f} hours")
        self.feedback_title.set_text("🎉 Hydration Recorded!")
        self.feedback_sub.set_text(f"Next reminder set for {dur_str} from now.")
        self.stack.set_visible_child_name("feedback")
        
        if self.on_action_callback:
            self.on_action_callback("drank", minutes)
            
        # Hide after 1.2 seconds
        self.schedule_auto_hide(1200)

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
            
        self.schedule_auto_hide(800)

    def on_click_dismiss(self, widget):
        if self.on_action_callback:
            self.on_action_callback("dismiss", 0)
        self.hide_overlay()

    def set_default_interval(self, minutes):
        self.config = load_config()
        self.config["interval_minutes"] = minutes
        save_config(self.config)
        self.feedback_title.set_text("⚙️ Setting Updated!")
        self.feedback_sub.set_text(f"Default reminder interval set to {minutes}m.")
        self.stack.set_visible_child_name("feedback")
        self.schedule_auto_hide(1000)

    def toggle_sound(self, widget):
        self.config = load_config()
        cur = self.config.get("sound_enabled", True)
        self.config["sound_enabled"] = not cur
        save_config(self.config)
        self.btn_sound_toggle.set_label(f"🔊 Sound: {'ON' if self.config['sound_enabled'] else 'OFF'}")

    def schedule_auto_hide(self, delay_ms):
        if self.feedback_timer_id:
            GLib.source_remove(self.feedback_timer_id)
        self.feedback_timer_id = GLib.timeout_add(delay_ms, lambda: self.hide_overlay(animated=True))

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
            
        self.is_closing = False
        self.bubble.show()
        self.config = load_config()
        self.badge_label.set_text(f"Today: {self.config.get('glasses_today', 0)} 🥛")
        self.stack.set_visible_child_name("prompt")
        
        # Start sound if enabled
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

