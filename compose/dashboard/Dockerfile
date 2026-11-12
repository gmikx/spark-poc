FROM python:3.12-slim
RUN pip install --no-cache-dir flask==3.* docker requests gunicorn
WORKDIR /app
COPY app.py .
COPY static static
CMD ["gunicorn", "-b", "0.0.0.0:8088", "-w", "1", "--threads", "4", "app:app"]
