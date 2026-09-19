# LVGL 8 versus LVGL 9 on MicroPython

Tutorials, forums and online examples mix three generations of the API. Identify the generation of any snippet before using it, and generate code for **the version of the user's firmware**.

## Identifying the generation of a snippet

| Hint in the code | Generation |
|---|---|
| `lv.btn`, `lv.scr_act()`, `lv.img`, `lv.disp_drv_t()`, `lv.indev_drv_t()` | LVGL 8 |
| `lv.button`, `lv.screen_active()`, `lv.image`, `lv.display_t`, `lv.indev_create()` | LVGL 9 |
| `set_style_local_*`, `lv.style_plain`, `lv.btn.STATE`, `set_action(...)` | LVGL 7 (obsolete: do not produce code in this format) |

## Migration table (most frequent cases)

Indicative table: the firmware is the source of truth (see `scripts/lv_introspect.py`).

| LVGL 8 | LVGL 9 |
|---|---|
| `lv.scr_act()` | `lv.screen_active()` |
| `lv.scr_load(s)` / `lv.scr_load_anim(...)` | `lv.screen_load(s)` / `lv.screen_load_anim(...)` |
| `lv.btn(parent)` | `lv.button(parent)` |
| `lv.img(parent)` | `lv.image(parent)` |
| `lv.btnmatrix` | `lv.buttonmatrix` |
| `lv.imgbtn` | `lv.imagebutton` |
| `lv.img_dsc_t` | `lv.image_dsc_t` |
| `obj.clear_flag(...)` | `obj.remove_flag(...)` |
| `obj.clear_state(...)` | `obj.remove_state(...)` |
| `e.get_target()` (then `__cast__`) | `e.get_target_obj()` |
| `lv.disp_t`, `lv.disp_drv_t`, `lv.disp_draw_buf_t` | `lv.display_t`, `lv.display_create(w, h)` (drivers do it for you) |
| `lv.indev_drv_t` + `register()` | `lv.indev_create()` (done by the touch drivers) |
| `lv.meter` | removed: use `lv.scale` (plus arcs/lines) |
| `lv.spinner(parent, time, angle)` | `lv.spinner(parent)` then `set_anim_params(time, angle)` |
| `lv.msgbox(parent, title, text, buttons, close)` | Builder-style API: `lv.msgbox()` then `add_title`, `add_text`, `add_footer_button`, `add_close_button` |
| `lv.label.LONG.WRAP` | `lv.label.LONG.WRAP` (9.0-9.2) or `lv.label.LONG_MODE.WRAP` (9.3+): **verify** |
| `lv.tick_inc(ms)`, `lv.task_handler()` | unchanged; normally called by `TaskHandler` (lvgl_micropython) or `lv_utils.event_loop` (official) |

What does not change and can be written without hesitation: `lv.obj`, `lv.label`, `lv.slider`, `lv.switch`, `lv.arc`, `lv.bar`, `lv.checkbox`, `lv.dropdown`, `lv.roller`, `lv.textarea`, `lv.keyboard`, `lv.chart`, `lv.tabview`, `lv.list`, `lv.led`, `lv.line`, `lv.canvas`, `lv.style_t()` + `style.init()`, `obj.add_style(style, selector)`, `obj.set_style_xxx(value, selector)`, `lv.color_hex(0xRRGGBB)`, `lv.palette_main(lv.PALETTE.X)`, `lv.pct(n)`, `lv.ALIGN.*`, `lv.EVENT.*`, `lv.STATE.*`, `lv.PART.*`, `lv.FLEX_FLOW.*`, `lv.SYMBOL.*`, `lv.timer_create(cb, ms, None)`.

## Events: binding specifics

- Signature of an event callback: `def cb(e): ...`. Reading data: `e.get_code()`, `e.get_target_obj()`, `e.get_user_data()`.
- `add_event_cb(cb, lv.EVENT.CLICKED, None)`: the third argument is `user_data`. Pass `None` or a dictionary (the binding's convention also stores the callable object there, so do not put anything else in it without need).
- If `e.get_target_obj()` returns a generic object lacking the widget's methods (for example `get_value` on a slider), there are two solutions: capture the widget in a closure (the simplest, no cast), or cast: `lv.slider.__cast__(e.get_target())`.
- To react to several events with a single function: `add_event_cb(cb, lv.EVENT.ALL, None)` then test `e.get_code()`.

## Touch and display on LVGL 9 with lvgl_micropython

The community binding registers the display (`lv.display_create`) and the input device (`lv.indev_create`) inside the driver classes. Do not copy v8 code like `lv.disp_drv_t()` / `disp_drv.register()` with this binding: it does not apply.

## When the version is unknown

1. Ask for the REPL boot banner, or run `import lvgl as lv; print(lv.version_info())` (it may be missing: in that case rely on the banner).
2. Test for a discriminating name: `hasattr(lv, 'screen_active')` is `True` on v9 and `False` on v8.
3. If the user pastes a snippet from a tutorial, translate it to their version instead of asking them to change firmware.
