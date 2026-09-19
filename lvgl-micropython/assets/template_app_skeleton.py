"""Template: multi-screen LVGL 9 application skeleton (MicroPython).

Principle: this module does NOT know the hardware. It assumes the display, the touch
driver and the LVGL loop (task_handler) are already initialized by `board.py` (board)
or by the simulator template. That way the same UI runs on the simulator and on the board.

Usage, in main.py:
    import board                 # initializes display + touch + TaskHandler
    import ui_app
    app = ui_app.App()           # KEEP the reference (module variable)

Object lifetime rule: each screen keeps its widgets, styles and timers as
attributes. Anything not kept can be freed by the garbage collector while LVGL
still uses it (random crash).
"""

import sys
import time

import lvgl as lv


def guarded(fn):
    """Decorator: print a callback's exceptions instead of losing them."""
    def wrapper(*args):
        try:
            return fn(*args)
        except Exception as exc:
            sys.print_exception(exc)
    return wrapper


class Theme:
    """Shared styles, created once and kept."""

    def __init__(self):
        self.button = lv.style_t()
        self.button.init()
        self.button.set_radius(12)
        self.button.set_bg_color(lv.palette_main(lv.PALETTE.BLUE))
        self.button.set_border_width(0)
        self.button.set_text_color(lv.color_white())

        self.button_pressed = lv.style_t()
        self.button_pressed.init()
        self.button_pressed.set_bg_color(lv.palette_darken(lv.PALETTE.BLUE, 2))

    def make_button(self, parent, text, on_click):
        btn = lv.button(parent)
        btn.add_style(self.button, 0)
        btn.add_style(self.button_pressed, lv.STATE.PRESSED)
        lbl = lv.label(btn)
        lbl.set_text(text)
        lbl.center()
        btn.add_event_cb(guarded(on_click), lv.EVENT.CLICKED, None)
        return btn


class HomeScreen:
    def __init__(self, app):
        self.app = app
        self.scr = lv.obj(None)                  # a screen = an object without a parent
        self.scr.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.scr.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER,
                                lv.FLEX_ALIGN.CENTER)

        self.clock = lv.label(self.scr)
        self.clock.set_text("--:--:--")

        self.btn_settings = app.theme.make_button(
            self.scr, lv.SYMBOL.SETTINGS + " Settings", self.on_settings)
        self.btn_settings.set_width(lv.pct(70))

        # LVGL timer: periodic update, reference kept on self.
        self.timer = lv.timer_create(self.refresh, 1000, None)

    @guarded
    def refresh(self, t):
        secs = time.ticks_ms() // 1000
        self.clock.set_text("%02d:%02d:%02d" % (secs // 3600, (secs // 60) % 60, secs % 60))

    def on_settings(self, e):
        self.app.show(self.app.settings)


class SettingsScreen:
    def __init__(self, app):
        self.app = app
        self.scr = lv.obj(None)
        self.scr.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.scr.set_flex_align(lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER,
                                lv.FLEX_ALIGN.CENTER)

        self.title = lv.label(self.scr)
        self.title.set_text("Brightness")

        self.slider = lv.slider(self.scr)
        self.slider.set_width(lv.pct(80))
        self.slider.set_range(0, 100)
        self.slider.set_value(100, False)
        self.slider.add_event_cb(guarded(self.on_slide), lv.EVENT.VALUE_CHANGED, None)

        self.btn_back = app.theme.make_button(
            self.scr, lv.SYMBOL.LEFT + " Back", self.on_back)

    def on_slide(self, e):
        value = self.slider.get_value()
        self.app.on_brightness(value)

    def on_back(self, e):
        self.app.show(self.app.home, back=True)


class App:
    def __init__(self, set_backlight=None):
        """`set_backlight`: optional callback (e.g. display.set_backlight) provided by board.py."""
        self._set_backlight = set_backlight
        self.theme = Theme()
        self.home = HomeScreen(self)
        self.settings = SettingsScreen(self)
        lv.screen_load(self.home.scr)

    def show(self, screen, back=False):
        anim = lv.SCREEN_LOAD_ANIM.MOVE_RIGHT if back else lv.SCREEN_LOAD_ANIM.MOVE_LEFT
        # auto_del=False: the screen is kept so we can come back to it
        lv.screen_load_anim(screen.scr, anim, 250, 0, False)

    def on_brightness(self, value):
        if self._set_backlight is not None:
            self._set_backlight(value)
