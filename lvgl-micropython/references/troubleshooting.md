# Troubleshooting LVGL + MicroPython

General method: **isolate**. First get a minimal screen working (`assets/template_spi_display_touch.py`), then the application. Change one thing at a time and read the REPL messages in full (exceptions, ESP-IDF backtraces).

## Table of contents

1. Black or white screen
2. Wrong colors
3. Distorted, shifted or noisy image
4. Touch missing, shifted or inverted
5. `MemoryError`
6. Random crashes and reboots
7. Frozen or choppy interface
8. `AttributeError`, `ImportError`, missing widget
9. Build and flash errors
10. First bring-up checklist

## 1. Black or white screen

| Likely cause | Check / fix |
|---|---|
| `display.init()` never called | Call it after creating the driver |
| Backlight off | `backlight_pin=` set and `display.set_backlight(100)`; on some boards the backlight is active-low |
| Wrong pinout (DC, CS, MOSI, SCK, RST) | Compare with the board schematic, not with a tutorial for another board |
| SPI frequency too high | Lower it (for example 80 MHz to 40 MHz or 20 MHz), long wires on a breadboard |
| Wrong controller model | Some modules sold as "ILI9341" are ST7789 or the reverse; try the other driver |
| LVGL loop missing | Create `task_handler.TaskHandler()` and **keep the reference** |
| Nothing drawn | Check that widgets are created on `lv.screen_active()` and that an opaque background does not hide everything |

## 2. Wrong colors

- Red and blue swapped: toggle `color_byte_order` between `BYTE_ORDER_RGB` and `BYTE_ORDER_BGR` of the driver module.
- "Dirty" or mixed colors on intermediate shades: try `rgb565_byte_swap=True` / `False`.
- Negative image (white background instead of black): `display.invert_colors()`.
- These three settings depend on the panel; test them separately, in this order, with a test interface using pure colors (red, green, blue).

## 3. Distorted, shifted or noisy image

- A few pixels of shift, a stray line: the panel's controller is larger than the visible matrix (ST7789 240x240, GC9A01, small ST7735). Look for the driver's offset parameters (`help(st7789.ST7789)` or the source in `api_drivers/common_api_drivers/display/`).
- Swapped dimensions: pass `display_width`/`display_height` in the panel's native orientation, then rotate with `display.set_rotation(...)` (after creating the touch driver).
- Noise or flicker on an RGB screen (S3): lower the pixel clock, check the panel porches, use partial buffers in PSRAM, stable power supply.

## 4. Touch missing, shifted or inverted

- Nothing reacts: check the I2C address (`i2c.scan()`), SDA/SCL/INT/RST pins, I2C frequency (start at 100 kHz), a separate CS for an XPT2046 on a shared SPI bus.
- Global offset: run `indev.calibrate()`. On ESP32 the calibration is stored in NVRAM; force it with `indev.calibrate()` if the screen orientation changed.
- Axes inverted after rotation: the touch driver must be **created before** `display.set_rotation(...)`, and calibration done **before** the rotation.
- Odd behavior on a shared SPI: use `machine.SPI.Device(spi_bus=..., freq=..., cs=...)` on the same `spi_bus` as the display, with a low touch frequency (~10 MHz or less).

## 5. `MemoryError`

| Context | Lead |
|---|---|
| Allocating a buffer | Partial buffers (~1/10 of the screen), internal DMA memory for SPI/I80, PSRAM for RGB; drop the second buffer |
| Creating widgets | Fewer simultaneous widgets, reuse instead of recreate, `gc.collect()` before heavy screens |
| Importing large modules | Freeze modules into the firmware (`FROZEN_MANIFEST=`) or compile to `.mpy` with `mpy-cross` |
| Board without PSRAM | Lower resolution or color depth, no full-screen images in RAM |

Diagnosis: `import gc; gc.collect(); print(gc.mem_free())` before and after each step.

## 6. Random crashes and reboots

Suspects, from most to least frequent:

1. **Object freed by the GC while LVGL uses it**: style, grid array, timer, animation, image, display/touch driver, `TaskHandler`. Symptom: crash after some delay or after a `gc.collect()`. Fix: keep a reference (module variable, class attribute).
2. **LVGL call from an ISR or another thread**: go through `micropython.schedule`, or a flag read in an LVGL timer. Same with `--dual-core-threads`: add locks.
3. **A callback that repeatedly raises an exception**: wrap in `try/except` with `sys.print_exception(e)`.
4. **Insufficient stack** in deep or recursive callbacks: simplify; on ESP32, `--task-stack-size=` at build time.
5. **Power supply**: backlight plus Wi-Fi on a weak USB port causes brown-outs; test with a solid supply.

## 7. Frozen or choppy interface

- Frozen: a `time.sleep` or wait loop in a callback; an exception stopped the LVGL loop task; the timer is no longer referenced.
- Slow to touch: long callbacks, computation in the event loop (offload or split with `asyncio`).
- Low FPS:
  - raise the SPI bus frequency if the panel supports it;
  - DMA buffers in internal RAM (SPI/I80);
  - avoid invalidating the whole screen (large animated images, gradients, shadows, large radii, opacities);
  - reduce the `TaskHandler` period only if the CPU has headroom;
  - on RGB: suitable partial buffers, rotation handled by the driver rather than LVGL.

## 8. `AttributeError`, `ImportError`, missing widget

- `AttributeError: 'module' object has no attribute 'btn'` (or `scr_act`): LVGL 8 code on an LVGL 9 firmware. See `api-v8-v9.md`.
- `AttributeError` on a method: name differs between versions, or the method is absent; use `i.find('word')` with `scripts/lv_introspect.py`.
- Widget, font or feature not found although it exists in the LVGL docs: disabled in the build's `lv_conf.h`. Rebuild with the right option (it is not a code bug).
- `ImportError: no module named 'lvgl'`: firmware without LVGL. Flash an LVGL firmware (`references/build-and-bringup.md`).
- `ImportError` on `st7789`, `xpt2046`, `task_handler`...: the driver was not included in the build (`DISPLAY=`, `INDEV=`), or wrong firmware/binding.

## 9. Build and flash errors

| Symptom | Lead |
|---|---|
| Build failures after following an official-binding tutorial | This community binding is installed **without** manually initializing submodules; delete the folder and clone again |
| Inconsistent errors after changing options | Add `clean`; for mpy-cross too |
| Python/ESP-IDF environment error | Python >= 3.10, system packages from the README (cmake, ninja, libusb...) |
| Build succeeds but the board boot-loops | Wrong memory variant: `BOARD_VARIANT=SPIRAM_OCT` (octal PSRAM) and `--octal-flash` only if the flash is octal; `--flash-size=` consistent with the board |
| No REPL after flashing on a native-USB board | Choose the channel: `--enable-cdc-repl=y` (and `--enable-uart-repl=n` if needed) |
| Port not found when flashing | Hold BOOT while plugging in, try `/dev/ttyACM0` then `/dev/ttyUSB0`, `dialout` group permissions |
| C3/C6: build fails | Check the repository issues for the target; some chips have little RAM |

## 10. First bring-up checklist

1. `import lvgl as lv` works and the banner shows the version.
2. The bus is created, the display driver instantiated, `display.init()` called.
3. Backlight on.
4. A solid color background displays (test R, G, B colors).
5. `TaskHandler` created and referenced.
6. A slider responds to touch (touch OK, calibrated, rotation applied afterwards).
7. Only then: the application.
