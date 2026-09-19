"""Template: Unix/macOS simulator (SDL), lvgl_micropython binding.

Build the binary (on the machine that will run it):
    python3 make.py unix DISPLAY=sdl_display INDEV=sdl_pointer

Then run this script with the MicroPython binary printed at the end of the build:
    <path/to/micropython> template_sdl_simulator.py

Purpose: iterate on the interface without flashing a board. Keep the UI
construction in a separate module (see template_app_skeleton.py) so it can be
reused unchanged on the hardware.
"""

from micropython import const
import lcd_bus

WIDTH = const(480)
HEIGHT = const(320)

bus = lcd_bus.SDLBus(flags=0)
buf1 = bus.allocate_framebuffer(WIDTH * HEIGHT * 3, 0)

import lvgl as lv          # noqa: E402
import sdl_display         # noqa: E402
import sdl_pointer         # noqa: E402
import task_handler        # noqa: E402

display = sdl_display.SDLDisplay(
    data_bus=bus,
    display_width=WIDTH,
    display_height=HEIGHT,
    frame_buffer1=buf1,
    color_space=lv.COLOR_FORMAT.RGB888,
)
display.init()

mouse = sdl_pointer.SDLPointer()

# A 5 ms duration gives good mouse responsiveness (a thread handles double buffering).
th = task_handler.TaskHandler(duration=5)

# ------------------------- Demo interface ----------------------------------
scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x101820), 0)

slider = lv.slider(scr)
slider.set_size(300, 25)
slider.center()

label = lv.label(scr)
label.set_text("LVGL simulator")
label.align(lv.ALIGN.CENTER, 0, -50)
