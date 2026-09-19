# LVGL 9 cookbook for MicroPython

All snippets assume the hardware is initialized and `import lvgl as lv` is done. They target LVGL 9; points that vary between versions are marked **verify** (see `scripts/lv_introspect.py`).

## Table of contents

1. Button, label, event
2. Shared styles and states
3. Flex layout
4. Grid layout
5. Slider, switch, dropdown
6. Text area and keyboard
7. Chart fed by a timer
8. LVGL timers
9. Animations
10. Multiple screens
11. asyncio and interrupts
12. Images and symbols
13. Structuring an application

## 1. Button, label, event

```python
scr = lv.screen_active()

btn = lv.button(scr)
btn.set_size(140, 50)
btn.align(lv.ALIGN.CENTER, 0, 0)
lbl = lv.label(btn)
lbl.set_text("OK")
lbl.center()

def on_click(e):
    lbl.set_text("Clicked")

btn.add_event_cb(on_click, lv.EVENT.CLICKED, None)
```

## 2. Shared styles and states

A style is defined once and applied to several objects. **It must stay referenced** (module variable or object attribute), otherwise the garbage collector frees it while LVGL is still using it.

```python
style_btn = lv.style_t()
style_btn.init()
style_btn.set_radius(12)
style_btn.set_bg_color(lv.palette_main(lv.PALETTE.BLUE))
style_btn.set_border_width(0)
style_btn.set_text_color(lv.color_white())

style_pressed = lv.style_t()
style_pressed.init()
style_pressed.set_bg_color(lv.palette_darken(lv.PALETTE.BLUE, 2))

btn.add_style(style_btn, 0)                     # 0 = main part, default state
btn.add_style(style_pressed, lv.STATE.PRESSED)  # only while pressed
```

Local style (specific to one object, no `lv.style_t`):

```python
obj.set_style_bg_color(lv.color_hex(0x202020), 0)
obj.set_style_radius(8, 0)
obj.set_style_text_font(lv.font_montserrat_20, 0)   # font must be enabled in lv_conf.h
```

Selector: combine part and state with `|`, for example `lv.PART.INDICATOR | lv.STATE.CHECKED`.

## 3. Flex layout

```python
cont = lv.obj(scr)
cont.set_size(lv.pct(100), lv.pct(100))
cont.set_flex_flow(lv.FLEX_FLOW.COLUMN)
cont.set_flex_align(lv.FLEX_ALIGN.START, lv.FLEX_ALIGN.CENTER, lv.FLEX_ALIGN.CENTER)

for i in range(3):
    b = lv.button(cont)
    b.set_width(lv.pct(80))
    l = lv.label(b)
    l.set_text("Item %d" % i)
```

Variants: `FLEX_FLOW.ROW`, `ROW_WRAP`, `COLUMN_WRAP`. To distribute space: `SPACE_EVENLY`, `SPACE_BETWEEN`. A child can take the remaining space with `child.set_flex_grow(1)`.

## 4. Grid layout

Descriptor arrays must stay referenced (module variables).

```python
col_dsc = [lv.grid_fr(1), lv.grid_fr(1), lv.GRID_TEMPLATE_LAST]  # v8: lv.GRID.TEMPLATE_LAST (verify)
row_dsc = [lv.grid_fr(1), lv.grid_fr(1), lv.GRID_TEMPLATE_LAST]

grid = lv.obj(scr)
grid.set_size(lv.pct(100), lv.pct(100))
grid.set_grid_dsc_array(col_dsc, row_dsc)

for row in range(2):
    for col in range(2):
        cell = lv.button(grid)
        cell.set_grid_cell(lv.GRID_ALIGN.STRETCH, col, 1,
                           lv.GRID_ALIGN.STRETCH, row, 1)
```

## 5. Slider, switch, dropdown

```python
slider = lv.slider(scr)
slider.set_width(200)
slider.set_range(0, 100)
slider.center()

value_lbl = lv.label(scr)
value_lbl.set_text("0")
value_lbl.align_to(slider, lv.ALIGN.OUT_BOTTOM_MID, 0, 15)

def on_slide(e):
    value_lbl.set_text(str(slider.get_value()))   # closure: no cast needed

slider.add_event_cb(on_slide, lv.EVENT.VALUE_CHANGED, None)

sw = lv.switch(scr)
sw.add_event_cb(lambda e: print("ON" if sw.has_state(lv.STATE.CHECKED) else "OFF"),
                lv.EVENT.VALUE_CHANGED, None)

dd = lv.dropdown(scr)
dd.set_options("Red\nGreen\nBlue")               # options separated by \n
dd.add_event_cb(lambda e: print(dd.get_selected()), lv.EVENT.VALUE_CHANGED, None)
```

## 6. Text area and keyboard

```python
ta = lv.textarea(scr)
ta.set_one_line(True)
ta.set_width(lv.pct(80))
ta.align(lv.ALIGN.TOP_MID, 0, 10)

kb = lv.keyboard(scr)
kb.set_textarea(ta)
```

