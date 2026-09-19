# Ports and boards

Identify the port first: `sys.platform` returns `'rp2'`, `'esp32'`, `'esp8266'`, `'pyboard'`/`'stm32'`, `'linux'` (Unix port), and so on; `os.uname().machine` names the board (for example "Raspberry Pi Pico W with RP2040"). Pin names and limits below are typical. Verify against the board's pinout and the port quick reference before wiring anything.

## Contents
- Raspberry Pi RP2 (Pico, Pico W, Pico 2, Pico 2 W)
- ESP32 family
- ESP8266
- STM32 and Pyboard
- Other ports and the Unix port
- Translating from CircuitPython
- Translating from Arduino

## Raspberry Pi RP2 (Pico, Pico W, Pico 2, Pico 2 W)

**Basics**
- Pins are `Pin(n)` with `n` = GPIO number (GP0 to GP22, GP26 to GP28 broken out on the Pico), not the physical header pin.
- Logic is 3.3 V and **not 5 V tolerant**.
- Firmware images differ by board: Pico, Pico W, Pico 2, Pico 2 W. Use the one for the board in hand. Pico 2 (RP2350) has more RAM and speed; the code is the same.
- Onboard LED: `Pin("LED")` on the W boards (it is wired through the WiFi chip, not GPIO25). Plain Pico: `Pin(25)` or `Pin("LED")` on recent builds.
- On the W boards, GPIO23, 24, 25, 29 are used by the WiFi chip; GP29 (VSYS sense) is not a normal ADC input.

**Peripheral pin rules**
- **I2C**: for GPIO `n`, the instance is `(n // 2) % 2` (0 or 1); even pins are SDA, odd pins are SCL. Example: GP8/GP9 are I2C0 (SDA/SCL), GP6/GP7 are I2C1. Always pass the right instance number for the pins chosen, or use `SoftI2C`.
- **SPI/UART**: fixed pin groups per instance. Typical choices: `SPI(0)`: SCK=GP18, MOSI=GP19, MISO=GP16; `SPI(1)`: SCK=GP10, MOSI=GP11, MISO=GP12; `UART(0)`: TX=GP0, RX=GP1; `UART(1)`: TX=GP4, RX=GP5. CS is any GPIO.
- **ADC**: GP26, GP27, GP28 = ADC0-2; `ADC(4)` = internal temperature on RP2040.
- **PWM**: every GPIO can output PWM; pins share slices in pairs (see `hardware-apis.md`).

**Special features**
- **PIO**: programmable I/O state machines for precise timing (WS2812, custom protocols, quadrature, fast parallel output). Example square wave:
  ```python
  import rp2
  from machine import Pin

  @rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
  def square():
      wrap_target()
      set(pins, 1) [1]        # 1 cycle + 1 delay
      set(pins, 0) [1]
      wrap()

  sm = rp2.StateMachine(0, square, freq=2000, set_base=Pin(15))
  sm.active(1)                 # 2000 Hz / 4 cycles per period = 500 Hz on GP15
  ```
  Each PIO block has 4 state machines and 32 instruction slots.
- **Second core**: `_thread.start_new_thread(fn, args)` starts a function on core 1 (one extra thread). Share data through simple flags or `_thread.allocate_lock()`. Flash writes stall the other core.
- **Overclock**: `machine.freq(200_000_000)` on RP2040 works but is not guaranteed for all chips; mention the risk if suggested.
- WiFi country code: `rp2.country("FR")` on recent releases.
- Bootloader: `machine.bootloader()` or `mpremote bootloader` reboots into UF2 mode.
- Deep sleep exists (`machine.deepsleep`) but idle current on RP2 is not as low as on ESP32 boards; do not promise battery-life numbers.

## ESP32 family

**Variants**: ESP32 (dual-core Xtensa, WiFi + Bluetooth Classic/BLE), ESP32-S2 (WiFi only, native USB), ESP32-S3 (dual-core, WiFi + BLE, native USB, often PSRAM), ESP32-C3/C6 (RISC-V single-core, WiFi + BLE; C6 adds WiFi 6 and 802.15.4). Bluetooth: BLE only on S3/C3/C6; none on S2.

