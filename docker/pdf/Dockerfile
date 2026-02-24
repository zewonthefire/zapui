FROM python:3.12-alpine

RUN apk add --no-cache wkhtmltopdf ttf-dejavu fontconfig

WORKDIR /app
COPY docker/pdf/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY docker/pdf/app.py ./app.py

EXPOSE 8092
CMD ["python", "app.py"]