To show the keyboard only on focus: hide it by default (`kb.add_flag(lv.obj.FLAG.HIDDEN)`), and handle `lv.EVENT.FOCUSED` / `lv.EVENT.DEFOCUSED` on the text area to remove/add the flag (`remove_flag` in v9).

## 7. Chart fed by a timer

```python
chart = lv.chart(scr)
chart.set_size(280, 150)
chart.set_type(lv.chart.TYPE.LINE)
chart.set_point_count(30)
chart.set_range(lv.chart.AXIS.PRIMARY_Y, 0, 100)
series = chart.add_series(lv.palette_main(lv.PALETTE.RED), lv.chart.AXIS.PRIMARY_Y)

import random
def feed(t):
    chart.set_next_value(series, random.randint(0, 100))

chart_timer = lv.timer_create(feed, 500, None)    # keep the reference
```

On small boards, reduce `set_point_count` and the update rate: every new point invalidates and redraws the chart area.

## 8. LVGL timers

```python
def tick(t):
    clock_lbl.set_text("%d s" % (time.ticks_ms() // 1000))

t = lv.timer_create(tick, 1000, None)
t.pause();  t.resume()
t.set_repeat_count(1)      # fire only once
t.delete()                 # when no longer needed
```

The callback receives the timer object. It runs in the LVGL loop context: a long callback freezes the interface.

## 9. Animations

```python
a = lv.anim_t()
a.init()
a.set_var(obj)
a.set_values(0, 200)
a.set_duration(600)
a.set_playback_duration(600)
a.set_repeat_count(lv.ANIM_REPEAT_INFINITE)         # verify for your version
a.set_path_cb(lv.anim_t.path_ease_in_out)
a.set_custom_exec_cb(lambda anim, v: obj.set_x(v))  # "Python" version of the exec callback
a.start()
```

Keep `a` referenced while the animation runs. `set_exec_cb` expects a C function pointer; use `set_custom_exec_cb` for a Python function.

## 10. Multiple screens

A screen is an object without a parent. Build each screen once and keep it.

```python
scr_home = lv.screen_active()
scr_settings = lv.obj(None)

# ... build widgets on scr_settings ...

def go_settings(e):
    lv.screen_load_anim(scr_settings, lv.SCREEN_LOAD_ANIM.MOVE_LEFT, 250, 0, False)

def go_home(e):
    lv.screen_load_anim(scr_home, lv.SCREEN_LOAD_ANIM.MOVE_RIGHT, 250, 0, False)
```

The last argument (`auto_del`) must stay `False` if you plan to come back to the screen. With little RAM, deleting a heavy screen (`scr.delete()`) once left and rebuilding it on demand can be preferable.

## 11. asyncio and interrupts

```python
import asyncio

async def sensor_loop():
    while True:
        lbl.set_text("%.1f C" % read_temperature())
        await asyncio.sleep_ms(1000)

async def main():
    asyncio.create_task(sensor_loop())
    while True:
        await asyncio.sleep_ms(100)

asyncio.run(main())
```

Check that the LVGL loop (`TaskHandler`) stays active alongside it: it is driven by a hardware timer, so it is compatible with asyncio, but a blocking call without `await` blocks everything.

From a hardware interrupt, **call nothing from LVGL**:

```python
import micropython

def _apply(_):
    lbl.set_text("Button pressed")         # normal context: allowed

def _irq(pin):
    micropython.schedule(_apply, 0)        # inside the ISR: only schedule

button_pin.irq(trigger=machine.Pin.IRQ_FALLING, handler=_irq)
```

## 12. Images and symbols

Built-in symbols (the Font Awesome subset shipped with LVGL) cost almost nothing:

```python
lbl.set_text(lv.SYMBOL.WIFI + " Connected")
```

Binary image loaded in memory (**verify**: header fields depend on the version; produce the `.bin` with the LVGL image converter in the desired color format):

```python
with open("/logo.bin", "rb") as f:
    logo_data = f.read()                   # keep the reference!

logo_dsc = lv.image_dsc_t({
    "header": {"w": 64, "h": 64, "cf": lv.COLOR_FORMAT.RGB565},
    "data_size": len(logo_data),
    "data": logo_data,
})
img = lv.image(scr)
img.set_src(logo_dsc)
```

A full-screen RGB565 image in RAM costs width x height x 2 bytes: load it from flash on demand, or shrink it, rather than keeping several.

Additional fonts: the available `lv.font_montserrat_XX` sizes are fixed by `lv_conf.h` (hence at build time). Custom fonts go through a build or a font file if the firmware enables it (**verify** for your firmware).

## 13. Structuring an application

Separate three layers so the UI can be tested on the simulator:

- `board.py`: buses, display, touch, `TaskHandler` (board-specific).
- `ui.py`: functions/classes that build widgets on a given screen, unaware of the hardware.
- `main.py`: calls `board.init()`, then `ui.build()`, then the logic (sensors, network).

One class per screen that keeps its widgets, styles and timers as attributes solves almost every object-lifetime problem. See `assets/template_app_skeleton.py`.
