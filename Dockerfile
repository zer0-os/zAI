FROM python:3.12 AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Install poetry
RUN pip install poetry
RUN poetry config virtualenvs.in-project true

# Copy dependency files
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

# Copy the rest of the application
COPY . .

FROM python:3.12-slim
WORKDIR /app

# Install poetry in the final image
RUN pip install poetry

# Copy from builder
COPY --from=builder /app /app

CMD ["/app/.venv/bin/python", "./src/main.py", "--web", "--debug", "--port", "8000"]
