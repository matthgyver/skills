---
name: micropython-dev
description: Write, review, debug, port, and deploy MicroPython code for microcontrollers (Raspberry Pi Pico / Pico W / Pico 2, ESP32 family, ESP8266, STM32/Pyboard, nRF, SAMD, and others). Use this skill whenever the user mentions MicroPython, boot.py/main.py, the machine module (Pin, I2C, SPI, UART, ADC, PWM, Timer, WDT), mpremote, mpy-cross, .mpy files, esptool or UF2 flashing of MicroPython firmware, asyncio on a microcontroller, umqtt, aioble, PIO, or sensor/display/WiFi/BLE projects on a Pico or ESP32 — even if they never say the word "MicroPython". Also use it to convert Arduino or CircuitPython code to MicroPython, write hardware drivers, fix MemoryError/OSError on a board, structure a firmware project, or set up testing and deployment. Not for Arduino C++ or CircuitPython-only work.
---

# MicroPython Development

MicroPython is a lean reimplementation of Python 3 for microcontrollers. Code that runs fine on a laptop often fails on a board because RAM is measured in kilobytes, much of the standard library is missing, and hardware APIs differ per port (RP2, ESP32, STM32...). Most bad MicroPython answers come from two mistakes: writing CPython-style code, and inventing APIs from Arduino or CircuitPython habits. This skill exists to prevent both.

## Workflow

1. **Pin down the target** (board/port, firmware version, peripherals, pins, connectivity).
2. **Pick building blocks** in this order: built-in module → micropython-lib package (via `mip`) → well-known community library → a small driver written from the datasheet.
3. **Write the code** following the conventions below: portable, allocation-aware, non-blocking, recoverable.
4. **Hand over a way to deploy and verify**: exact `mpremote` commands and the output the user should see.
5. **Debug from evidence**: the exact exception text, `micropython.mem_info()`, `os.uname()`. Never guess at pin numbers or API names.

## 1. Pin down the target

Determine, from the conversation first and by asking only if a wrong guess would produce non-working code:

| Question | Why it matters |
|---|---|
| Board / chip (Pico, Pico W, Pico 2, ESP32, ESP32-S3, ESP32-C3...) | Pin numbering, available modules, ADC/WiFi/BLE support |
| Firmware version (`sys.implementation.version`) | Module names and APIs change between releases |
| Peripherals and wiring | I2C/SPI/UART pin choices, voltage levels, pull-ups |
| Connectivity, power source | WiFi/BLE needs, sleep strategy |

If the user has not said, **state your assumptions in two or three lines and put pins and constants in a config block at the top of the code** so they are trivial to change. Do not interrogate the user with a long questionnaire.

If a board is attached and you have shell access, run `mpremote run scripts/device_info.py` to get the facts directly. Otherwise give the user that one-liner (or `mpremote exec "import os; print(os.uname())"`) and ask them to paste the output.

MicroPython releases keep renaming things (`uasyncio` → `asyncio`, `urequests` → `requests`, `upip` → `mip`, `ujson` → `json`). Prefer the modern names. When something might depend on the version, say so and point to the docs for the matching release (docs.micropython.org).

**CircuitPython is a different project.** If the user's code imports `board`, `digitalio`, `busio`, `analogio`, `supervisor`, or `adafruit_*`, it is CircuitPython, not MicroPython. Tell them, and translate it (see `references/ports-and-boards.md`). Many web tutorials mix the two.

## 2. What differs from CPython

Design for these from the first line, not after the first `MemoryError`.

