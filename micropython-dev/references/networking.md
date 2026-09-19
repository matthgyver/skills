# Networking (WiFi, HTTP, MQTT, BLE, ESP-NOW)

Applies to boards with a radio: Pico W / Pico 2 W (CYW43), ESP32 family, ESP8266. Plain Pico boards have no WiFi.

## Contents
- WiFi station (client) with timeout and status handling
- Access point mode
- HTTP client
- HTTP server
- MQTT
- NTP and TLS notes
- BLE with aioble
- ESP-NOW (ESP32)
- Reliability patterns

## WiFi station

```python
import network, time

def wifi_connect(ssid, password, timeout_s=20, hostname=None):
    """Return a connected WLAN or raise OSError. Never blocks forever."""
    wlan = network.WLAN(network.STA_IF)
    if hostname:
        network.hostname(hostname)          # set before connecting
    wlan.active(True)
    if wlan.isconnected():
        return wlan
    wlan.connect(ssid, password)

    # Status constants have different numeric values per port: compare by name.
    failures = set()
    for name in ("STAT_WRONG_PASSWORD", "STAT_NO_AP_FOUND", "STAT_CONNECT_FAIL"):
        if hasattr(network, name):
            failures.add(getattr(network, name))

    deadline = time.ticks_add(time.ticks_ms(), timeout_s * 1000)
    while not wlan.isconnected():
        if wlan.status() in failures:
            raise OSError("wifi failed, status=%d" % wlan.status())
        if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
            raise OSError("wifi timeout, status=%d" % wlan.status())
        time.sleep_ms(200)
    return wlan

# ip, netmask, gateway, dns = wlan.ifconfig()
```

Notes:
- Radios are **2.4 GHz only**. A 5 GHz-only network never appears in a scan.
- Set the regulatory country where the port supports it (for example `network.country("FR")` or `rp2.country("FR")` on recent releases); otherwise some channels may be unavailable.
- Scan: `wlan.scan()` returns tuples `(ssid, bssid, channel, RSSI, security, hidden)` as bytes for ssid/bssid.
- Static IP: `wlan.ifconfig(("192.168.1.50", "255.255.255.0", "192.168.1.1", "1.1.1.1"))` before/after connecting.
- On ESP32, a failed attempt sometimes needs `wlan.disconnect()` before retrying.
- Pico W power saving can add latency to inbound connections; if a server on the board is slow to answer, try `wlan.config(pm=network.WLAN.PM_PERFORMANCE)` (older builds: the raw value `0xa11140`).
- Reconnect in the main loop: if `not wlan.isconnected()`, call `wifi_connect` again with backoff (5 s, 10 s, 20 s... capped at a few minutes).

## Access point mode

```python
import network
ap = network.WLAN(network.AP_IF)
ap.config(essid="my-device", password="at-least-8-chars")   # WPA2 needs 8+ chars
ap.active(True)
print(ap.ifconfig())          # gateway/IP is commonly 192.168.4.1
```

Typical use: a captive configuration page where the user enters home WiFi credentials, which the device saves and then uses in station mode.

## HTTP client

```python
import requests          # recent firmware / `mpremote mip install requests`; older builds: urequests

r = requests.get("http://example.com/api", timeout=10)     # timeout supported on recent versions
try:
    if r.status_code == 200:
        data = r.json()
finally:
    r.close()            # always close: sockets and RAM are limited
```

- Always close the response. Leaking sockets is the classic cause of `OSError` after a few hours.
- `requests.post(url, json={...})` and `headers={...}` work as in CPython.
- HTTPS needs RAM (TLS buffers can take tens of KB). Call `gc.collect()` before the request and reuse connections sparingly.
- Large downloads: do not call `r.content` or `r.text`; read in chunks from `r.raw` (or `r.raw.readinto(buf)`) and write to a file.
- Time-bound everything: set timeouts; otherwise a dead server hangs the device.

Raw-socket fallback for tiny requests:

```python
import socket
addr = socket.getaddrinfo("example.com", 80)[0][-1]
s = socket.socket()
try:
    s.settimeout(10)
    s.connect(addr)
    s.send(b"GET / HTTP/1.0\r\nHost: example.com\r\n\r\n")
    data = s.recv(512)
finally:
    s.close()
```

## HTTP server

For a status page or a small JSON API, use **Microdot** (small async-capable framework; check its docs for the current install method) or a hand-rolled asyncio server:

```python
import asyncio

async def handle(reader, writer):
    try:
        request_line = await reader.readline()          # b"GET /path HTTP/1.1\r\n"
        while (await reader.readline()) not in (b"\r\n", b""):
            pass                                        # skip headers
        body = b'{"ok": true}'
        writer.write(b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n")
        writer.write(body)
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle, "0.0.0.0", 80)
    while True:
        await asyncio.sleep(3600)

asyncio.run(main())
```

Keep handlers short, limit request size, and never trust input. Do not expose an unauthenticated control endpoint to the internet.

## MQTT

