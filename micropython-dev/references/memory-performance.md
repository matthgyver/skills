# Memory and performance

Read this when the user hits `MemoryError`, when RAM is tight (ESP8266, big displays, TLS, long-running programs), or when code is too slow.

## Contents
- How the heap behaves
- Measuring
- Reducing RAM use
- Fragmentation
- Import cost, `.mpy`, and frozen modules
- Speed: `const`, locals, `native`, `viper`
- Interrupt-safe code
- Flash and filesystem

## How the heap behaves

- One garbage-collected heap holds all Python objects. Its size depends on the board (order of magnitude: ESP8266 about 30 KB free, ESP32 without PSRAM about 100 KB, RP2040 about 150-200 KB; ESP32 with PSRAM gives megabytes). Always measure with `gc.mem_free()` instead of trusting these numbers.
- Allocation needs a **contiguous** free block. After hours of churn the heap can have plenty of free memory in total and still fail a 4 KB allocation. That is fragmentation.
- Small ints are unboxed (no allocation), but **floats, big ints, strings, bytes, lists, dicts, tuples, closures, bound methods, and objects allocate**. A `for` loop creating a tuple or float each iteration is a steady source of garbage.
- The GC runs automatically when allocation fails or crosses a threshold; a collection takes milliseconds. Calling `gc.collect()` at a moment of your choosing (between work cycles, before a big allocation) avoids surprise pauses.

## Measuring

```python
import gc, micropython

gc.collect()
print(gc.mem_free(), gc.mem_alloc())     # bytes free / used
micropython.mem_info()                   # summary; mem_info(1) adds a heap map
                                         # heap map: '.' is free, letters mark object types

def measure(fn, *args):
    gc.collect()
    before = gc.mem_free()
    result = fn(*args)
    after = gc.mem_free()               # what is still retained
    return result, before - after
```

- Log `gc.mem_free()` periodically in long-running programs. A steady downward drift means a leak (a growing list/dict/log buffer, unclosed sockets, cached responses).
- `micropython.qstr_info()` shows interned-string usage; many unique dynamic strings used as keys or attribute names grow it.
- Time code with `time.ticks_us()` and `ticks_diff`, over many repetitions; single measurements are noisy.

## Reducing RAM use

**Buffers**
```python
buf = bytearray(64)                       # allocate once at start
mv = memoryview(buf)                      # slicing a memoryview does not copy
n = uart.readinto(buf)
handle(mv[:n])

i2c.readfrom_mem_into(addr, reg, buf)     # *_into variants avoid a new bytes per call
```

**Strings**
- Avoid `s += x` in loops (allocates a new string each time). Collect in a list and `''.join()`, or better, write pieces directly to the file/socket.
- `"%d" % n` or f-strings allocate; format outside hot loops and interrupt handlers.
- Use `bytes`/`bytearray` for binary and protocol data, not `str`.

**Data structures**
- `array.array('H', ...)` or `bytearray` for numeric series instead of lists of ints; one byte or two per element instead of one machine word (plus overhead).
- Tuples are smaller than lists and can be stored as constants; use them for fixed tables.
- Use generators and iterators instead of building large lists.
- Ring buffers with a fixed size for logs and samples; never an unbounded list.
- Class instances: define `__slots__ = ("a", "b")` for classes with many instances to avoid a per-instance dict.
- Avoid deep recursion; the C stack is small. Convert to loops.

**Code and imports**
- Import heavy modules only where used; `del` and `gc.collect()` after one-off work (for example a setup wizard).
- Do not `import *`.
- Keep big constant tables in flash: put them in a module compiled to `.mpy` or frozen into firmware, or read them from a file in chunks rather than loading everything.

**Reading and parsing**
- Stream JSON/CSV/HTTP bodies line by line instead of `read()` of the whole thing.
- Parse only the fields you need; do not keep the full decoded response.

## Fragmentation

- Allocate long-lived objects (buffers, big lists, objects with fixed lifetime) **early**, right after boot, before the heap gets churned.
- Allocate short-lived things after that, and let them go before the next big allocation.
- Call `gc.collect()` right before a large allocation (TLS handshake, HTTP download buffer, framebuffer).
- If allocation of a fixed-size block fails repeatedly, allocate it once and keep it rather than repeating.
- On boards with PSRAM (ESP32-S3, ESP32 WROVER), large buffers can go there automatically on firmware built with PSRAM support; check `gc.mem_free()` at boot to see whether the firmware uses it.

## Import cost, `.mpy`, and frozen modules

Importing a `.py` compiles it in RAM first, which can need much more memory than the resulting code. Two ways around this:

