# ABTorrents Proxy

ABTorrents Proxy is a Python script that acts as a proxy server, providing an HTTP server to forward requests to an ABTorrents Selenium browser instance. It is designed to make the Cardigan custom definition able to handle logins and search ABTorrents via the Selenium instance.

## Features

- HTTP server forwarding requests to an ABTorrents Selenium browser instance.
- Handles logins and searches on ABTorrents.
- Uses Selenium and ChromeDriver for browser automation.

## Prerequisites

- Docker

## Configuration

Set the following environment variables before running the script:

    ABT_URL: ABTorrents URL (not required, defaults to https://abtorrents.me/)
    ABT_PROXYPORT: Proxy port (not required, defaults to default: 8080)
    ABT_USERNAME: ABTorrents username (not required)
    ABT_PASSWORD: ABTorrents password (not required)

## Usage

Local build:
```
git clone https://github.com/captmicr0/abtorrents-proxy
cd abtorrents-proxy
docker build -t captmicr0/abtorrents-proxy:1.3.0 .
docker run captmicr0/abtorrents-proxy:1.3.0
```

Install abtorrents-proxy.yml in Prowlarr by adding it to the Definitions/Custom folder.
Add a new proxy in prowlarr, entering the docker container hostname or IP and port (default port 8080).
Add a new indexer in prowlarr, chosing abtorrents-proxy, and entering your username and password.
Configure the indexer to use the proxy you added.

## License

The proxy server and ABTProwlarrHandler server will start. The proxy will overwrite requests to ABTorrents, allowing Cardigan to use ABTorrents as a custom indexer.
License

This project is licensed under the MIT License.
