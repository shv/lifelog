# Life Journal with Plan and Notes

## Description

This service is designed for keeping a life journal.

## Installation

You need to install poetry:

`pip install --upgrade poetry`

Then the project itself:

`poetry install`

It's better to do this in a virtual environment.

## Running the application locally

`poetry run python manage.py runserver`

## Ruff

Check code and formatting:

```bash
poetry run ruff check .
poetry run ruff format --check .
```

Format code:

```bash
poetry run ruff check . --fix
poetry run ruff format .
```

Django entry points (`manage.py`, `asgi.py`, `wsgi.py`),
app configurations (`apps.py`), and migrations are excluded from both linting and
formatting, including when passed explicitly. Other files, including
`project/settings.py` and `project/urls.py`, remain eligible.

## Docker compose

### Building

```bash
docker compose build prod
```

### Running

```bash
docker compose up -d prod
```
