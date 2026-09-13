FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Train the classifier at build time so the image is ready to route
# requests immediately (re-run manually after adding real labeled data).
RUN python data/generate_seed_dataset.py && PYTHONPATH=. python -m app.classifier.train

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
