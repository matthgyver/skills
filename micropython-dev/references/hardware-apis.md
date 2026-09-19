# Hardware APIs (machine module and friends)

Portable patterns that work across RP2, ESP32, and most other ports. Anything port-specific is flagged. When in doubt, check the quick reference for the target port at docs.micropython.org (`/rp2/quickref.html`, `/esp32/quickref.html`, ...) and probe with `dir(machine)`.

## Contents
- Pin and interrupts
- ADC
- PWM
- I2C
- SPI
- UART
- Timer
- Watchdog
- Sleep, reset cause, wake
- Time, RTC, NTP
- NeoPixel (WS2812)
- DHT11/DHT22
- DS18B20 (OneWire)
- Ultrasonic distance (HC-SR04)
- OLED (SSD1306) and framebuf

## Pin and interrupts

```python
from machine import Pin

led = Pin(15, Pin.OUT, value=0)
btn = Pin(14, Pin.IN, Pin.PULL_UP)     # wired to GND: pressed reads 0

led.value(1); led.on(); led.off(); led.toggle()
pressed = btn.value() == 0
```

Onboard LED: `Pin("LED")` on Pico W / Pico 2 W (and recent builds for the plain Pico); `Pin(25)` on older plain Pico builds. ESP32 dev boards vary (often GPIO 2 or a NeoPixel); ask or check the board schematic.

Interrupt with debounce, deferring the real work out of interrupt context:

```python
import time
from machine import Pin

_DEBOUNCE_MS = 50
_last_ms = 0
_pressed = False          # set in ISR, consumed in main loop

def _isr(pin):
    global _last_ms, _pressed
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_ms) > _DEBOUNCE_MS:
        _last_ms = now
        _pressed = True

btn = Pin(14, Pin.IN, Pin.PULL_UP)
btn.irq(trigger=Pin.IRQ_FALLING, handler=_isr)

while True:
    if _pressed:
        _pressed = False
        print("button")
    time.sleep_ms(10)
```

Rules: the handler gets the `Pin` as its argument; keep it allocation-free; use `Pin.IRQ_RISING | Pin.IRQ_FALLING` for both edges. Use `micropython.schedule(fn, arg)` to run bigger work soon after, in normal context.

## ADC

```python
from machine import ADC, Pin

adc = ADC(Pin(26))           # RP2: GP26-28 = ADC0-2. ESP32: use ADC1 pins (32-39)
raw = adc.read_u16()         # 0..65535 on every port, regardless of native resolution
volts = raw * 3.3 / 65535    # RP2 reference is 3.3 V
```

- **ESP32**: call `adc.atten(ADC.ATTN_11DB)` for a full ~0-3.3 V range (the response is nonlinear near the ends). Where available, `adc.read_uv()` returns calibrated microvolts. **ADC2 pins cannot be used while WiFi is active.**
- **RP2**: the internal temperature sensor is `ADC(4)` on RP2040 (recent builds also expose `ADC.CORE_TEMP`; RP2350 uses a different channel). `T = 27 - (volts - 0.706) / 0.001721`.
- Average several samples (for example 16) to reduce noise. Never exceed 3.3 V on an ADC pin; use a resistor divider for higher voltages.
- `adc.read()` is a legacy ESP32/ESP8266 call with a different range; avoid it.

## PWM

```python
from machine import PWM, Pin

pwm = PWM(Pin(15), freq=1000, duty_u16=32768)   # 50 % duty
pwm.duty_u16(16384)                              # 25 %
pwm.freq(2000)
pwm.deinit()                                     # release the pin/slice when done
```

- Hobby servo: 50 Hz, pulse 0.5-2.5 ms (1.0-2.0 ms is the usual safe range). Where `duty_ns` exists: `pwm.duty_ns(1_500_000)` is centre.
- RP2: pins share PWM slices in pairs (A/B channels). Two pins on the same slice cannot have different frequencies.
- `duty()` (0-1023) is a legacy ESP form; prefer `duty_u16`.
- On ESP32, changing the frequency on one PWM can affect others that share a timer.

