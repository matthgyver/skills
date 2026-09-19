# device_info.py: print a compact, paste-able report about a MicroPython board.
#
# Run from the host (nothing is copied to the board):
#     mpremote run scripts/device_info.py
#
# Every section is guarded, so it works on any port (RP2, ESP32, STM32, Unix...).
# It does not activate WiFi or Bluetooth and does not write to flash.

import gc
import os
import sys

_MPY_ARCH = (
    "none", "x86", "x64", "armv6", "armv6m", "armv7m", "armv7em",
    "armv7emsp", "armv7emdp", "xtensa", "xtensawin", "rv32imc", "debug", "rv64imc",
)


def section(title):
    print("\n== " + title)


def show(label, fn):
    try:
        print("%-14s %s" % (label + ":", fn()))
    except Exception as e:  # report and carry on: a missing feature is information too
        print("%-14s (unavailable: %s)" % (label + ":", e))


def mpy_info():
    v = sys.implementation._mpy
    version = v & 0xFF
    sub = (v >> 8) & 3
    arch = v >> 10
    name = _MPY_ARCH[arch] if arch < len(_MPY_ARCH) else str(arch)
    return "mpy v%d.%d, native arch %s (raw %d)" % (version, sub, name, v)


def version_string():
    v = sys.implementation.version
    text = ".".join(str(x) for x in v[:3])
    if len(v) > 3 and v[3]:
        text += "-" + str(v[3])      # e.g. "preview"
    return text


def reset_cause():
    import machine

    cause = machine.reset_cause()
    names = [n for n in dir(machine) if n.endswith("_RESET") and getattr(machine, n) == cause]
    return "%s (%d)" % (names[0] if names else "unknown", cause)


def flash_usage():
    st = os.statvfs("/")
    block = st[1]
    total, free = st[2] * block, st[3] * block
    return "%d KB free of %d KB" % (free // 1024, total // 1024)


def memory():
    gc.collect()
    free, used = gc.mem_free(), gc.mem_alloc()
    return "%d KB free, %d KB used" % (free // 1024, used // 1024)


def freq():
    import machine

    return "%d MHz" % (machine.freq() // 1_000_000)


def unique_id():
    import machine

    return "".join("%02x" % b for b in machine.unique_id())


def importable(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def modules_report():
    # Import-safe modules only (none of these switch a radio on).
    names = (
        "machine", "network", "bluetooth", "rp2", "esp32", "espnow", "asyncio",
        "neopixel", "dht", "onewire", "ds18x20", "framebuf", "socket", "ssl",
        "json", "re", "struct", "hashlib", "ntptime", "mip", "requests", "urequests",
    )
    have = [n for n in names if importable(n)]
    missing = [n for n in names if n not in have]
    print("present:      ", " ".join(have))
    print("not present:  ", " ".join(missing))


def lib_report():
    for path in ("/lib", "/flash/lib", "lib"):
        try:
            entries = sorted(os.listdir(path))
        except OSError:
            continue
        print("%s: %s" % (path, " ".join(entries) if entries else "(empty)"))
        return
    print("no /lib directory")


def root_files():
    return " ".join(sorted(os.listdir("/")))


print("MicroPython device report")

section("Firmware")
show("platform", lambda: sys.platform)
show("version", version_string)
show("board", lambda: os.uname().machine)
show("release", lambda: os.uname().release)
show("build", lambda: os.uname().version)
show("mpy format", mpy_info)

section("Hardware")
show("cpu freq", freq)
show("unique id", unique_id)
show("reset cause", reset_cause)

section("Memory and storage")
show("heap", memory)
show("flash fs", flash_usage)
show("root files", root_files)

section("Modules (import check, no radios activated)")
try:
    modules_report()
except Exception as e:
    print("(unavailable: %s)" % e)

section("Installed libraries")
lib_report()

print("\n== end of report")
