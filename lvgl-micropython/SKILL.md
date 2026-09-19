---
name: lvgl-micropython
description: Design, build, debug and optimize LVGL graphical interfaces on MicroPython (ESP32/S3/C3/C6, RP2, STM32, Unix/SDL simulator). Covers firmware builds (community lvgl_micropython by kdschlosser, official lv_micropython), display and touch drivers (ST7789, ILI9341, ST7796, GC9A01, GT911, XPT2046, FT6x36, CST816S), SPI/I80/RGB buses, the task_handler loop, widgets, styles, flex/grid layouts, events, timers, animations, memory/GC, and LVGL 8-to-9 migration. Use whenever the user mentions LVGL with MicroPython, `import lvgl as lv`, `lcd_bus`, `task_handler`, a touchscreen on ESP32/Pico/CYD (Cheap Yellow Display)/T-Display/Waveshare boards, or wants an embedded GUI/HMI/dashboard in Python, even if they never write "LVGL". Also triggers on French requests such as "interface graphique sur ESP32", "écran tactile MicroPython", "mon écran reste blanc", "compiler le firmware LVGL".
---

# LVGL on MicroPython

LVGL is a C graphics library. On MicroPython it is exposed through an **automatically generated binding** built from the C headers, so the Python API closely mirrors the C API (`lv_button_create` becomes `lv.button(parent)`, `lv_obj_set_size(o, w, h)` becomes `o.set_size(w, h)`). The practical consequence: the exact name of a function depends on the **LVGL version compiled into the firmware** and on the **options in `lv_conf.h`**. Never guess an API name from memory when in doubt; verify it (see "Verify the API instead of guessing").

Reply in the user's language, and keep code, identifiers and log messages exactly as they appear in the API.

## Step 0: frame the problem before writing code

Most failures come from a wrong frame (wrong firmware, wrong API version). Collect the following, deducing what you can from the conversation and asking at most one grouped question for the rest:

1. **Board**: ESP32 (which variant? PSRAM? how much flash?), RP2, STM32, or the Unix simulator.
2. **Display**: controller (ST7789, ILI9341...), bus (SPI, I80/8-bit parallel, RGB), resolution.
3. **Touch**: controller (XPT2046, GT911, CST816S...) and bus (shared SPI or I2C).
4. **Firmware**: is LVGL already built in? At boot the REPL shows something like `Version: LVGL (9.2.2) MicroPython (1.24.1)`. If `import lvgl` fails, a firmware with LVGL must be built or flashed (see `references/build-and-bringup.md`).
5. **LVGL version** (8 or 9): it changes API names (see `references/api-v8-v9.md`).

If the user has a popular off-the-shelf board (CYD, T-Display S3, Waveshare ESP32-S3-Touch-LCD...), look for a working example for that exact board instead of reconstructing the wiring from memory: pinouts and quirks (color inversion, offsets, backlight polarity) are board-specific.

## Two ecosystems, do not mix them

| | **lvgl_micropython** (community, kdschlosser) | **lv_micropython / lv_binding_micropython** (official LVGL) |
|---|---|---|
| Repository | `github.com/lvgl-micropython/lvgl_micropython` | `github.com/lvgl/lv_micropython` |
| LVGL | 9.x | historically 8.x, check the branch |
| Build | `python3 make.py esp32 BOARD=... DISPLAY=... INDEV=...` | Makefile/CMake of the MicroPython fork |
| Drivers | modules `lcd_bus`, `st7789`, `xpt2046`...; `task_handler` | drivers shipped in the repo (`ili9XXX`, ...); `lv_utils.event_loop` |
| Targets | ESP32, RP2, STM32, unix, macOS... | ESP32, STM32, RP2, unix |

The community binding's README explicitly warns **not to use information from the official binding** to build it: build procedures and driver APIs differ. For a new ESP32 project, default to **lvgl_micropython (LVGL 9)** unless the user already has an official firmware or a version constraint. The **widget** API (`lv.button`, `lv.label`, styles, events) is the same in both; only bring-up (buses, drivers, loop) differs.

## Recommended workflow

1. **Iterate on the simulator first** when possible (`python3 make.py unix DISPLAY=sdl_display INDEV=sdl_pointer`, `assets/template_sdl_simulator.py`). Cycles are much shorter than flashing a board, and UI logic can be tested without hardware.
2. **Get the hardware working with a minimal screen** (one slider or label) before writing the application: this separates bus/color/touch problems from UI problems. Start from `assets/template_spi_display_touch.py`.
3. **Write the application** with hardware code (`board.py`: buses, display, touch) separate from UI code (`ui.py`), so it can also run on the simulator (see `assets/template_app_skeleton.py`).
4. **Debug** with `references/troubleshooting.md`, which maps symptoms to causes.

