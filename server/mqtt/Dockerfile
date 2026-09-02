FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir paho-mqtt==2.1.0 psycopg2-binary==2.9.9 python-dotenv==1.0.1
COPY subscriber.py .
CMD ["python", "subscriber.py"]
