---
name: fastapi-frontend-jinja
description: Front‑end development (HTML, CSS, JavaScript) for an application whose back‑end is FastAPI, especially using the Jinja2 template engine. Use this whenever the user works on HTML pages served by FastAPI, Jinja2 templates (inheritance, blocks, includes, macros, filters), static file organization (CSS/JS) via StaticFiles, HTML forms submitted to FastAPI routes, or light dynamic interactions (HTMX, Alpine.js, fetch/vanilla JS) with a FastAPI back‑end. It also triggers for more general requests such as “create a web page with FastAPI”, “add a contact form to my FastAPI app”, “how to structure my Jinja2 templates”, “make this page interactive without building a React SPA”, even if the user does not explicitly mention “Jinja” or “template”. Do not use for completely decoupled front‑ends (React/Vue SPA consuming a pure FastAPI JSON API) unless the user also mixes server‑side rendering.
---

# Front‑end HTML/CSS/JS for FastAPI back‑end (Jinja2)

## When this skill applies

FastAPI does more than JSON: when served with Jinja2Templates + StaticFiles, it becomes a classic “full‑stack” server‑side rendering (SSR) framework, similar in spirit to Flask/Django. This skill covers that specific case: generating server‑side HTML with Jinja2, styling it with CSS, and adding interactivity with JS (vanilla, HTMX or Alpine.js) without necessarily building a separate SPA.

If the user wants a React/Vue SPA that consumes a FastAPI JSON API, Jinja2 template rendering is not relevant — treat that as a “classic” front‑end (see the `frontend‑design` skill if present) and FastAPI as a plain JSON API.

## Recommended project structure

Always start from this layout, even for a small project — it avoids the most common path errors that cause `TemplateNotFound` and 404s for static files:

```
app/
├── main.py
├── routers/                # one file per functional domain (optional for small projects)
├── templates/
│   ├── base.html            # common skeleton (head, nav, footer)
│   ├── partials/            # reusable fragments (navbar, card, table row…)
│   │   └── _card.html
│   └── pages/
│       ├── index.html
│       └── contact.html
└── static/
    ├── css/
    │   └── main.css
    ├── js/
    │   └── app.js
    └── img/
```

The `_` prefix on partials (e.g. `_card.html`) is a useful convention to spot at a glance files that are **not** meant to be rendered alone (they don’t extend `base.html`).

## Basic configuration (main.py)

```python
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

@app.get("/")
def index(request: Request):
    # “request” must ALWAYS be present in the context: Jinja2Templates
    # needs it for url_for() to work inside the template.
    return templates.TemplateResponse(
        request=request,
        name="pages/index.html",
        context={"title": "Home"},
    )
```

### Things never to forget
- `request` must be injected into every route that renders a template and passed to the context (via `request=request` in recent FastAPI versions, or `context={"request": request, …}` in older ones — check the installed version if the existing code uses the older form).
- The `name="static"` given to `app.mount` enables `{{ url_for('static', path='css/main.css') }}` inside templates — never hard‑code `/static/...` paths; always use `url_for`.
- Route URLs are also generated via `url_for`: `{{ url_for('route_function_name', **params) }}`, which prevents broken links when URLs change.

## Template inheritance (the pattern to always follow)

`templates/base.html` – the single skeleton that **all** pages inherit:

```jinja
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}My app{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', path='css/main.css') }}">
  {% block extra_head %}{% endblock %}
</head>
<body>
  {% include "partials/_navbar.html" %}
  <main>
    {% block content %}{% endblock %}
  </main>
  <script src="{{ url_for('static', path='js/app.js') }}"></script>
  {% block extra_scripts %}{% endblock %}
</body>
</html>
```

A concrete page extends `base.html` and only fills the necessary blocks:

```jinja
{% extends "base.html" %}

{% block title %}Contact{% endblock %}

{% block content %}
  <h1>Contact us</h1>
  <form method="post" action="{{ url_for('submit_contact') }}">
    ...
  </form>
{% endblock %}
```

This `base.html` + `{% extends %}` + `{% block %}` pattern should be the **first** reaction when you create more than one page — duplicating the `<head>` and navigation in every template is an error to avoid from the start, not something to fix later.

For more advanced Jinja2 syntax (macros, filters, whitespace‑controlled loops, `{% include %}` vs macros, auto‑escape), see `references/jinja2-syntax.md`.

## CSS and JS: organization and caching