- **Memory is scarce.** A Pico has roughly 150–200 KB of usable heap, a classic ESP32 about 100 KB, an ESP8266 about 30 KB. Every string, list, float, object, and closure lives there, and the heap fragments. See `references/memory-performance.md`.
- **Missing or reduced standard library.** No `pathlib`, `subprocess`, `dataclasses`, or `enum`; `typing` is absent at runtime (annotations are accepted but ignored, so never `import typing` unguarded); `os.path` is not in the core (use `os.stat` in `try/except`, or `mip install os-path`); `re` is a subset; `datetime` is not built in; `collections` is partial; `threading` is replaced by the low-level `_thread` (ESP32, RP2 only). Avoid `match/case`.
- **Do not rely on dict ordering.** Use `collections.OrderedDict` if order matters.
- **Epoch is 2000-01-01** on most embedded ports (Unix epoch on the Unix port). Add `946684800` to convert to Unix time. `time.localtime()` has no timezone support.
- **Floats are often single precision** (about 7 significant digits) and may allocate on the heap. Never accumulate time in floats; use integer milliseconds and `time.ticks_*`.
- **`ticks_ms()` wraps around.** Always compute elapsed time with `time.ticks_diff(now, start)`, and build deadlines with `time.ticks_add`. Never compare raw tick values.
- **Bare `except:` is dangerous.** It swallows `KeyboardInterrupt`, so Ctrl-C stops working and the board becomes hard to recover. Use `except Exception`.
- **Print tracebacks with `sys.print_exception(e)`**, not the `traceback` module.
- **Numeric errno values differ between ports.** Compare with names (`errno.ETIMEDOUT`), never with literals like `110`.
- **`.py` vs `.mpy`**: `.mpy` is precompiled bytecode. It loads faster and uses less RAM, but must match the firmware's mpy version.

## 3. Project layout and boot flow

```
project/
├── src/
│   ├── boot.py        # runs first; keep tiny, never loops
│   ├── main.py        # runs after boot.py
│   ├── config.py      # pins, constants, tunables
│   ├── secrets.py     # WiFi/API credentials (gitignored)
│   └── lib/           # drivers and helpers (on sys.path by default)
├── tests/             # pure-logic tests runnable on the Unix port
└── .gitignore
```

- **`boot.py` stays minimal.** A crash or infinite loop there makes the board hard to reach. Put real logic in `main.py`.
- **Leave an escape hatch during development.** Start `main.py` with a short window (about 2–3 s of `time.sleep_ms`, or a "held button skips main" check) so Ctrl-C or `mpremote` can always interrupt before a tight loop takes over. If a board is stuck, see the recovery steps in `references/tooling-workflow.md`.
- **Production entry point**: wrap the run loop, log the exception, wait, then `machine.reset()`. Re-raise `KeyboardInterrupt`. Rate-limit log writes so a crash loop cannot wear out flash. Template in `references/templates.md`.
- **Enable a watchdog** (`machine.WDT`) for unattended devices, and feed it from the main loop only. It cannot be stopped once started on most ports, so leave it out while iterating.
- **Credentials never go in code that is committed.** Use `secrets.py` or `config.json`, gitignored, with a `secrets.example.py` alongside.

## 4. Coding conventions

**Portability and API correctness**
- Use the portable API forms: `ADC.read_u16()` (0–65535 on every port), `PWM.duty_u16()`, `Pin(id, mode, pull, value=...)`, `time.sleep_ms()`.
- Use named constants (`Pin.IN`, `Pin.PULL_UP`, `network.STAT_GOT_IP`), never their numeric values; those differ per port.
- Do not invent APIs. If you are unsure that a method or module exists on the target, say so and give a check (`dir(machine)`, `help(module)`, `help('modules')`) rather than guessing. When unsure a library exists, offer to write a small driver instead of naming a package that may not exist.

**Timing and concurrency**
- Never write a bare `while True:` that spins without sleeping or awaiting.
- Pick one concurrency model per program and stick to it: a simple polling loop for small jobs, or `asyncio` when several things happen at once (sensor reads + network + button). In coroutines never call `time.sleep()`; use `await asyncio.sleep_ms()`. One blocking call freezes every task.
- Hardware timers and pin interrupts run in interrupt context. Keep handlers tiny: set a flag or store a value, nothing else. **No allocation in handlers** (no string formatting, new lists or dicts, floats), no blocking, no `print`. Defer real work with `micropython.schedule(fn, arg)` or a flag polled by the main loop. Call `micropython.alloc_emergency_exception_buf(100)` early so errors inside handlers are visible. Debounce with `ticks_diff`.
- Data shared between a handler and main code: keep it to single ints or preallocated buffers, and guard multi-step updates with `machine.disable_irq()` / `enable_irq(state)`.

**Memory habits** (details in `references/memory-performance.md`)
- Preallocate buffers once (`bytearray`, `memoryview`) and reuse them with `readinto` / `readfrom_mem_into`.
- Do not build strings with `+=` in loops; use `''.join()`, `bytearray`, or write pieces directly to the file/socket.
- Use `from micropython import const` for constants (`_REG = const(0x10)`; the leading underscore makes it module-private and costs no RAM).
- Import lazily inside rarely used functions, and `gc.collect()` before large allocations or after big transient work.
- Prefer generators and iterators over big lists.