```python
# mpremote mip install umqtt.simple    (umqtt.robust builds on it)
from umqtt.robust import MQTTClient
import time

def on_message(topic, msg):            # both are bytes
    print(topic, msg)

client = MQTTClient("device-01", "broker.local", port=1883, keepalive=60)
client.set_callback(on_message)
client.connect()
client.subscribe(b"home/device-01/cmd")

last_pub = time.ticks_ms()
while True:
    client.check_msg()                 # non-blocking; call often
    if time.ticks_diff(time.ticks_ms(), last_pub) > 10_000:
        client.publish(b"home/device-01/temp", b"21.5")
        last_pub = time.ticks_ms()
    time.sleep_ms(50)
```

- Use bytes for topics and payloads.
- With `keepalive` set, the loop must run `check_msg()` (or `ping()`) regularly or the broker drops you.
- `umqtt.robust` retries publishes after reconnecting; plain `umqtt.simple` raises `OSError` when the link breaks, so wrap in try/except and reconnect.
- For asyncio applications with unreliable WiFi, `mqtt_as` (by Peter Hinch) is the robust choice.
- TLS: pass `ssl=` with an `ssl.SSLContext` (see below).
- Publish JSON with `json.dumps(obj).encode()`.

## NTP and TLS notes

- `ntptime.settime()` sets UTC (see `hardware-apis.md`). TLS certificate validation needs a correct clock, so sync time first.
- Prefer `ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)` over the deprecated `ssl.wrap_socket`. Certificate verification depends on the port and firmware; unverified TLS protects against eavesdropping but not against impersonation. Say so when disabling verification, and load a CA certificate where the port supports it.
- TLS handshakes need a large contiguous heap block: `gc.collect()` first, and retry on `MemoryError` after freeing RAM.

## BLE with aioble

`bluetooth` is the low-level IRQ-based API; **aioble** (`mpremote mip install aioble`) is the asyncio wrapper and the right default. Available on ESP32 (classic, S3, C3...), Pico W / Pico 2 W, and some STM32 boards.

Peripheral (advertise + notify a temperature):

```python
import asyncio, struct, bluetooth
import aioble

_ENV_SENSING = bluetooth.UUID(0x181A)
_TEMP_CHAR = bluetooth.UUID(0x2A6E)
_ADV_INTERVAL_US = 250_000

service = aioble.Service(_ENV_SENSING)
temp_char = aioble.Characteristic(service, _TEMP_CHAR, read=True, notify=True)
aioble.register_services(service)

async def sensor_task():
    while True:
        temp_char.write(struct.pack("<h", int(read_temp_c() * 100)), send_update=True)
        await asyncio.sleep_ms(2000)

async def advertise_task():
    while True:
        async with await aioble.advertise(
            _ADV_INTERVAL_US, name="my-sensor", services=[_ENV_SENSING]
        ) as connection:
            await connection.disconnected()

async def main():
    await asyncio.gather(sensor_task(), advertise_task())

asyncio.run(main())
```

Central (scan and read):

```python
async def find_and_read():
    async with aioble.scan(5000, interval_us=30_000, window_us=30_000, active=True) as scanner:
        async for result in scanner:
            if result.name() == "my-sensor":
                device = result.device
                break
        else:
            return None
    connection = await device.connect()
    async with connection:
        service = await connection.service(_ENV_SENSING)
        char = await service.characteristic(_TEMP_CHAR)
        raw = await char.read()
        return struct.unpack("<h", raw)[0] / 100
```

Notes: use standard 16-bit UUIDs where a standard profile exists; encode values with `struct`; handle `aioble.DeviceDisconnectedError` and timeouts; BLE and WiFi coexist on ESP32 and Pico W but eat RAM. Only one central connection strategy at a time on small chips.

## ESP-NOW (ESP32)

Connectionless peer-to-peer messaging between ESP32s; no router needed; low latency; up to 250 bytes per message.

```python
import network, espnow

sta = network.WLAN(network.STA_IF)
sta.active(True)                       # required before ESP-NOW
en = espnow.ESPNow()
en.active(True)

peer = b"\xbb\xbb\xbb\xbb\xbb\xbb"     # peer's MAC (see: sta.config("mac"))
en.add_peer(peer)
en.send(peer, b"hello")

host, msg = en.recv(1000)              # timeout in ms; host is None if nothing arrived
```

## Reliability patterns

- **Timeouts everywhere**: connect, socket, HTTP, MQTT. A missing timeout is a frozen device.
- **Retry with backoff**, capped, plus jitter if many devices share a server.
- **Supervisor loop**: check link health each iteration and reconnect; if repeated failures exceed a threshold, `machine.reset()`.
- **Watchdog** feeds only after a successful cycle (see `hardware-apis.md`).
- **Store and forward** when offline: buffer readings in a small ring buffer or an append-only file with a size cap, and flush on reconnect. Avoid unbounded lists.
- **Do not block the event loop** with synchronous `requests` calls in an asyncio app that must stay responsive; run them in a dedicated task and accept the pause, or use an async HTTP approach.
- **Secrets** come from `secrets.py`; never log passwords or tokens.
