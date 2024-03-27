FROM python:3.11-alpine

# Update apk repo
RUN echo "http://dl-4.alpinelinux.org/alpine/v3.14/main" >> /etc/apk/repositories && \
    echo "http://dl-4.alpinelinux.org/alpine/v3.14/community" >> /etc/apk/repositories

# Install chromedriver
RUN apk update
#RUN apk add bash chromium chromium-chromedriver

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

ENTRYPOINT ["python", "-u", "./abtorrents-proxy.py"]

LABEL org.opencontainers.image.source=https://github.com/captmicr0/abtorrents-proxy

# Local build
# docker build -t captmicr0/abtorrents-proxy:1.3.0 .
# docker run captmicr0/abtorrents-proxy:1.3.0