**Robustness**
- Wrap I/O in `try/except OSError`. Sensors get unplugged and WiFi drops. Decide what to do (retry, back off, skip) instead of letting the program die.
- Always release resources: `close()` sockets and files (`with open(...)`, `try/finally`), and `deinit()` PWM, Timer, and UART when done.
- Limit flash writes. Do not rewrite a file every second. Batch, append, or keep state in RAM and save on change or on a slow schedule.
- On WiFi, always use a connect timeout and check `wlan.status()`; never loop forever on `isconnected()`.

**Style**
- Follow PEP 8. Type hints are optional (ignored at runtime) and add parse cost; use them sparingly for documentation only.
- Comment the *why* for hardware facts: the datasheet register, the timing requirement, the pin restriction.
- Cache attribute and global lookups in locals inside hot loops.

## 5. Choosing drivers and libraries

1. **Built in to the firmware**: `machine`, `neopixel`, `dht`, `onewire`, `ds18x20`, `framebuf`, `network`, `socket`, `bluetooth`, `rp2` (RP2 only), `esp32` (ESP32 only), `espnow` (ESP32), `struct`, `json`, `asyncio`.
2. **micropython-lib via `mip`**: `aioble` (BLE), `umqtt.simple` / `umqtt.robust` (MQTT), `ssd1306` (OLED), `requests` (HTTP), `unittest`, `os-path`, and more. Install from the host with `mpremote mip install <pkg>`, or on the board with `import mip; mip.install("<pkg>")` (needs network). Packages land in `/lib`. `upip` is obsolete.
3. **Well-known community libraries**: Peter Hinch's `micropython-async` and `mqtt_as` (robust async MQTT), Microdot (web server). Verify current install instructions before giving a command.
4. **Write a driver** when nothing fits. Use the I2C/SPI driver template in `references/templates.md`: read the datasheet's register map, check the chip ID on init, use preallocated buffers, and expose a small API.

## 6. Deploy, run, and verify

Give the user runnable commands, not just code. Essentials (full detail in `references/tooling-workflow.md`):

```bash
mpremote devs                         # list serial devices
mpremote run main.py                  # run from the host without copying
mpremote fs cp main.py :main.py       # copy a file to the board
mpremote fs cp -r lib :               # copy a directory to the board
mpremote fs ls                        # list files on the board
mpremote repl                         # interactive REPL (Ctrl-] to exit)
mpremote reset                        # hard reset
mpremote mip install aioble           # install a library from micropython-lib
```

`scripts/deploy.sh` syncs a `src/` tree to the board, optionally compiling `lib/` to `.mpy`. REPL keys: Ctrl-C interrupt, Ctrl-D soft reset, Ctrl-E paste mode.

Always finish a deliverable with: **how to run it, what output to expect, and what to check if it does not work** (wiring, address scan, `mem_info`).

## 7. Debugging playbook

Ask for the exact exception text and the board/firmware version. Then match:

