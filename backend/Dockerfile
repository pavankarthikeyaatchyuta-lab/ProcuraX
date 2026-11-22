FROM python:3.13-slim
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && useradd -m procure && mkdir -p /app/data/documents && chown -R procure:procure /app
COPY --chown=procure:procure . .
USER procure
EXPOSE 8000
CMD ["sh","-c","python -m app.cli init && python -m app.cli seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
