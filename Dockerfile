FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
  python3 python3-pip \
  chromium-browser chromium-chromedriver \
  xvfb \
  libglib2.0-0=2.50.3-2 \
  libnss3=2:3.26.2-1.1+deb9u1 \
  libgconf-2-4=3.2.6-4+b1 \
  libfontconfig1=2.11.0-6.7+b1 \
  && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# App
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt \
    # Remove temporary files
    && rm -rf /root/.cache

COPY src .
COPY package.json ../

EXPOSE 8080

ENTRYPOINT ["python3", "-u", "./abtorrents-proxy.py"]

LABEL org.opencontainers.image.source=https://github.com/captmicr0/abtorrents-proxy

# Local build
# docker build -t captmicr0/abtorrents-proxy:1.3.0 .
# docker run captmicr0/abtorrents-proxy:1.3.0
