FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY activities.py workflows.py main.py ./

ENV TEMPORAL_HOST=temporal:7233
ENV TASK_QUEUE=order-saga
ENV DATABASE_URL=postgresql://postgres:workshop@postgres:5432/orders
ENV HTTP_PORT=8088

EXPOSE 8088
CMD ["python", "-u", "main.py"]