## Initialization order (lvgl_micropython)

Order matters, and breaking it produces confusing symptoms (shifted touch, black screen):

1. Create the bus (`lcd_bus.SPIBus` / `I80Bus` / `RGBBus`) and, if needed, allocate buffers.
2. Instantiate the display driver, then call `display.init()`.
3. Create the touch driver; calibrate if `not indev.is_calibrated`.
4. **Only then** call `display.set_rotation(...)`: the touch driver must exist before the rotation so coordinates follow it.
5. Turn the backlight on (`display.set_backlight(100)`), then create `task_handler.TaskHandler()`.
6. Build the interface on `lv.screen_active()`.

## Coding rules that prevent crashes

- **Keep a reference** to every object that must survive: display and input drivers, `lv.style_t`, grid descriptor arrays, `lv.timer_t`, animations, images (`image_dsc_t`) and buffers. The MicroPython garbage collector frees anything with no Python reference while LVGL still points to it, causing random crashes, often long after startup. Store them in module variables or on an application object.
- **Never block** in a callback (`time.sleep`, wait loops): the LVGL loop is driven by a timer and the UI freezes. Use `lv.timer_create`, `asyncio`, or a state machine.
- **Never call LVGL from an interrupt or another thread.** LVGL is not thread-safe. From a `Pin.irq`, set a flag or use `micropython.schedule(cb, arg)` and touch the UI inside `cb`.
- **Save RAM**: a partial display buffer (about 1/10 of the screen) is enough, DMA buffers go in internal RAM, large RGB buffers in PSRAM. Avoid creating and destroying hundreds of widgets in a loop; prefer hiding and reusing (`add_flag(lv.obj.FLAG.HIDDEN)` in v9). Add targeted `gc.collect()` calls outside animations.
- **Wrap callbacks in `try/except`** that prints the error (`sys.print_exception(e)`): an exception inside a callback can go unnoticed when no REPL is attached.
- **Prefer named functions or lambdas with captured values** over globals modified everywhere; with several screens, wrap each screen in a class that owns its widgets.

## Minimal skeleton (LVGL 9, after hardware initialization)

```python
import lvgl as lv

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x101820), 0)

btn = lv.button(scr)
btn.set_size(140, 50)
btn.align(lv.ALIGN.CENTER, 0, 0)

lbl = lv.label(btn)
lbl.set_text("Click me")
lbl.center()

count = 0
def on_click(e):
    global count
    count += 1
    lbl.set_text("Clicks: %d" % count)

btn.add_event_cb(on_click, lv.EVENT.CLICKED, None)
```

For richer patterns (styles, flex/grid, slider, chart, timers, animations, screen changes, asyncio, images), read `references/cookbook.md`.

## Verify the API instead of guessing

When a name fails (`AttributeError`) or the version is unclear:

- Read the REPL boot banner for the LVGL/MicroPython versions.
- Copy `scripts/lv_introspect.py` to the board (`mpremote cp scripts/lv_introspect.py :`), then run
  `mpremote exec "import lv_introspect as i; i.info(); i.find('long_mode')"`.
  The script lists available widgets, searches a term across the whole `lvgl` module, and prints a class's members (`i.members('label')`).
- A missing widget (`lv.chart`, `lv.font_montserrat_28`...) usually means it is **disabled in `lv_conf.h`**: the firmware must be rebuilt, it is not a code bug.
- The repository's `stubs/` folder gives IDE autocompletion.

## What this skill cannot state with certainty

Some details change from one version to another (enum names such as `lv.label.LONG.WRAP` versus `lv.label.LONG_MODE.WRAP`, the `image_dsc_t` header, exact driver constructor parameters, `TaskHandler` options). When a cookbook example is marked "verify", tell the user so and suggest the introspection check instead of asserting.

## Files in this skill

- `references/build-and-bringup.md`: building the firmware (`make.py` options, board variants, PSRAM), configuring bus/display/touch, calibration, SDL simulator. **Read whenever flashing, wiring or initializing a display.**
- `references/api-v8-v9.md`: LVGL 8 to 9 migration table, naming differences. **Read if the code comes from an older tutorial or on `AttributeError`.**
- `references/cookbook.md`: code recipes ready to adapt. **Read when building the interface.**
- `references/troubleshooting.md`: symptoms, likely causes, fixes (black screen, wrong colors, shifted touch, `MemoryError`, crashes, slowness, build errors).
- `scripts/lv_introspect.py`: API introspection on the board or the simulator.
- `assets/template_spi_display_touch.py`, `assets/template_sdl_simulator.py`, `assets/template_app_skeleton.py`: starting points to copy and adapt.
