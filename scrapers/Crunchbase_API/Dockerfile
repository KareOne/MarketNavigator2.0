FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install -r requirements.txt
RUN pip install playwright && playwright install-deps && playwright install


COPY . /app/

EXPOSE 8003

CMD ["python", "api_handler.py"]
