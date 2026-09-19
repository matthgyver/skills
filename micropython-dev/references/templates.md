# Code templates

Starting points to adapt. Every template is written to be portable across ports; pins and constants live in `config.py`. Change names, pins, and addresses to match the user's hardware.

## Contents
- `boot.py`
- `config.py` and `secrets.example.py`
- Polling `main.py` with escape window, watchdog, crash log
- Non-blocking periodic timing helper
- asyncio application
- Settings persistence (JSON, safe write)
- I2C sensor driver
- Host-side tests with a fake bus

## `boot.py`

```python
# boot.py: runs first on every reset. Keep it tiny and never loop here.
import gc

gc.collect()
# import esp; esp.osdebug(None)   # ESP32/ESP8266: silence vendor debug output
```

## `config.py` and `secrets.example.py`

```python
# config.py: everything the user might need to change for their wiring or behaviour.
VERSION = "0.1.0"

# --- Wiring (GPIO numbers; "LED" is the onboard LED on Pico W) ---
PIN_LED = "LED"
I2C_ID = 0
PIN_I2C_SDA = 8
PIN_I2C_SCL = 9
I2C_FREQ = 400_000

# --- Behaviour ---
SAMPLE_INTERVAL_MS = 10_000
DEV_ESCAPE_MS = 3000        # startup window in which Ctrl-C / mpremote can interrupt; set 0 in production
WDT_TIMEOUT_MS = 8000       # 0 disables the watchdog (RP2 maximum is about 8388)
CRASH_LOG = "crash.log"
CRASH_LOG_MAX_BYTES = 4096
```

```python
# secrets.example.py: copy to secrets.py (gitignored) and fill in.
WIFI_SSID = "your-network"
WIFI_PASSWORD = "your-password"
MQTT_HOST = "192.168.1.10"
```

## Polling `main.py` with escape window, watchdog, crash log

```python
# main.py
import os
import sys
import time

import machine

import config


def log(msg):
    print("[%d ms] %s" % (time.ticks_ms(), msg))


def log_crash(exc):
    """Append a traceback to a size-capped file. Must never raise."""
    try:
        try:
            if os.stat(config.CRASH_LOG)[6] > config.CRASH_LOG_MAX_BYTES:
                os.remove(config.CRASH_LOG)
        except OSError:
            pass
        with open(config.CRASH_LOG, "a") as f:
            f.write("--- t=%d ms reset_cause=%d version=%s\n"
                    % (time.ticks_ms(), machine.reset_cause(), config.VERSION))
            sys.print_exception(exc, f)
    except Exception:
        pass


def setup():
    """Create hardware objects once; return whatever the loop needs."""
    led = machine.Pin(config.PIN_LED, machine.Pin.OUT)
    return led


def run():
    led = setup()
    wdt = machine.WDT(timeout=config.WDT_TIMEOUT_MS) if config.WDT_TIMEOUT_MS else None
    log("started v%s" % config.VERSION)

    next_sample = time.ticks_ms()
    while True:
        now = time.ticks_ms()
        if time.ticks_diff(now, next_sample) >= 0:
            next_sample = time.ticks_add(now, config.SAMPLE_INTERVAL_MS)
            led.toggle()
            # ... read sensors, publish, etc. Wrap flaky I/O in try/except OSError.
        if wdt:
            wdt.feed()            # only reached when the loop is healthy
        time.sleep_ms(20)


def main():
    if config.DEV_ESCAPE_MS:
        time.sleep_ms(config.DEV_ESCAPE_MS)     # Ctrl-C here drops to the REPL
    try:
        run()
    except KeyboardInterrupt:
        raise                                   # let the developer stop the program
    except Exception as e:
        sys.print_exception(e)
        log_crash(e)
        time.sleep(5)                           # avoid a fast crash loop
        machine.reset()


main()
```

Notes: `except Exception` does not catch `KeyboardInterrupt` (it is a `BaseException`), but the explicit re-raise documents intent. Never use a bare `except:`.

## Non-blocking periodic timing helper

For polling loops that run several jobs at different intervals without `asyncio`.

```python
import time


class Every:
    """Returns True from due() once per period, drift-free, safe across tick wrap-around."""

    def __init__(self, period_ms):
        self.period = period_ms
        self.next = time.ticks_add(time.ticks_ms(), period_ms)

    def due(self):
        now = time.ticks_ms()
        if time.ticks_diff(now, self.next) >= 0:
            self.next = time.ticks_add(self.next, self.period)
            return True
        return False


# usage
read_sensor = Every(5_000)
publish = Every(60_000)
while True:
    if read_sensor.due():
        pass  # read
    if publish.due():
        pass  # send
    time.sleep_ms(10)
```

## asyncio application

Use when several activities overlap (sensors, network, buttons, display). One `main()`; tasks share state through plain objects (single-threaded, so no locks are needed unless a task awaits in the middle of a multi-step update).

