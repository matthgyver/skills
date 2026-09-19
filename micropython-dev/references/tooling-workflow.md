# Tooling and workflow

## Contents
- Host tool setup
- Flashing firmware (RP2, ESP32, STM32)
- Serial access and permissions
- mpremote in practice
- Installing libraries with mip
- Precompiling with mpy-cross
- Recovering a stuck or corrupted board
- Editors and IDEs
- Type stubs and linting
- Custom firmware and frozen modules
- Project hygiene

## Host tool setup

```bash
pip install mpremote mpy-cross esptool    # esptool only needed for ESP boards
mpremote --version
mpy-cross --version                       # should match the firmware release
```

Use a virtual environment (`python -m venv .venv`) on machines that manage Python packages system-wide.

## Flashing firmware

Get the firmware for the **exact board** from micropython.org/download (search by board name). Prefer the latest stable release unless the user needs a specific version.

### Raspberry Pi Pico / Pico W / Pico 2 (RP2)
1. Hold the BOOTSEL button while plugging in USB (or run `mpremote bootloader` if MicroPython is already running).
2. A drive named `RPI-RP2` (RP2040) or `RP2350` appears.
3. Copy the `.uf2` file onto it. The board reboots into MicroPython on its own.
4. Pico vs Pico W vs Pico 2 vs Pico 2 W each have their own `.uf2`. The wrong one may run without WiFi or misbehave.

### ESP32 family
```bash
# list ports: mpremote devs   (Linux /dev/ttyUSB0 or /dev/ttyACM0, macOS /dev/cu.usbserial-*, Windows COM3)
esptool --port /dev/ttyUSB0 erase-flash
esptool --port /dev/ttyUSB0 --baud 460800 write-flash 0x1000 ESP32_GENERIC-<version>.bin
```
- Flash offset depends on the chip: **`0x1000` for ESP32 and ESP32-S2; `0x0` for ESP32-S3, ESP32-C3, ESP32-C6.** Use the value shown on the firmware's download page.
- Older esptool uses `esptool.py`, `erase_flash`, `write_flash`; underscores still work in newer versions with a deprecation notice.
- Some boards need BOOT held while pressing EN/RESET to enter download mode. Boards with native USB (S3/C3 with USB-JTAG) may enumerate as a different port after flashing.
- Always erase first when switching between MicroPython versions or from other firmware.

### STM32 (Pyboard, Nucleo, others)
Use DFU mode with `dfu-util` or the vendor tool; the board page on micropython.org lists exact steps. Pyboard: `mpremote` works the same as on other boards.

## Serial access and permissions

- **Linux**: add the user to the serial group, then log out and back in: `sudo usermod -aG dialout $USER` (Debian/Ubuntu; `uucp` on Arch). "Permission denied" on `/dev/ttyACM0` is almost always this.
- **macOS**: ports look like `/dev/cu.usbmodem*`. Prefer `cu.*` over `tty.*`.
- **Windows**: a `COMx` port; check Device Manager. Boards using CH340/CP210x USB-serial chips may need their driver.
- Only one program can hold the serial port at a time. Close Thonny, other terminals, or an editor plugin before using `mpremote`, and vice versa.
- Use a data-capable USB cable. Charge-only cables are a common cause of "no port shows up".

## mpremote in practice

```bash
mpremote devs                          # list serial devices
mpremote connect /dev/ttyACM0 ...      # pick a device (or a0/u0 shortcuts; COM3 on Windows)
mpremote                               # connect + open REPL (Ctrl-] exits, Ctrl-D soft reset)

# files
mpremote fs ls                         # list device files
mpremote fs tree                       # recursive listing
mpremote fs cp main.py :               # host -> device (colon marks the device side)
mpremote fs cp :main.py .              # device -> host
mpremote fs cp -r lib :                # copy directory 'lib' into device root (as :lib)
mpremote fs rm :old.py
mpremote fs mkdir :data
mpremote df                            # filesystem usage

# running code
mpremote run test.py                   # execute a host file on the device, stream output
mpremote exec "import os; print(os.uname())"
mpremote eval "1+2"
mpremote mount .                       # mount current host dir on device; `import` reads host files

# lifecycle
mpremote soft-reset
mpremote reset                         # hard reset
mpremote bootloader                    # enter bootloader (RP2 UF2 mode, etc.)

# chaining commands with '+'
mpremote fs cp main.py : + reset + repl
```

Notes:
- `fs cp` skips files that are unchanged (compares hashes). Use `-f` to force.
- Copying a directory with `cp -r dir :` puts it *inside* the destination when that exists. To deploy the contents of `src/`, copy each top-level entry (`scripts/deploy.sh` does this).
- `mpremote run script.py` does not copy the script, and it does not auto-reset afterwards. State from earlier runs can persist on the board until a soft reset.
- Use `mpremote mount .` plus `mpremote run` for a fast edit-test loop without copying files each time.
- Running `mpremote` while `main.py` is looping works by interrupting it (Ctrl-C equivalent). If it cannot connect, see "Recovering" below.

## Installing libraries with mip