**Pin restrictions (classic ESP32)**
- GPIO34-39 are **input only** and have **no internal pull-ups/pull-downs**.
- GPIO6-11 are connected to the flash chip: never use them.
- Strapping pins affect boot: GPIO0 (must be high to boot normally; low enters download mode), GPIO2, GPIO5, GPIO12 (high at reset can select the wrong flash voltage and prevent boot), GPIO15. Avoid attaching loads that pull these at reset.
- ADC1 = GPIO32-39; **ADC2 (GPIO0, 2, 4, 12-15, 25-27) cannot be read while WiFi is active.**
- DAC on GPIO25/26 (`machine.DAC`) exists on the classic ESP32 only.
- Other variants have different maps. Check the module datasheet, especially for S3 (pins used by octal PSRAM/flash, USB on GPIO19/20) and C3 (USB on GPIO18/19).

**Peripherals**
- `I2C(0, scl=Pin(x), sda=Pin(y))` works on almost any pins; `SoftI2C` is also available.
- Classic ESP32 SPI defaults (verify in the quick reference): `SPI(1)`: SCK=14, MOSI=13, MISO=12; `SPI(2)`: SCK=18, MOSI=23, MISO=19.
- UART0 is the REPL; use UART1/UART2 for peripherals (pins are configurable).
- PWM via `machine.PWM` (LEDC): 8 to 16 channels depending on chip.
- Timers: `Timer(0)` to `Timer(3)`.
- Onboard LED differs per board (GPIO2 on many DevKits, a NeoPixel on others).

**ESP32-specific features**
- **NVS** (persistent key-value store in flash, robust for settings):
  ```python
  import esp32
  nvs = esp32.NVS("app")
  nvs.set_i32("boot_count", 5)
  nvs.commit()
  count = nvs.get_i32("boot_count")      # raises OSError if the key does not exist
  ```
- **RTC memory**: `machine.RTC().memory()` keeps a few bytes across deep sleep.
- **Deep sleep wake**: `esp32.wake_on_ext0(pin, level)`, `esp32.wake_on_ext1(...)`, touch pads, or a timer via `machine.deepsleep(ms)`.
- **ESP-NOW** and `network.WLAN` (see `networking.md`).
- **RMT** (`esp32.RMT`) for precise pulse trains (IR, WS2812), **I2S** (`machine.I2S`) for audio, **SD cards** (`machine.SDCard`).
- **PSRAM** boards: check `gc.mem_free()` at boot to confirm whether the firmware uses it.
- Threads: `_thread` works (FreeRTOS tasks); keep the count low and protect shared data.
- Suppress vendor debug output: `import esp; esp.osdebug(None)`.

## ESP8266

Legacy chip, still common on cheap boards. About 30-40 KB of free heap, one ADC (`ADC(0)`, 0-1 V input range, so use a divider), and limited GPIO.
- GPIO0, GPIO2, GPIO15 are strapping pins; GPIO16 does not support interrupts or PWM; GPIO6-11 are for flash.
- Hardware UART0 shares the REPL; UART1 is TX-only.
- `Timer(-1)` for a software timer.
- TLS/HTTPS is very memory-hungry; many operations fail with `MemoryError`. Freeze modules or use `.mpy`.
- For new projects, recommend ESP32 (or RP2 with a W board) instead.

## STM32 and Pyboard

- The `pyb` module is the legacy Pyboard API; **`machine` is preferred** for portable code, and `pyb` is still needed for some Pyboard-specific features.
- Pins are named strings (`Pin("A5")`, `Pin("X1")`). Use the board's pin naming diagram.
- Firmware flashes over DFU; the board also exposes a USB flash drive and a USB serial REPL.
- Timers, DMA, and hardware peripherals are rich and board-specific. Check the STM32 quick reference.
- `mpremote` works normally.

## Other ports and the Unix port

- **nRF (nRF52, nRF51)**: BLE-focused, small RAM; pin naming and USB support vary by board, so check the board page and the port quick reference.
- **SAMD21/SAMD51, Renesas RA, NXP i.MX RT (Teensy 4.x), Zephyr port**: consult the port's docs for pin naming and modules. Do not assume the ESP32 or RP2 APIs.
- **Unix port** (`micropython` binary on Linux/macOS): no `machine`, no `network`. Perfect for testing pure-logic modules and running `unittest` on the host. Its `time.time()` uses the Unix epoch, not 2000. Available from packages (often an older release) or built from the MicroPython repository.
- **WebAssembly port**: MicroPython in a browser; useful for demos, not hardware.

