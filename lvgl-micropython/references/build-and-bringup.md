# Firmware build and hardware bring-up

This reference is based on the **lvgl-micropython/lvgl_micropython** repository (LVGL 9). The repository moves fast: when unsure about an option, run `python3 make.py --help` and read the repository README before asserting anything.

## Table of contents

1. Why a custom firmware
2. Prerequisites
3. Building (commands, options)
4. Flashing
5. Supported buses and drivers
6. Initialization: SPI display + touch (annotated example)
7. Other buses: I80 and RGB
8. Unix/SDL simulator
9. Calibration and rotation
10. Choosing buffers

## 1. Why a custom firmware

LVGL is compiled **into** the MicroPython firmware: there is no `mip` package to install. The binding is generated from the C headers according to `lv_conf.h`, so available widgets and fonts depend on the build. A prebuilt LVGL firmware for a specific board may exist (look at the board's repository); otherwise, build one.

## 2. Prerequisites

- Python >= 3.10 on the build machine.
- Ubuntu for ESP32: `build-essential cmake ninja-build python3 python3-venv libusb-1.0-0-dev`.
- For RP2/STM32, add `gcc-arm-none-eabi libnewlib-arm-none-eabi`.
- For the Unix simulator: many SDL development libraries (X11, ALSA, Wayland...); the full list is in the README.
- Windows: not natively supported for several targets; suggest WSL2 or a Linux VM.

## 3. Building

Clone **without** initializing submodules by hand (the script handles them):

```bash
git clone https://github.com/lvgl-micropython/lvgl_micropython
cd lvgl_micropython
```

Syntax: `python3 make.py {target} {build options} {target options} {global options}`.

First build for an ESP32-S3 with octal PSRAM and an ST7789 display:

```bash
python3 make.py esp32 submodules clean mpy_cross \
    BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT DISPLAY=st7789
```

Later builds (the `submodules` and `mpy_cross` parameters are no longer needed):

```bash
python3 make.py esp32 clean BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT DISPLAY=st7789
```

Example with an ST7796 display and a GT911 touch controller:

```bash
python3 make.py esp32 BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT DISPLAY=st7796 INDEV=gt911
```

Useful options:

| Option | Purpose |
|---|---|
| `BOARD=` / `BOARD_VARIANT=` | Board model and variant (e.g. `ESP32_GENERIC_S3` + `SPIRAM_OCT`, `ESP32_GENERIC` + `SPIRAM`) |
| `DISPLAY=` / `INDEV=` | Display / input driver to embed (repeatable for several drivers, or a path to a custom driver) |
| `--flash-size={4,8,16,...}` | Board flash size in MB |
| `--octal-flash` | Octal flash (some S3 boards); a wrong setting causes a boot loop |
| `--enable-cdc-repl=y` / `--enable-uart-repl=n` / `--enable-jtag-repl=y` | REPL channel on boards with native USB |
| `--optimize-size` | Smaller firmware at the cost of speed |
| `--ota` / `--partition-size=` | Two application partitions for OTA updates |
| `--dual-core-threads` | Experimental: code on both cores, GIL disabled, you must add locks yourself |
| `--ccache` | Speeds up rebuilds |
| `CONFIG_*=value` | Override ESP-IDF configuration |
| `FROZEN_MANIFEST=path/manifest.py` | Freeze Python modules into the firmware (saves RAM) |
| `LV_CFLAGS="..."` | Compiler flags passed to LVGL only |
| `--custom-board-path=` / `--toml=` | Custom board, TOML file (see `custom_board_and_toml_examples/` in the repo) |
| `deploy` `PORT=` `BAUD=` | Flash directly after the build |

Other targets: `rp2`, `stm32`, `unix`, `macOS`, `nrf`, `mimxrt`, `samd`, `renesas-ra`. Some boards have too little RAM or flash to run LVGL: say so plainly rather than insisting.

To **update**, delete the local folder and clone again (the authors recommend this) rather than running `git pull` with submodules.

## 4. Flashing

At the end of the build, the script prints **two commands** to run in order: the first erases memory, the second writes the firmware. Replay them as printed, adapting the serial port (`/dev/ttyACM0`, `/dev/ttyUSB0`, `COMx`) and possibly the speed (`-b 460800` instead of `921600` for weak USB-serial bridges). On some S3/C3/C6 boards, hold the BOOT button while plugging in USB to enter the bootloader.

## 5. Supported buses and drivers

Bundled display controllers: GC9A01, HX8357B/D, ILI9163, ILI9225, ILI9341, ILI9481, ILI9486, ILI9488, R61581, RM68120, RM68140, S6D02A1, SSD1351, SSD1963 (variants), ST7735B/R, ST7789, ST7796; LT768x, RA8876 and ST7701S are flagged "WIP". A generic RGB panel goes through `rgb_display`.

Touch controllers: CST816S, FT5x06/16/26/36/46, FT6x06, FT6x36, GT911, STMPE610, XPT2046.

Buses in `lcd_bus`: `SPIBus`, `I80Bus` (8/16-bit parallel), `RGBBus`, and `SDLBus` for the simulator.

## 6. Initialization: SPI display + XPT2046 touch on the same bus

Pattern from the README (adapt to the board's pinout). ESP32 SPI host 0 is reserved for flash/PSRAM: use host 1 or 2.

```python
import machine
import lcd_bus
from micropython import const

_WIDTH, _HEIGHT = const(320), const(480)
_BL, _DC = const(45), const(0)
_MOSI, _MISO, _SCK = const(11), const(13), const(12)
_HOST = const(1)                       # SPI2; host 0 is taken by flash
_LCD_CS, _LCD_FREQ = const(10), const(80000000)
_TOUCH_CS, _TOUCH_FREQ = const(18), const(10000000)

spi_bus = machine.SPI.Bus(host=_HOST, mosi=_MOSI, miso=_MISO, sck=_SCK)
display_bus = lcd_bus.SPIBus(spi_bus=spi_bus, freq=_LCD_FREQ, dc=_DC, cs=_LCD_CS)

import st7796
import lvgl as lv

display = st7796.ST7796(
    data_bus=display_bus,
    display_width=_WIDTH, display_height=_HEIGHT,
    backlight_pin=_BL,
    color_space=lv.COLOR_FORMAT.RGB565,
    color_byte_order=st7796.BYTE_ORDER_RGB,
    rgb565_byte_swap=True,
)

import task_handler
import xpt2046

display.set_power(True)
display.init()
display.set_backlight(100)

touch_dev = machine.SPI.Device(spi_bus=spi_bus, freq=_TOUCH_FREQ, cs=_TOUCH_CS)
indev = xpt2046.XPT2046(touch_dev)

th = task_handler.TaskHandler()        # keep the reference!
```

Points of attention:

- Without explicit buffers, the driver picks a reasonable size and location itself. To set them: `fb = display_bus.allocate_framebuffer(size_bytes, lcd_bus.MEMORY_INTERNAL | lcd_bus.MEMORY_DMA)`, then pass it via `frame_buffer1=` (and `frame_buffer2=` for double buffering).
- The color parameters (`color_byte_order`, `rgb565_byte_swap`, and `display.invert_colors()`) depend on the panel. They are the number one cause of "red and blue swapped" or negative colors (see troubleshooting).
- The driver module and class vary: `st7789.ST7789`, `ili9341.ILI9341`, `st7796.ST7796`, etc. To list accepted parameters: `help(st7789.ST7789)` on the board, or read the `api_drivers/common_api_drivers/display/` folder of the repository.

## 7. Other buses

**I80 (8-bit parallel)**: `lcd_bus.I80Bus(dc=..., wr=..., freq=..., data0=...data7=...)`, two buffers in internal DMA RAM (`lcd_bus.MEMORY_INTERNAL | lcd_bus.MEMORY_DMA`), then the display driver with `frame_buffer1/2`. Touch is often on I2C:

```python
import i2c
i2c_bus = i2c.I2C.Bus(host=0, scl=5, sda=6, freq=100000, use_locks=False)
touch_dev = i2c.I2C.Device(bus=i2c_bus, dev_id=ft6x36.I2C_ADDR, reg_bits=ft6x36.BITS)
indev = ft6x36.FT6x36(touch_dev)
```

**RGB (16-bit parallel panels, ESP32-S3)**: `lcd_bus.RGBBus(hsync=..., vsync=..., de=..., pclk=..., data0=...data15=..., freq=..., hsync_front_porch=..., ...)` with the `rgb_display` driver. The two full-frame buffers are managed in C; the user allocates **partial buffers** in PSRAM (`bus.allocate_framebuffer(size, lcd_bus.MEMORY_SPIRAM)`), about 1/10 of the screen to start. Timings (porches, pulse widths, pixel clock) come from the panel datasheet: do not invent them, look for the exact board's configuration (for instance the repository discussions for the Waveshare ESP32-S3-Touch-LCD boards).

## 8. Unix/SDL simulator

```bash
python3 make.py unix DISPLAY=sdl_display INDEV=sdl_pointer
```

The resulting MicroPython binary is printed at the end of the build. Do not enable `LV_USE_DRAW_SDL` (unsupported). See `assets/template_sdl_simulator.py`. The simulator is also valuable for developing the UI away from the hardware: keep interface construction in a module that does not depend on the bus.

## 9. Calibration and rotation

- The touch driver follows the rotation set on the display **provided** the display is initialized, then the touch driver is created, **then** the rotation is applied.
- On ESP32, calibration is stored in NVRAM across reboots: `if not indev.is_calibrated: indev.calibrate()`.
- Recalibration can be forced at any time with `indev.calibrate()` (for example from a button in the UI).
- Calibrate before rotating the screen to keep corners correctly oriented: `display.set_rotation(lv.DISPLAY_ROTATION._90)`.

## 10. Choosing buffers

| Situation | Recommendation |
|---|---|
| SPI/I80, limited internal RAM | Two partial buffers (~1/10 of the screen, a few tens of KB), in `MEMORY_INTERNAL` and `MEMORY_DMA` combined |
| SPI with PSRAM | Let the driver choose, or internal DMA partial buffers for speed |
| RGB | Partial buffers in `MEMORY_SPIRAM`, never full-screen |
| `MemoryError` at allocation | Reduce the size, drop one buffer, check `BOARD_VARIANT=SPIRAM...` and that PSRAM is detected (`import esp32`, `gc.mem_free()`) |
