# HTMX avec FastAPI

HTMX permet à des éléments HTML de déclencher des requêtes HTTP et de remplacer un morceau de
la page avec le HTML renvoyé — sans écrire de JS ni monter une API JSON séparée. Bien adapté à
une app Jinja2/FastAPI existante.

## Installation

Un seul script, pas de build :

```html
<script src="https://unpkg.com/htmx.org@2.0.0"></script>
```

(Préférer héberger le fichier en local dans `static/js/` pour la prod plutôt que de dépendre
d'un CDN externe, sauf si l'utilisateur est explicitement en développement/prototypage rapide.)

## Principe : la route renvoie un fragment, pas une page complète

```jinja
{# templates/partials/_todo_item.html — PAS de {% extends %}, c'est un fragment autonome #}
<li id="todo-{{ todo.id }}">
  {{ todo.title }}
  <button hx-delete="{{ url_for('delete_todo', todo_id=todo.id) }}"
          hx-target="closest li"
          hx-swap="outerHTML">
    Supprimer
  </button>
</li>
```

```python
@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int, request: Request):
    # ... suppression en base ...
    return HTMLResponse("")  # réponse vide : hx-swap="outerHTML" retire l'élément du DOM
```

```python
@app.post("/todos")
def create_todo(request: Request, title: str = Form(...)):
    todo = save_todo(title)
    return templates.TemplateResponse(
        request=request,
        name="partials/_todo_item.html",
        context={"todo": todo},
    )
```

Le formulaire d'ajout poste avec HTMX et insère la réponse dans la liste :

```jinja
<form hx-post="{{ url_for('create_todo') }}" hx-target="#todo-list" hx-swap="beforeend">
  <input type="text" name="title" required>
  <button type="submit">Ajouter</button>
</form>
<ul id="todo-list">
  {% for todo in todos %}{% include "partials/_todo_item.html" %}{% endfor %}
</ul>
```

## Distinguer requête HTMX et navigation classique

Utile quand la même route doit répondre soit par une page complète (navigation directe), soit
par un fragment (appel HTMX) :

```python
@app.get("/todos")
def list_todos(request: Request):
    todos = get_all_todos()
    template = "partials/_todo_list.html" if request.headers.get("HX-Request") else "pages/todos.html"
    return templates.TemplateResponse(request=request, name=template, context={"todos": todos})
```

## Gestion des erreurs et redirections côté HTMX

- Pour une redirection après une action HTMX (ex: après suppression du dernier élément), utiliser
  le header `HX-Redirect` plutôt qu'un `RedirectResponse` classique (HTMX intercepte les requêtes
  et un 3xx standard ne déclenche pas de navigation) :

  ```python
  from fastapi import Response

  @app.post("/logout")
  def logout(response: Response):
      response.headers["HX-Redirect"] = "/login"
      return Response(status_code=200)
  ```

- Pour afficher une erreur de validation dans le fragment retourné, renvoyer le même fragment
  avec un statut d'erreur et un bloc d'erreur dans le HTML — HTMX affiche par défaut la réponse
  même sur un code 4xx si `hx-swap` n'est pas configuré pour l'ignorer :

  ```python
  return templates.TemplateResponse(
      request=request, name="partials/_todo_form.html",
      context={"error": "Le titre est requis"}, status_code=422,
  )
  ```

## Attributs HTMX les plus utiles à connaître

- `hx-get` / `hx-post` / `hx-put` / `hx-delete` : la requête à déclencher.
- `hx-target` : où insérer la réponse (par défaut, l'élément lui-même). `closest li`, `#id`,
  `next .selector` sont tous valides.
- `hx-swap` : comment insérer (`innerHTML` par défaut, `outerHTML`, `beforeend`, `afterbegin`…).
- `hx-trigger` : quel événement déclenche la requête (`click` par défaut sur un bouton,
  `keyup changed delay:300ms` pour une recherche en live, `load` pour charger au montage).
- `hx-indicator` : élément à afficher pendant la requête (spinner de chargement).
- `hx-confirm` : boîte de confirmation native avant d'envoyer la requête (suppression, etc.).

## Quand HTMX n'est pas la bonne réponse

Si l'utilisateur a besoin d'état client complexe partagé entre plusieurs composants
(ex: un panier qui doit se mettre à jour dans le header ET dans le contenu sans refaire une
requête serveur), ou d'animations/transitions élaborées, ou de fonctionnement hors-ligne, HTMX
seul devient vite limitant — le signaler et évoquer Alpine.js en complément (état local réactif)
avant de recommander une vraie SPA.
