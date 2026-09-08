# Syntaxe Jinja2 avancée

Référence à consulter quand le besoin dépasse le simple `{% extends %}` / `{% block %}` déjà
couvert dans SKILL.md.

## Boucles et conditions

```jinja
<ul>
{% for item in items %}
  <li class="{{ 'is-active' if loop.first else '' }}">{{ item.name }}</li>
{% else %}
  <li>Aucun élément.</li>
{% endfor %}
</ul>
```

`loop.first`, `loop.last`, `loop.index` (1-indexé), `loop.index0` (0-indexé) sont disponibles
dans toute boucle. Le bloc `{% else %}` d'un `{% for %}` s'exécute uniquement si l'itérable
est vide — pratique pour éviter un `{% if items %}` englobant.

## Filtres utiles

```jinja
{{ price | round(2) }} €
{{ description | truncate(120) }}
{{ user.bio | default("Pas de bio.", true) }}
{{ items | length }} résultat(s)
{{ raw_html | safe }}          {# uniquement si le contenu est déjà de confiance #}
{{ tags | join(", ") }}
{{ date | strftime("%d/%m/%Y") }}   {# filtre custom, voir plus bas #}
```

`default(valeur, true)` avec le deuxième argument à `true` traite aussi les chaînes vides
comme "absentes" (pas seulement `undefined`).

### Filtres custom

Pour un filtre non standard (formatage de date, devise…), l'enregistrer sur l'instance
`Jinja2Templates` :

```python
def format_date(value, fmt="%d/%m/%Y"):
    return value.strftime(fmt)

templates.env.filters["strftime"] = format_date
```

## Macros (fonctions réutilisables qui produisent du HTML)

Les macros remplacent avantageusement `{% include %}` dès qu'un fragment prend des
paramètres. Les définir dans un fichier dédié, par exemple `templates/partials/_macros.html` :

```jinja
{% macro input(name, label, type="text", value="", error=None) %}
<div class="field {{ 'field--error' if error else '' }}">
  <label for="{{ name }}">{{ label }}</label>
  <input type="{{ type }}" id="{{ name }}" name="{{ name }}" value="{{ value }}">
  {% if error %}<p class="field__error">{{ error }}</p>{% endif %}
</div>
{% endmacro %}
```

Utilisation depuis une autre page :

```jinja
{% from "partials/_macros.html" import input %}

<form method="post">
  {{ input("email", "Email", type="email", value=values.email, error=errors.email) }}
</form>
```

Règle simple pour choisir entre les deux :
- **`{% include %}`** : fragment sans paramètres, ou qui lit directement des variables déjà
  dans le contexte (ex: une navbar qui utilise `request.url.path` pour l'état actif).
- **macro** : fragment réutilisé avec des valeurs différentes à chaque appel (un champ de
  formulaire, une carte produit, un badge de statut).

## Contrôle du whitespace

Par défaut, les balises Jinja laissent des lignes vides dans le HTML généré. Pour du HTML lisible
en sortie (utile en debug ou si le HTML brut est inspecté), utiliser `-` pour trimmer :

```jinja
{% for item in items -%}
  <li>{{ item }}</li>
{%- endfor %}
```

Ce n'est pas nécessaire pour un rendu correct (le navigateur ignore les espaces superflus en
HTML), donc à réserver aux cas où la lisibilité du HTML source compte réellement.

## Contexte global (variables disponibles partout sans les repasser à chaque route)

Pour éviter de repasser des variables comme `current_user` ou `settings` dans chaque
`TemplateResponse`, les ajouter aux globals de l'environnement Jinja :

```python
templates.env.globals["app_name"] = "Mon App"
```

Pour des valeurs qui dépendent de la requête (utilisateur connecté, etc.), un context
processor manuel reste nécessaire — Jinja2Templates de FastAPI n'a pas de mécanisme de
"context processor" automatique comme Flask ; fusionner ces valeurs dans le `context=` de
chaque route, ou écrire un petit helper `def render(request, name, **extra)` qui les injecte
systématiquement.
