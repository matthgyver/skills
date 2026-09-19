"""Template: SPI display + SPI touch (XPT2046) on the same bus, lvgl_micropython binding.

TO ADAPT (see the CONFIG block): pins, resolution, display driver module.
Based on the example in the README of github.com/lvgl-micropython/lvgl_micropython.

Required firmware: built with DISPLAY=<controller> and INDEV=xpt2046.
For another display controller, replace `st7796` / `ST7796` with the matching
module and class (e.g. st7789.ST7789, ili9341.ILI9341).

Order matters: display -> touch -> rotation -> backlight -> TaskHandler.
"""

from micropython import const
import machine
import lcd_bus

# ----------------------------- CONFIG --------------------------------------
WIDTH = const(320)          # native panel dimensions
HEIGHT = const(480)
PIN_BL = const(45)          # backlight
PIN_DC = const(0)
PIN_MOSI = const(11)
PIN_MISO = const(13)
PIN_SCK = const(12)
SPI_HOST = const(1)         # SPI2; host 0 is reserved for flash/PSRAM
PIN_LCD_CS = const(10)
LCD_FREQ = const(40000000)  # start conservative (40 MHz), raise later
PIN_TOUCH_CS = const(18)
TOUCH_FREQ = const(10000000)
ROTATION = None             # e.g. lv.DISPLAY_ROTATION._90, or None
# ---------------------------------------------------------------------------

spi_bus = machine.SPI.Bus(host=SPI_HOST, mosi=PIN_MOSI, miso=PIN_MISO, sck=PIN_SCK)
display_bus = lcd_bus.SPIBus(spi_bus=spi_bus, freq=LCD_FREQ, dc=PIN_DC, cs=PIN_LCD_CS)

import lvgl as lv          # noqa: E402
import st7796              # noqa: E402  (adapt to your controller)
import xpt2046             # noqa: E402
import task_handler        # noqa: E402

# Without frame_buffer1/2 the driver picks size and location. To set them:
#   fb1 = display_bus.allocate_framebuffer(size_bytes,
#                                          lcd_bus.MEMORY_INTERNAL | lcd_bus.MEMORY_DMA)
display = st7796.ST7796(
    data_bus=display_bus,
    display_width=WIDTH,
    display_height=HEIGHT,
    backlight_pin=PIN_BL,
    color_space=lv.COLOR_FORMAT.RGB565,
    color_byte_order=st7796.BYTE_ORDER_RGB,   # try BYTE_ORDER_BGR if red/blue are swapped
    rgb565_byte_swap=True,                    # try False if colors look mixed
)

display.set_power(True)
display.init()
# display.invert_colors()                     # uncomment if the image is negative
display.set_backlight(100)

touch_dev = machine.SPI.Device(spi_bus=spi_bus, freq=TOUCH_FREQ, cs=PIN_TOUCH_CS)
indev = xpt2046.XPT2046(touch_dev)

if not indev.is_calibrated:
    indev.calibrate()                         # follow the on-screen instructions

if ROTATION is not None:
    display.set_rotation(ROTATION)            # AFTER creating and calibrating the touch driver

# Keep the reference: without it the LVGL loop stops at the first garbage collection.
th = task_handler.TaskHandler()

# ------------------------- Minimal test screen -----------------------------
scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x000000), 0)

label = lv.label(scr)
label.set_text("LVGL OK")
label.align(lv.ALIGN.CENTER, 0, -50)

slider = lv.slider(scr)
slider.set_size(240, 30)
slider.center()


def on_slide(e):
    label.set_text("Value: %d" % slider.get_value())


slider.add_event_cb(on_slide, lv.EVENT.VALUE_CHANGED, None)