```bash
mpremote mip install aioble                       # from micropython-lib, installed to /lib
mpremote mip install umqtt.simple
mpremote mip install github:owner/repo            # third-party (repo with a package.json)
mpremote mip install --target /lib github:owner/repo/path/to/file.py
```

On the board (needs network):

```python
import mip
mip.install("ssd1306")
```

`upip` is obsolete. If a library is not available through `mip`, copy its `.py` file (or `.mpy`) into `/lib` on the device.

## Precompiling with mpy-cross

```bash
mpy-cross -o build/lib/driver.mpy src/lib/driver.py        # bytecode for the matching release
mpy-cross -march=xtensawin -o out.mpy in.py                # only needed if the module uses native/viper
```

- Use the same MicroPython release for `mpy-cross` and the firmware; mpy bytecode versions change. Symptom of a mismatch: `ValueError: incompatible .mpy file`.
- Check the firmware's version with `mpremote exec "import sys; print(sys.implementation)"`.
- Do not compile `boot.py` and `main.py`; the interpreter runs them as `.py`.
- If a `.py` and a `.mpy` with the same module name are both on the board, the `.py` is found first. After switching a library to `.mpy`, remove the old source (`mpremote fs rm :lib/driver.py`).
- Keep the `.py` sources in version control; `.mpy` is a build artifact (`build/` in `.gitignore`).

## Recovering a stuck or corrupted board

Symptoms: `mpremote` cannot connect ("could not enter raw REPL"), REPL never appears, boot loops.

1. **Interrupt the program**: open a terminal (`mpremote repl` or Thonny) and press Ctrl-C repeatedly; press Ctrl-D for a soft reset while spamming Ctrl-C to catch the moment before a loop starts. Unplug/replug to catch it at boot if needed.
2. **Delete the culprit file**: once at the `>>>` prompt: `import os; os.remove('main.py')`. Or `mpremote fs rm :main.py` right after a reset.
3. **RP2 with a stuck filesystem**: hold BOOTSEL and re-flash the MicroPython `.uf2`. To wipe the whole flash, copy Raspberry Pi's `flash_nuke.uf2` (from the Raspberry Pi Pico documentation) to the drive first, then re-flash MicroPython.
4. **ESP32**: `esptool erase-flash`, then re-flash the firmware.
5. **Prevention**: keep the escape window at the top of `main.py` (see the template) so a faulty `main.py` can always be interrupted before its loop starts.
6. If the REPL works but the filesystem raises `OSError: [Errno 5]` or looks corrupt, first back up what you can (`mpremote fs cp -r :lib backup/`), then reflash (erase first on ESP32, `flash_nuke.uf2` on RP2). Reformatting from the REPL is port-specific, so reflashing is the reliable route.

## Editors and IDEs

- **Thonny**: easiest for beginners (interpreter set to MicroPython on the right port). It holds the serial port while open.
- **VS Code**: "MicroPico" (Raspberry Pi Pico focus) or "Pymakr" extensions; or plain VS Code with `mpremote` in the terminal, which works for every board.
- **PyCharm**: MicroPython plugin.
- Any editor works with `mpremote` plus `scripts/deploy.sh`. This is the most portable workflow and the one to recommend for a serious project.
- WebREPL (ESP) and Bluetooth/WiFi-based REPLs exist for wireless workflows; they need explicit setup (`import webrepl_setup`) and a password. Do not leave them open on an untrusted network.

## Type stubs and linting

```bash
pip install micropython-rp2-stubs        # or micropython-esp32-stubs, micropython-stm32-stubs...
pip install micropython-stdlib-stubs
```

Add the stubs to the editor's Python environment for autocompletion of `machine`, `network`, and so on, and to catch typos with Pylance/mypy/pyright. Configure the linter to accept MicroPython-only names (`time.sleep_ms`, `micropython`, `const`). Stubs do not replace testing on hardware.

## Custom firmware and frozen modules

Build your own firmware when: RAM is too tight even with `.mpy`, you need a C module, or you need a board definition for custom hardware. Overview:

1. Clone `micropython/micropython`, build `mpy-cross` (`make -C mpy-cross`), and set up the port's toolchain (see `ports/<port>/README` for ESP-IDF, Pico SDK, arm-none-eabi-gcc).
2. Put your Python modules in a `manifest.py` (`module("driver.py", base_path="modules")`, or `require("aioble")` for micropython-lib packages).
3. `make -C ports/rp2 BOARD=RPI_PICO_W FROZEN_MANIFEST=/path/to/manifest.py` (ESP32 uses `idf.py` via `make BOARD=...`).
4. Flash the resulting `.uf2`/`.bin` as usual. Frozen modules import from flash with almost no RAM cost.

Explain the toolchain requirement upfront; do not suggest this as a first step.

## Project hygiene

`.gitignore`:

```
.venv/
build/
__pycache__/
secrets.py
*.mpy
```

- Commit `secrets.example.py` with placeholder values.
- Keep a `README` with: board and firmware version, wiring table, deploy command, how to enter the REPL.
- Version the firmware release in the README, so a `.mpy` mismatch is easy to diagnose later.
- Add a `VERSION` constant to `config.py` and print it at boot; it removes doubt about what is running on a board.
