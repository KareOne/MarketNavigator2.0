FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Xvfb and other dependencies for headed browser in containers
RUN apt-get update && apt-get install -y \
    xvfb \
    x11-utils \
    xauth \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install playwright && playwright install-deps && playwright install

COPY . /app/

EXPOSE 8910

CMD ["xvfb-run", "-a", "--server-args=-screen 0 1024x768x24", "python", "api.py"]