1. **Precompile with `mpy-cross`** to `.mpy` and copy that to `/lib`:
   ```bash
   mpy-cross -o build/lib/mydriver.mpy src/lib/mydriver.py
   ```
   Lower RAM at import, faster start. `boot.py` and `main.py` stay `.py`. The `.mpy` must match the firmware: compare `mpy-cross --version` with `sys.implementation._mpy & 0xFF` (mismatch gives `ValueError: incompatible .mpy file`). Use the `mpy-cross` from the same MicroPython release as the firmware.

2. **Freeze modules into the firmware** (`manifest.py` in a custom build, or `freeze()`). Frozen code is executed straight from flash and uses almost no RAM. This needs building firmware (see the MicroPython repo `ports/<port>/` docs), so recommend it only when `.mpy` is not enough.

## Speed

Measure before optimizing; first fix algorithms and allocations.

**Cheap wins**
- Bind globals and attributes to locals in hot loops:
  ```python
  def loop(pin, n):
      value = pin.value                # bound method cached once
      total = 0
      for _ in range(n):
          total += value()
      return total
  ```
- Use `const()` for fixed integers: `_REG_CTRL = const(0x10)` (module-private with the underscore prefix, inlined at compile time, no RAM for the name). Expressions of `const`s fold at compile time.
- Prefer integer math; avoid floats in hot paths (`x * 100 // 256` rather than `x * 0.390625`).
- Use `bytes.translate`, slicing on `memoryview`, and built-in functions in place of Python-level loops where they apply.
- `time.sleep_ms()` in the main loop lowers CPU use and heat. In asyncio, yield with `await asyncio.sleep_ms(0)` in long loops so other tasks run.

**`@micropython.native`**: compiles the function to machine code with Python semantics (typically about 2x faster, more RAM for the code). Works everywhere the port supports native emitters.

**`@micropython.viper`**: much faster (often 10x or more on tight integer loops), with restrictions: integer and pointer types via annotations, no floats, and machine-word integer semantics (values wrap around instead of growing into big ints).

```python
import micropython

@micropython.viper
def checksum(buf: ptr8, n: int) -> int:
    total = 0
    for i in range(n):
        total += buf[i]
    return total & 0xFF

data = bytearray(b"\x01\x02\x03\x04")
print(checksum(data, len(data)))
```

- `ptr8`, `ptr16`, `ptr32` give raw pointer access to `bytearray`/`array`; there is no bounds checking, so a wrong `n` corrupts memory. Validate length in normal Python before calling.
- Viper and native code need to be compiled for the right architecture when precompiling to `.mpy`: use `-march=` matching the chip (`mpy-cross --help` lists `armv6m`, `armv7emsp`, `xtensa`, `xtensawin`, `rv32imc`, ...). Compiling from source on the device needs no flag.
- On RP2, PIO (see `ports-and-boards.md`) is the right tool for precise timing and fast bit-banging; on ESP32, use `esp32.RMT` and `machine.bitstream` before hand-rolled loops.

**Bit-banging**: `machine.bitstream(pin, encoding, timing, data)` drives WS2812-style protocols from C, much faster than a Python loop.

## Interrupt-safe code

Handlers for `Pin.irq`, `Timer`, and similar run in interrupt context, and the heap is not safe there (allocation can corrupt or fail).

- Only: integer math, reading/writing preallocated buffers, setting a flag, `array`/`bytearray` element access.
- Not: `print`, string formatting, creating lists/dicts/tuples/objects, float math (may allocate), `time.sleep`, anything that raises.
- Move work out with `micropython.schedule(fn, arg)`. `fn(arg)` runs later in normal context. The schedule queue is small (default 8); a full queue raises `RuntimeError`, so keep handlers infrequent or count drops.
- Add `micropython.alloc_emergency_exception_buf(100)` at start so an error inside a handler prints a real message.
- Share data safely:
  ```python
  state = machine.disable_irq()
  try:
      snapshot = (counter, last_value)     # multi-variable read must be atomic
  finally:
      machine.enable_irq(state)
  ```
  Keep the critical section short; disabling interrupts also delays radios and USB.

## Flash and filesystem

- Free space: `os.statvfs('/')` returns `(f_bsize, f_frsize, f_blocks, f_bfree, ...)`; free bytes = `f_frsize * f_bfree`.
- Flash has limited erase cycles (order of 10k-100k per sector). Do not log every second to a file. Batch writes, append rather than rewrite, cap file sizes (rotate or truncate), and avoid writing in a crash loop.
- Power loss during a write can corrupt a file (LittleFS is resilient at the filesystem level but your application data can still be half-written). For critical state, write to a temporary file, then `os.rename` over the target.
- Two cores on RP2: writes to flash briefly stall the other core; keep flash access off latency-sensitive paths.