- One CSS entry point (`main.css`) and one JS entry point (`app.js`) to start; split into multiple files only if the project really grows (then use a sub‑folder `css/components/`).
- Browsers aggressively cache static files. In development, add a version query string to force reload during iteration:  
  `{{ url_for('static', path='css/main.css') }}?v={{ range(1, 99999) | random }}` is **not** a production best practice — for real cache‑busting, prefer a content hash (via a build tool) or, at minimum, a manually incremented version variable in the config.
- For CSS, prefer CSS variables (`:root { --color-primary: … }`) over hard‑coded repeated values, as you would in any front‑end project — see the `frontend‑design` skill for artistic direction if visual design is a concern.

## HTML forms → FastAPI routes

Standard pattern for a classic HTML form (no JS) that posts to a FastAPI route:

```python
from fastapi import Form
from fastapi.responses import RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER

@app.post("/contact")
def submit_contact(name: str = Form(...), email: str = Form(...), message: str = Form(...)):
    # … processing, business validation, saving …
    # Always redirect after a successful POST (Post/Redirect/Get pattern) to avoid
    # form resubmission on browser refresh.
    return RedirectResponse(url="/thanks", status_code=HTTP_303_SEE_OTHER)
```

If validation fails and you want to re‑display the form with errors and previously entered values, re‑render the same template passing the values and an error dict in the context instead of relying on `request.form()` client‑side:

```python
@app.post("/contact")
def submit_contact(request: Request, name: str = Form(...), email: str = Form(...)):
    errors = {}
    if "@" not in email:
        errors["email"] = "Invalid email address"
    if errors:
        return templates.TemplateResponse(
            request=request,
            name="pages/contact.html",
            context={"errors": errors, "values": {"name": name, "email": email}},
            status_code=422,
        )
    ...
```

For more complex forms (file uploads, dynamic multiple fields), stay on `Form(...)` per field or a Pydantic model with `Form` — avoid external form libraries unless the user already has them in the project.

## Interactivity: three levels, from simplest to richest

1. **Vanilla JS** for pure local interactions (menu toggle, basic client‑side validation): no dependencies, enough for 80 % of simple cases.
2. **HTMX** when you want partial page updates without writing JS or building a separate JSON API: FastAPI returns HTML fragments. This is the default choice for “make a FastAPI page dynamic” without moving to a SPA — see `references/htmx-patterns.md`.
3. **Alpine.js** for reactive local state inside HTML (dropdowns, tabs, multi‑step forms) without a JSON back‑end or bundler — works well together with HTMX for the rest.

Offer a full SPA (React/Vue with a build step) only if the user explicitly asks for it or if the need is clearly a rich client‑side application — for the majority of Jinja2‑served sites, HTMX/Alpine are sufficient and avoid the complexity of a separate JS bundle.

## Basic security reminders (to mention spontaneously)

- Jinja2 escapes HTML by default (`autoescape=True` is automatically enabled by `Jinja2Templates` for `.html` files) — never use `| safe` on user‑provided content.
- CSRF: FastAPI has no built‑in CSRF protection. For classic HTML forms (session cookies), tell the user about adding a CSRF token (e.g., `itsdangerous` to sign a token stored in a cookie + hidden form field) as soon as there is a notion of session/authentication — don’t add it silently for a simple prototype without auth, but mention it.
- Never build a URL or SQL query by concatenating strings taken from the template or form context.

## Minimal complete example

A starter skeleton ready to copy (main.py + base.html + home page + CSS + JS) is available in `assets/`:
- `assets/base.html` — base template with navbar
- `assets/main.css` — CSS variables + minimal reset
- `assets/app.js` — JS skeleton (event delegation)

Copy these files as the starting point rather than starting from scratch for every project.

## Common troubleshooting

- **`jinja2.exceptions.TemplateNotFound`**: verify that the `directory=` argument in `Jinja2Templates(...)` points to the `templates/` folder with an absolute path (via `Path(__file__).resolve().parent`), not a relative path that depends on where `uvicorn` is launched.
- **404 on `/static/...`**: ensure `app.mount("/static", ...)` is called on the **same** `app` instance (not forgotten after refactoring into routers), and that `name="static"` matches what `url_for('static', …)` uses in templates.
- **`jinja2.exceptions.UndefinedError: 'request' is undefined`**: the route did not pass `request` into the `TemplateResponse` context — this is mandatory for `url_for` to work in the template.
- **Form submitted as JSON by mistake**: a classic HTML `<form>` sends `application/x-www-form-urlencoded`, not JSON — the route must use `Form(...)`, not a Pydantic model received via `Body`. Mixing the two is the most frequent error when someone copies a JSON‑API example for an HTML form.
