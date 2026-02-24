FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        wkhtmltopdf \
        fonts-dejavu-core \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY docker/pdf/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY docker/pdf/app.py ./app.py

EXPOSE 8092
CMD ["python", "app.py"]
