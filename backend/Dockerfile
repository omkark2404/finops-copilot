FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=10001:10001 . .
RUN mkdir -p /app/data && chown -R 10001:10001 /app/data
USER 10001:10001
EXPOSE 8000
CMD ["python","-m","app.serve"]