```python
import asyncio
from machine import Pin

import config

state = {"temp_c": None, "button_presses": 0}
button_flag = asyncio.ThreadSafeFlag()        # safe to set() from an interrupt handler


def _button_isr(pin):
    button_flag.set()                         # no allocation, no work here


async def sensor_task():
    while True:
        try:
            state["temp_c"] = 21.5            # replace with a real read, e.g. sensor.temperature_c()
        except OSError as e:
            print("sensor error:", e)         # log and keep going
        await asyncio.sleep_ms(config.SAMPLE_INTERVAL_MS)


async def button_task(pin):
    while True:
        await button_flag.wait()
        await asyncio.sleep_ms(30)            # debounce
        button_flag.clear()
        if pin.value() == 0:
            state["button_presses"] += 1
            print("presses:", state["button_presses"])


async def heartbeat_task():
    led = Pin(config.PIN_LED, Pin.OUT)
    while True:
        led.toggle()
        await asyncio.sleep_ms(500)


async def main():
    button = Pin(14, Pin.IN, Pin.PULL_UP)
    button.irq(trigger=Pin.IRQ_FALLING, handler=_button_isr)
    tasks = (
        asyncio.create_task(sensor_task()),
        asyncio.create_task(button_task(button)),
        asyncio.create_task(heartbeat_task()),
    )
    await asyncio.gather(*tasks)


try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()                  # clear scheduler state so a re-run after Ctrl-C works
```

Rules: no `time.sleep()` inside coroutines; wrap each task's body in `try/except Exception` so one failure does not silently end that task (a task that raises stops without stopping the others when created with `create_task`); a watchdog task that feeds `WDT` only while a health flag is true detects a frozen loop.

## Settings persistence (JSON, safe write)

```python
import json
import os


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):       # missing file or corrupt JSON
        return default


def save_json(path, obj):
    """Write to a temp file first so a power cut cannot leave a half-written settings file."""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    try:
        os.rename(tmp, path)
    except OSError:                     # some filesystems cannot rename over an existing file
        os.remove(path)
        os.rename(tmp, path)
```

Save only when a value changes, not on a timer. On ESP32, `esp32.NVS` is an alternative for small settings.

## I2C sensor driver

Register map below is an example: replace addresses, IDs, and scaling using the chip's datasheet. Patterns to keep: `const` register names, a chip-ID check at init (fails fast on wiring/address mistakes), one reused buffer, `_into` reads, integer math where possible.

```python
"""Driver for a 16-bit I2C temperature sensor (example register map)."""
from micropython import const

_ADDR_DEFAULT = const(0x48)
_REG_TEMP = const(0x00)      # result, signed 16-bit, 1/128 degC per LSB
_REG_CONFIG = const(0x01)
_REG_ID = const(0x0F)
_CHIP_ID = const(0x0117)


class TempSensor:
    def __init__(self, i2c, addr=_ADDR_DEFAULT):
        self._i2c = i2c
        self._addr = addr
        self._buf = bytearray(2)        # reused for every transfer: no allocation in the read path
        chip_id = self._read_u16(_REG_ID)
        if chip_id != _CHIP_ID:
            raise OSError("unexpected chip id 0x%04x at address 0x%02x" % (chip_id, addr))

    def _read_u16(self, reg):
        self._i2c.readfrom_mem_into(self._addr, reg, self._buf)
        return (self._buf[0] << 8) | self._buf[1]        # big-endian

    def _write_u16(self, reg, value):
        self._buf[0] = (value >> 8) & 0xFF
        self._buf[1] = value & 0xFF
        self._i2c.writeto_mem(self._addr, reg, self._buf)

    def temperature_c(self):
        raw = self._read_u16(_REG_TEMP)
        if raw & 0x8000:                                  # two's complement
            raw -= 0x10000
        return raw / 128

    def temperature_mc(self):
        """Integer milli-degrees C: avoids floats in tight loops."""
        raw = self._read_u16(_REG_TEMP)
        if raw & 0x8000:
            raw -= 0x10000
        return raw * 1000 // 128
```

Usage:

```python
from machine import I2C, Pin
from tempsensor import TempSensor

i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=400_000)
print([hex(a) for a in i2c.scan()])         # confirm the address first
sensor = TempSensor(i2c)
print(sensor.temperature_c())
```

Driver checklist: accept an already-created bus object (so several devices can share it), document units, raise `OSError` or `ValueError` on bad input rather than returning garbage, add `deinit()`/`sleep()` if the chip has a low-power mode, and keep the public API small.

## Host-side tests with a fake bus

Test logic on the Unix port (`micropython tests/test_tempsensor.py`, with `unittest` installed by `mip install unittest`) without hardware. Inject a fake bus that mimics the two methods the driver uses.

```python
# tests/test_tempsensor.py
import unittest
import sys

sys.path.insert(0, "src/lib")                 # find the driver when running on the host
from tempsensor import TempSensor


class FakeI2C:
    def __init__(self, regs):
        self.regs = regs                      # {register: 2-byte value}

    def readfrom_mem_into(self, addr, reg, buf):
        buf[:] = self.regs[reg]

    def writeto_mem(self, addr, reg, data):
        self.regs[reg] = bytes(data)


def make(temp_raw):
    regs = {0x0F: b"\x01\x17", 0x00: temp_raw.to_bytes(2, "big")}
    return TempSensor(FakeI2C(regs))


class TestTempSensor(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(make(0x0C80).temperature_c(), 25.0)      # 3200 / 128

    def test_negative(self):
        self.assertEqual(make(0xFF80).temperature_c(), -1.0)      # -128 / 128

    def test_milli_degrees(self):
        self.assertEqual(make(0x0C80).temperature_mc(), 25000)

    def test_wrong_chip_id(self):
        regs = {0x0F: b"\x00\x00", 0x00: b"\x00\x00"}
        with self.assertRaises(OSError):
            TempSensor(FakeI2C(regs))


if __name__ == "__main__":
    unittest.main()
```

Tips: keep parsing, scaling, state machines, and protocol code free of `machine` imports so they can be tested this way; for modules that must import `machine`, create a fake `machine` module in `tests/` and put it first on `sys.path`. Always state which behaviour was verified on the host and which still needs a real board.