| Symptom | Likely causes and fixes |
|---|---|
| `MemoryError` | Fragmentation or oversized allocation. `gc.collect()`, then `micropython.mem_info(1)`. Preallocate buffers, precompile to `.mpy`, freeze modules, avoid big lists and string concatenation, import lazily. |
| `OSError: [Errno 19] ENODEV` or `[Errno 5] EIO` on I2C | No device ACK. Check wiring, SDA/SCL swapped, missing pull-ups (about 4.7 kΩ), 3.3 V power, wrong address (`i2c.scan()`), wrong I2C instance for the pins (RP2 pins map to fixed instances), or use `SoftI2C`. |
| `ImportError: no module named 'x'` | Not in firmware and not in `/lib`. Check `help('modules')`, then `mip install`, then copy the file. |
| `ValueError: invalid pin` or `AttributeError` on `machine` | Wrong pin for this board or method not in this port. Check the port quick reference and `dir(machine)`. |
| `ValueError: incompatible .mpy file` | `mpy-cross` version does not match firmware. Compare `mpy-cross --version` with `sys.implementation._mpy & 0xFF`. |
| `OSError` on sockets (ETIMEDOUT, EHOSTUNREACH, ECONNRESET) | Not connected, DNS failure, server down. Verify `wlan.isconnected()`, ping by IP, set socket timeouts, retry with backoff. |
| WiFi never connects | Wrong password, 5 GHz-only network (radios are 2.4 GHz), hidden SSID, weak signal, missing `wlan.active(True)`, country code not set. Print `wlan.status()` and compare with `network.STAT_*` names. |
| Random resets | Brownout (weak USB or supply, motors/relays sharing the rail), watchdog not fed, deep-sleep wake (re-runs `boot.py`), recursion depth, crash loop. Check `machine.reset_cause()`. |
| Board unresponsive, `mpremote` cannot connect | `main.py` is in a tight loop. Press Ctrl-C repeatedly, or reset and interrupt inside the escape window. As a last resort erase the filesystem (see tooling reference). |
| ADC readings noisy or wrong | ESP32: ADC2 is unusable while WiFi is active, attenuation not set. RP2: no reference filtering; average several samples. Check the divider and the 3.3 V limit. |
| Callback silently does nothing | Exception inside an interrupt handler. Add `micropython.alloc_emergency_exception_buf(100)`, or move the work out of the handler with `schedule`. |
| Program slows down over hours | Memory leak or growing lists, fragmentation. Log `gc.mem_free()` periodically. |

Useful probes: `os.uname()`, `sys.implementation`, `gc.mem_free()`, `micropython.mem_info()`, `machine.freq()`, `machine.reset_cause()`, `help('modules')`, `dir(obj)`, `sys.print_exception(e)`, `os.statvfs('/')` for free flash.

## 8. Testing without hardware

- Keep logic (parsing, state machines, calibration math, protocol encoding) in functions and classes that take **injected** pins/buses, and keep hardware calls in a thin layer. That makes the logic testable off-device.
- Run pure-logic tests on the **Unix port** of MicroPython (`micropython tests/test_x.py`) so you exercise MicroPython semantics (not CPython) with no board attached. `unittest` comes from micropython-lib.
- For hardware classes, pass fake `Pin`/`I2C` objects (see the fake-bus example in `references/templates.md`).
- For editor support and linting, install the type stubs for the port (`pip install micropython-rp2-stubs`, `micropython-esp32-stubs`, ...) in the host environment.
- The final check is always on the real board. Say clearly which parts were verified only logically.

## 9. Delivering results

- For a project: a file tree, each file with its on-device path, a **wiring table** (signal → GPIO → connects to), deploy commands, expected output, and troubleshooting hints.
- For a question: a direct answer with a minimal, correct snippet. Skip the project scaffolding.
- Call out electrical facts that can destroy hardware: **3.3 V logic** (do not connect 5 V signals such as an HC-SR04 echo pin directly, and use a divider or level shifter), no motors, relays, or long LED strips driven straight from a GPIO (use a transistor/MOSFET, a flyback diode for inductive loads, and a common ground), and input-only or strapping pins on ESP32.
- Say which port and version the code targets, and mark anything port-specific in a comment.

## Reference files

Read only what the task needs:

| File | Read when |
|---|---|
| `references/hardware-apis.md` | Using Pin/IRQ, ADC, PWM, I2C, SPI, UART, Timer, WDT, sleep, RTC/NTP, NeoPixel, DHT, DS18X20, ultrasonic, OLED |
| `references/networking.md` | WiFi (STA/AP), HTTP client/server, sockets, MQTT, TLS, BLE with aioble, ESP-NOW, reliability patterns |
| `references/memory-performance.md` | `MemoryError`, fragmentation, speed-ups (`const`, `native`, `viper`), frozen modules, `.mpy`, ISR-safe code |
| `references/tooling-workflow.md` | Flashing firmware, `mpremote`, `mip`, `mpy-cross`, IDEs, permissions, recovering a stuck board |
| `references/ports-and-boards.md` | Port-specific pins and limits (RP2, ESP32, ESP8266, STM32...), PIO, translating from Arduino or CircuitPython |
| `references/templates.md` | Starting code: boot/main skeletons, config and secrets, asyncio app, I2C driver, logger, fake-bus tests |

Bundled scripts: `scripts/device_info.py` (run on the board via `mpremote run`, reports version, memory, filesystem, reset cause) and `scripts/deploy.sh` (sync `src/` to the board, optional `.mpy` compilation).
