FROM python:3.13-slim-bookworm

EXPOSE 8000

WORKDIR /code

ENV PYTHONDONTWRITEBYTECODE 1 PYTHONUNBUFFERED 1

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential gcc libc-dev libffi-dev libssl-dev && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip && \
    pip install --upgrade setuptools && \
    pip install --upgrade poetry

COPY poetry.lock pyproject.toml /code/

ARG POETRY_DEV_INSTALL=false

RUN poetry config virtualenvs.create false && \
    if [ "$POETRY_DEV_INSTALL" = "true" ]; then \
      poetry install --no-interaction --no-ansi --with dev; \
    else \
      poetry install --no-interaction --no-ansi --without dev; \
    fi

COPY . /code

RUN poetry run python manage.py collectstatic --no-input

CMD ["poetry", "run", "python", "manage.py", "runserver", "0.0.0.0:8000"]
