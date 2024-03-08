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

## Docker container build

Local build:
```
git clone https://github.com/captmicr0/abtorrents-proxy
cd abtorrents-proxy
docker build -t captmicr0/abtorrents-proxy:1.3.0 .
```

## Docker container usage
```
docker run captmicr0/abtorrents-proxy:1.3.0 -d
```

The proxy server and ABTProwlarrHandler server will start.
The proxy will overwrite requests to ABTorrents domain, forwarding them to the ABTProwlarrServer instance.
The ABTProwlarrServer instance will request the page from the ABTorrents instance which will return the webpages source.
It checks for unread PM's after login and before each request made by the ABTProwlarrServer instance,
if any exist it will open them which marks them as read, and resume returning the webpages source.

## Prowlarr configuration
Install abtorrents-proxy.yml in Prowlarr by adding it to the Definitions/Custom folder.
Add a new proxy in prowlarr, entering the docker container hostname or IP and port (default port 8080).
Add a new indexer in prowlarr, chosing abtorrents-proxy, and entering your username and password.
Configure the indexer to use the proxy you added.

## License

This project is licensed under the MIT License.


## Example/Expected output
```
[*] ABTorrents-proxy starting...

DevTools listening on ws://127.0.0.1:20565/devtools/browser/5be5f2dd-ff0f-46fe-b4fc-7fe5b4e30ef9
[ABTorrents] cookie file ./cookies.json does not exist.
[0307/231409.901:ERROR:cert_issuer_source_aia.cc(35)] Error parsing cert retrieved from AIA (as DER):
ERROR: Couldn't read tbsCertificate as SEQUENCE
ERROR: Failed parsing Certificate

[*] abtProwlarrServer init [ localhost:8333 ]
[*] overwriteProxyServer init [ :8080 ]
[*] creating threads
[*] starting threads
[ABTProwlarrHandler] requesting login form: /doLogin.py
[ABTProwlarrHandler] attempting login: /doLogin.py
[ABTorrents] login successful
[ABTorrents] saving cookies in ./cookies.json
[{'domain': 'abtorrents.me',
  'expiry': 1712463262,
  'httpOnly': True,
  'name': 'remember',
  'path': '/',
  'sameSite': 'Lax',
  'secure': True,
  'value': '****removed****'},
 {'domain': '.abtorrents.me',
  'httpOnly': True,
  'name': 'ABTorrents',
  'path': '/',
  'sameSite': 'Strict',
  'secure': True,
  'value': '****removed****'}]
[ABTProwlarrHandler] requesting url: /index.php
[ABTorrents] getting page source for: https://abtorrents.me/index.php
[0307/231514.261:WARNING:spdy_session.cc(2978)] Received HEADERS for invalid stream 249
[ABTProwlarrHandler] requesting url: /browse.php
[ABTorrents] getting page source for: https://abtorrents.me/browse.php
```