## Translating from CircuitPython

CircuitPython (Adafruit) is a fork with a different API. Its libraries (`adafruit_*`) generally will not import on MicroPython without changes.

| CircuitPython | MicroPython |
|---|---|
| `import board` / `board.LED`, `board.D5` | `Pin("LED")`, `Pin(5)` (GPIO numbers) |
| `digitalio.DigitalInOut(pin)`; `.direction`, `.value = True` | `Pin(n, Pin.OUT)`; `.value(1)` |
| `pull = digitalio.Pull.UP` | `Pin(n, Pin.IN, Pin.PULL_UP)` |
| `analogio.AnalogIn(board.A0).value` (0-65535) | `ADC(Pin(26)).read_u16()` (0-65535) |
| `pwmio.PWMOut(pin, frequency=..., duty_cycle=...)` | `PWM(Pin(n), freq=..., duty_u16=...)` |
| `busio.I2C(scl, sda)` + `i2c.try_lock()` | `I2C(0, scl=Pin(), sda=Pin())`, no lock needed |
| `busio.SPI(clk, MOSI, MISO)` | `SPI(0, sck=Pin(), mosi=Pin(), miso=Pin())` |
| `busio.UART(tx, rx)` | `UART(1, tx=Pin(), rx=Pin())` |
| `time.monotonic()` (seconds, float) | `time.ticks_ms()` with `ticks_diff` |
| `time.sleep(0.1)` | `time.sleep_ms(100)` or `time.sleep(0.1)` |
| `code.py`, `boot.py`, USB drive `CIRCUITPY` | `main.py`, `boot.py`, no USB drive; use `mpremote`/Thonny |
| Auto-reload on save | None; copy the file and reset (or `mpremote run`) |
| `supervisor`, `microcontroller.cpu`, `alarm` | Not available; use `machine`, `machine.deepsleep` |
| `neopixel.NeoPixel(board.NEOPIXEL, n)` | `neopixel.NeoPixel(Pin(n), n)` |
| `adafruit_ssd1306`, `adafruit_bme280` ... | `ssd1306` from micropython-lib; find or write a MicroPython driver |
| `wifi.radio.connect(...)`, `socketpool`, `adafruit_requests` | `network.WLAN`, `socket`, `requests` |
| `asyncio` (same idea) | `asyncio` (`import asyncio`) |

## Translating from Arduino

| Arduino | MicroPython |
|---|---|
| `setup()` / `loop()` | Setup at module level, `while True:` loop with sleeps (or an asyncio `main()`) |
| `pinMode(p, OUTPUT)` | `Pin(p, Pin.OUT)` |
| `digitalWrite(p, HIGH)` / `digitalRead(p)` | `pin.value(1)` / `pin.value()` |
| `INPUT_PULLUP` | `Pin.IN, Pin.PULL_UP` |
| `analogRead(p)` (0-1023) | `adc.read_u16() >> 6` (scale to 10 bit) or use the 16-bit value directly |
| `analogWrite(p, 0..255)` | `pwm.duty_u16(v * 257)` (0-255 scaled to 0-65535) |
| `delay(ms)` / `delayMicroseconds(us)` | `time.sleep_ms(ms)` / `time.sleep_us(us)` |
| `millis()` / `micros()` | `time.ticks_ms()` / `time.ticks_us()` (with `ticks_diff`) |
| `Serial.println(x)` | `print(x)` (goes to the REPL/USB serial) |
| `attachInterrupt(pin, isr, FALLING)` | `pin.irq(trigger=Pin.IRQ_FALLING, handler=isr)` |
| `Wire.beginTransmission` / `Wire.write` | `i2c.writeto(addr, data)` / `i2c.writeto_mem(...)` |
| `SPI.transfer` | `spi.write_readinto(tx, rx)` |
| `tone(pin, freq)` | `PWM(Pin(pin), freq=freq, duty_u16=32768)` |
| `map(x, a, b, c, d)` | `(x - a) * (d - c) // (b - a) + c` |
| `EEPROM`, `Preferences` | Files (JSON) or `esp32.NVS` on ESP32 |
| Blocking `delay()` in loops | Prefer `ticks_diff` timing or asyncio so other work continues |