## I2C

```python
from machine import I2C, Pin

i2c = I2C(0, scl=Pin(9), sda=Pin(8), freq=400_000)   # RP2: GP8=SDA, GP9=SCL for I2C0
print([hex(a) for a in i2c.scan()])                  # discover addresses

i2c.writeto_mem(0x48, 0x01, b"\x60")                 # write register
data = i2c.readfrom_mem(0x48, 0x00, 2)               # read 2 bytes from register
```

- RP2: each pin belongs to a fixed I2C instance (I2C0 or I2C1); check the pinout. ESP32: hardware I2C can use almost any pins.
- Any pins on any port: `SoftI2C(scl=Pin(5), sda=Pin(4), freq=100_000)` (slower, no instance constraints).
- Start at 100 kHz while debugging. External pull-ups (about 4.7 kOhm to 3.3 V) are required unless the breakout board has them.
- Use `readfrom_mem_into(addr, reg, buf)` with a preallocated `bytearray` in loops.
- Decode multi-byte values with `struct.unpack_from('>h', buf)` (big-endian signed 16-bit) or `int.from_bytes(buf, 'big')`.
- Empty `scan()` result: wiring, power, pull-ups, or wrong instance/pins. 5 V-only sensors may not respond at 3.3 V logic.

## SPI

```python
from machine import SPI, Pin

spi = SPI(0, baudrate=1_000_000, polarity=0, phase=0,
          sck=Pin(18), mosi=Pin(19), miso=Pin(16))    # RP2 SPI0 default pins
cs = Pin(17, Pin.OUT, value=1)                        # chip select is a normal GPIO

cs(0)
spi.write(b"\x9f")            # e.g. JEDEC ID command
ident = spi.read(3)
cs(1)

rx = bytearray(4)
spi.write_readinto(b"\x00\x00\x00\x00", rx)           # full duplex
```

Match `polarity`/`phase` to the device's SPI mode (CPOL/CPHA in the datasheet). Hold CS low across a whole transaction. `SoftSPI` exists for arbitrary pins.

## UART

```python
from machine import UART, Pin

uart = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5), timeout=100)   # RP2 UART1 on GP4/GP5

uart.write(b"AT\r\n")
if uart.any():
    line = uart.readline()        # bytes, or None on timeout
```

- TX of one device goes to RX of the other; grounds must be common; logic is 3.3 V.
- UART0 on the ESP32 is the REPL; use UART1 or UART2 for peripherals.
- For asyncio: `reader = asyncio.StreamReader(uart)` then `await reader.readline()`.
- GPS modules: NMEA sentences are lines; read with `readline()`, validate the checksum, parse with `split(',')`.

## Timer

```python
from machine import Timer

ticked = False

def tick(t):                      # runs in interrupt context: keep it tiny
    global ticked
    ticked = True

# RP2 (software timers, no id needed on recent builds):
tim = Timer(period=1000, mode=Timer.PERIODIC, callback=tick)
# ESP32: give a hardware id, e.g. Timer(0); ESP8266: Timer(-1)
# tim.deinit() to stop
```

Check the port quick reference for the exact constructor. For simple periodic work in an asyncio app, prefer a task with `await asyncio.sleep_ms(...)` over a hardware timer.

## Watchdog

```python
from machine import WDT

wdt = WDT(timeout=5000)     # ms. RP2 maximum is about 8388 ms
while True:
    do_work()
    wdt.feed()
```

Cannot be stopped once started on most ports. Feed it only when the whole program is healthy (for example after a successful loop iteration), not from a timer interrupt, otherwise it hides hangs. Do not enable it while debugging.

## Sleep, reset cause, wake

```python
import machine

machine.lightsleep(5000)          # ms; RAM and program state preserved; execution continues
machine.deepsleep(60_000)         # ms; board RESETS on wake and runs boot.py/main.py again

if machine.reset_cause() == machine.DEEPSLEEP_RESET:
    ...                           # woke from deep sleep
# other causes: PWRON_RESET, HARD_RESET, WDT_RESET, SOFT_RESET
```

