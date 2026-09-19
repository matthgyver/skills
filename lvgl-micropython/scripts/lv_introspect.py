"""LVGL API introspection for MicroPython (board or Unix simulator).

The LVGL binding is generated from the C headers: the names that exist depend
on the LVGL version and on lv_conf.h. This module lets you check a name
instead of guessing it.

Install and use:
    mpremote cp lv_introspect.py :
    mpremote exec "import lv_introspect as i; i.info()"
    mpremote exec "import lv_introspect as i; i.find('long_mode')"
    mpremote exec "import lv_introspect as i; i.members('label')"

On the Unix simulator, put the file next to your script and import it.
MicroPython-compatible: no f-strings, no external dependency.
"""

import sys

import lvgl as lv


def _names(obj):
    try:
        return sorted(dir(obj))
    except Exception:
        return []


def _is_widget(obj):
    return isinstance(obj, type) and hasattr(obj, "set_size") and hasattr(obj, "align")


def version():
    """LVGL version string if the binding exposes it, otherwise None."""
    fn = getattr(lv, "version_info", None)
    if fn is not None:
        try:
            return fn()
        except Exception:
            pass
    return None


def widgets():
    """List of widget classes compiled into this firmware."""
    out = []
    for name in _names(lv):
        if name.startswith("_"):
            continue
        try:
            obj = getattr(lv, name)
        except Exception:
            continue
        if _is_widget(obj):
            out.append(name)
    return out


def info():
    """Summary: versions, API generation (v8 or v9), available widgets."""
    print("LVGL        :", version() or "unknown (see the REPL boot banner)")
    print("MicroPython :", sys.version)
    if hasattr(lv, "screen_active"):
        gen = "LVGL 9 (screen_active present)"
    elif hasattr(lv, "scr_act"):
        gen = "LVGL 8 (scr_act present)"
    else:
        gen = "undetermined"
    print("API         :", gen)
    ws = widgets()
    print("Widgets (%d):" % len(ws))
    line = "  "
    for name in ws:
        if len(line) + len(name) > 70:
            print(line)
            line = "  "
        line += name + " "
    print(line)


def find(term, limit=60):
    """Search `term` (case-insensitive) in lv.* and in the members of every class."""
    t = term.lower()
    hits = 0
    for name in _names(lv):
        if name.startswith("_"):
            continue
        if t in name.lower():
            print("lv.%s" % name)
            hits += 1
            if hits >= limit:
                print("... (limit reached, narrow the term)")
                return
        try:
            obj = getattr(lv, name)
        except Exception:
            continue
        if isinstance(obj, type):
            for member in _names(obj):
                if member.startswith("_"):
                    continue
                if t in member.lower():
                    print("lv.%s.%s" % (name, member))
                    hits += 1
                    if hits >= limit:
                        print("... (limit reached, narrow the term)")
                        return
    print("%d result(s) for %r" % (hits, term))


def members(name):
    """Print the public members of lv.<name> (methods, enumerations)."""
    obj = getattr(lv, name, None)
    if obj is None:
        print("lv.%s does not exist in this firmware (widget disabled in lv_conf.h?)" % name)
        return
    names = [m for m in _names(obj) if not m.startswith("_")]
    print("lv.%s: %d members" % (name, len(names)))
    line = "  "
    for m in names:
        if len(line) + len(m) > 70:
            print(line)
            line = "  "
        line += m + " "
    print(line)
