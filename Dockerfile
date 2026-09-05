FROM python:3.13-slim
WORKDIR /app
COPY tools/sandbox/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY tools/sandbox/app ./app
COPY tools/sandbox/static ./static
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
