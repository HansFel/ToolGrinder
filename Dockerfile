FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRINDER_DATA_DIR=/app/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Grinder.py webapp.py ./
COPY ToolLib ./ToolLib
COPY templates ./templates
COPY static ./static

RUN mkdir -p /app/data/generated

EXPOSE 8080

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "webapp:app"]