- State does not survive `deepsleep`, except ESP32 RTC memory: `machine.RTC().memory(b"...")` (small, survives deep sleep).
- ESP32 wake sources: `esp32.wake_on_ext0/ext1`, touch pads, timer. Check `machine.wake_reason()`.
- Turn off radios (`wlan.active(False)`) and peripherals before sleeping; a connected USB serial link may drop while sleeping.

## Time, RTC, NTP

```python
import time, ntptime

ntptime.host = "pool.ntp.org"
try:
    ntptime.settime()             # sets RTC to UTC; blocks briefly; raises OSError on failure
except OSError:
    pass

y, mo, d, h, mi, s, wd, yd = time.localtime()   # UTC unless you offset it yourself
unix_ts = time.time() + 946684800               # embedded epoch is 2000-01-01
```

- No timezone or DST support in the firmware: apply the offset in your code (or a small helper for the rules you need).
- Without NTP or a battery-backed RTC, the clock restarts at 2000-01-01 after power loss. Use `ticks_ms()` for intervals; use RTC time only for timestamps.

## NeoPixel (WS2812)

```python
import neopixel
from machine import Pin

np = neopixel.NeoPixel(Pin(16), 8)     # 8 LEDs, RGB. Use bpp=4 for RGBW.
np[0] = (255, 0, 0)
np.fill((0, 0, 16))
np.write()                             # nothing changes until write()
```

Keep brightness low: each LED can draw about 60 mA at full white. Power long strips separately, share ground, and consider a 300-500 Ohm resistor in series with the data line and a 3.3 V to 5 V level shifter for reliability.

## DHT11 / DHT22

```python
import dht
from machine import Pin

sensor = dht.DHT22(Pin(4))             # or dht.DHT11
try:
    sensor.measure()
    t, h = sensor.temperature(), sensor.humidity()
except OSError:
    t = h = None                       # read failed: retry later
```

Minimum interval between reads: about 2 s for DHT22, 1 s for DHT11. Needs a pull-up on the data line (often built into the breakout).

## DS18B20 (OneWire)

```python
import onewire, ds18x20, time
from machine import Pin

ds = ds18x20.DS18X20(onewire.OneWire(Pin(4)))     # needs a 4.7 kOhm pull-up to 3V3
roms = ds.scan()
ds.convert_temp()
time.sleep_ms(750)                                  # conversion time at 12 bit
temp_c = ds.read_temp(roms[0])
```

In asyncio programs use `await asyncio.sleep_ms(750)` instead of the blocking sleep.

## Ultrasonic distance (HC-SR04)

```python
import time
from machine import Pin, time_pulse_us

trig = Pin(3, Pin.OUT, value=0)
echo = Pin(2, Pin.IN)             # HC-SR04 echo is 5 V: use a divider (e.g. 1k + 2k) or a 3.3 V variant

def distance_cm():
    trig.value(1); time.sleep_us(10); trig.value(0)
    us = time_pulse_us(echo, 1, 30_000)     # negative on timeout
    return None if us < 0 else us / 58
```

## OLED (SSD1306) and framebuf

```python
# mpremote mip install ssd1306
import ssd1306
from machine import I2C, Pin

i2c = I2C(0, scl=Pin(9), sda=Pin(8))
oled = ssd1306.SSD1306_I2C(128, 64, i2c)     # I2C address defaults to 0x3C
oled.fill(0)
oled.text("Hello", 0, 0)
oled.hline(0, 12, 128, 1)
oled.show()                                  # draw calls only touch the buffer until show()
```

`framebuf.FrameBuffer(buf, w, h, framebuf.MONO_HLSB)` is built in; the display driver subclasses it. The buffer for a 128x64 mono display is 1 KB. Larger colour displays (SPI TFT) need far more RAM: RGB565 at 240x240 is about 115 KB, so draw in strips or use a driver that streams.
