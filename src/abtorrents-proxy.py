import os, sys, tempfile
import pprint

#import undetected_chromedriver as driver
from selenium import webdriver as driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import pickle
import cv2

class ABTorrents:
    def __init__(self, webdrv, baseUrl, cookieFile, captchaTemplateDir):
        # Save for later
        self.cookieFile = cookieFile
        self.baseUrl = baseUrl

        # Captcha Templates
        self.captchaTemplates = [os.path.join(captchaTemplateDir,img) for img in os.listdir(captchaTemplateDir)]

        # Configure chrome options
        self.chrome_options = webdrv.ChromeOptions()
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--single-process')
        self.chrome_options.add_argument('--no-zygote')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument('log-level=3')

        # Open browser
        self.webdriver = webdrv.Chrome(options=self.chrome_options)

        # Load cookies
        self.loadCookies()

        # Setup wait for later
        self.wait = WebDriverWait(self.webdriver, 10)

        # Open ABTorrents
        self.webdriver.get(self.baseUrl)
    
    def saveCookies(self):
        print("[ABTorrents] saving cookies in " + self.cookieFile)
        pickle.dump(self.webdriver.get_cookies() , open(self.cookieFile,"wb"))
        pprint.pp(self.webdriver.get_cookies())

    def loadCookies(self):
        if os.path.exists(self.cookieFile) and os.path.isfile(self.cookieFile):
            print("[ABTorrents] loading cookies from " + self.cookieFile)
            cookies = pickle.load(open(self.cookieFile, "rb"))

            # Enables network tracking so we may use Network.setCookie method
            self.webdriver.execute_cdp_cmd('Network.enable', {})

            # Iterate through pickle dict and add all the cookies
            for cookie in cookies:
                # Fix issue Chrome exports 'expiry' key but expects 'expire' on import
                if 'expiry' in cookie:
                    cookie['expires'] = cookie['expiry']
                    del cookie['expiry']

                # Replace domain 'apple.com' with 'microsoft.com' cookies
                cookie['domain'] = cookie['domain'].replace('apple.com', 'microsoft.com')

                # Set the actual cookie
                self.webdriver.execute_cdp_cmd('Network.setCookie', cookie)

            # Disable network tracking
            self.webdriver.execute_cdp_cmd('Network.disable', {})
            return 1

        print("[ABTorrents] cookie file " + self.cookieFile + " does not exist.")
        return 0

    def findMatchingIcon(self, inputImagePath, threshold=0.8):
        # Read the input image
        inputImage = cv2.imread(inputImagePath)

        # Initialize variables to store the best match information
        bestMatchValue = 0
        bestMatchTemplate = None

        # Perform template matching for each template image
        for templatePath in self.captchaTemplates:
            template = cv2.imread(templatePath, cv2.IMREAD_UNCHANGED)

            # Split the template into image and alpha components
            templateImg = template[:, :, :3]
            templateAlpha = template[:, :, 3]  # Alpha channel without normalization

            # Ensure the alpha channel has the correct depth
            templateAlpha = cv2.cvtColor(templateAlpha, cv2.COLOR_GRAY2BGR)

            # Perform matching considering alpha values
            result = cv2.matchTemplate(inputImage[:, :, :3], templateImg, cv2.TM_CCOEFF_NORMED, mask=templateAlpha)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            # Check if the current template is a better match
            if max_val > bestMatchValue:
                bestMatchValue = max_val
                bestMatchTemplate = templatePath

        # Check if the best match exceeds the threshold
        if bestMatchValue >= threshold:
            return bestMatchTemplate

        raise Exception("No match found!")
    
    def doLogin(self, username, password):
        # Go to login page
        self.webdriver.get(urljoin(self.baseUrl, "/login.php"))
        
        # Make sure it actually the login page and not redirected to homepage
        if not "login.php" in self.webdriver.current_url:
            print("[ABTorrents] still not on login page")
            if self.webdriver.current_url.endswith("index.php"):
                print("[ABTorrents] redirected to index.php, must be logged in already")
                self.checkPMs()
                return 1
            return 0
        
        # Wait for captcha images to load
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "captchaImage"))
            )
        except:
            print("[ABTorrents] no captchaImage elements found")
            return 0

        # Create temp directory for saving captcha images
        captchaTempDir = tempfile.mkdtemp()
        
        # Save captcha images in order and match to templates
        captchaImages = self.webdriver.find_elements(By.CLASS_NAME, "captchaImage")
        captchaMatches = []
        for img in captchaImages:
            imgFn = os.path.join(captchaTempDir, "captchaImage-%d.png" % captchaImages.index(img))
            img.screenshot(imgFn)
            try:
                matchingIcon = self.findMatchingIcon(imgFn) 
                matchingIconFn = os.path.split(matchingIcon)[1]
                matchingIconName = os.path.splitext(matchingIconFn)[0]
                captchaMatches.append(matchingIconName)
            except Exception as err:
                print("[ABTorrents] error matching image (%s)" % imgFn, err)
                return 0

        # Get which icon we need to click on
        captchaText = self.webdriver.find_element(By.CLASS_NAME, "captchaText").text
        captchaToClick = captchaImages[captchaMatches.index(captchaText)]

        # Enter username and password
        usernameBox = self.webdriver.find_element(By.NAME, "username")
        passwordBox = self.webdriver.find_element(By.NAME, "password")
        usernameBox.send_keys(username)
        passwordBox.send_keys(password)

        # Check the "Remember Me?" checkbox
        remember = self.webdriver.find_element(By.NAME, "remember")
        if not remember.is_selected(): remember.click()

        # Click the correct captcha icon
        captchaToClick.click()

        # Find the X and click to login
        currURL = self.webdriver.current_url
        submit = self.webdriver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='X']")
        submit.click()

        print("[ABTorrents] submitted login form, waiting for url to change...")

        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='logout.php']"))
            )
        except (NoSuchElementException, TimeoutException) as e:
            print(f"[ABTorrents] login failed: {e}")
            return 0

        print("[ABTorrents] login successful")
        
        # Save cookies
        self.saveCookies()

        # Check for PMs
        self.checkPMs()

        return 1
    
    def doLogout(self):
        try:
            # Wait for logout button to exist and click it
            logoutLink = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='logout.php']"))
            )
            logoutLink.click()
            print("[ABTorrents] logout successful")
        except (NoSuchElementException, TimeoutException) as e:
            print("[ABTorrents] logout failed: {e}")

    def getPageSource(self, path):
        # Create return variables
        repsonseHTML = "Error fetching page source"
        responseCode = 500

        # Do nothing if on the login page
        if "login.php" in self.webdriver.current_url:
            responseHTML="redirected to login.php, you need to login first"
            print(f"[ABTorrents] {responseHTML}")
            return responseCode, responseHTML

        # Join the baseUrl and requested path 
        reqUrl = urljoin(self.baseUrl, path)
        print("[ABTorrents] getting page source for: %s" % reqUrl)

        # Open a new tab
        numWindowsBefore = len(self.webdriver.window_handles)
        windowBefore = self.webdriver.current_window_handle

        self.webdriver.switch_to.new_window('tab')

        # Wait until new tab is open
        self.wait.until(EC.number_of_windows_to_be(numWindowsBefore + 1))

        try:
            # Go to requested URL
            self.webdriver.get(reqUrl)

            # Check for PMs
            self.checkPMs()
            
            # Wait for body tag again
            self.wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Save the page source
            responseHTML = self.webdriver.page_source
            responseCode = 200
        finally:
            self.webdriver.close()
            self.webdriver.switch_to.window(windowBefore)

        # Pass back to caller
        return responseCode, responseHTML

    def checkPMs(self):
        # Save current URL
        preCheckUrl = self.webdriver.current_url

        if "login" in preCheckUrl: return 0

        # Check if PMs need read
        try:
            # Wait for base_globelmessage tag
            self.wait.until(
                EC.presence_of_element_located((By.ID, "base_globelmessage"))
            )
            # Check if warning exists
            newPMalert = self.webdriver.find_element(By.CSS_SELECTOR, "a[href*='pm_system.php'] > b.alert-warning")
            self.readPMs()
            # Go to old URL
            self.webdriver.get(preCheckUrl)
        except (NoSuchElementException, TimeoutException):
            pass

        return 0

    def readPMs(self):
        print("[ABTorrents] reading unread PMs")
        try:
            self.webdriver.get(urljoin(self.baseUrl, "/pm_system.php"))

            # Wait for body tag
            self.wait.until(
                EC.presence_of_element_located((By.ID, "base_globelmessage"))
            )
            
            # Find all PM links and message status images
            viewMessageLinks = self.webdriver.find_elements(By.CSS_SELECTOR, "tr > td > a[href*='pm_system.php?action=view_message']")
            msgStatusPictures = self.webdriver.find_elements(By.CSS_SELECTOR, "tr > td > img[src*='pic/pn_inbox']")[:-2]

            # Check if same number of matching elements
            if len(viewMessageLinks) != len(msgStatusPictures): raise Exception("not same amount of PM links and status images")
            
            # Check for unread ones and read them
            msgCount = len(viewMessageLinks)
            for idx in range(msgCount):
                status = ("pn_inboxnew" in msgStatusPictures[idx].get_attribute("src")) and "new" or "old"
                if status == "new":
                    link = viewMessageLinks[idx]
                    print("[ABTorrents] reading new message: %s" % link.text)
                    linkURL = link.get_attribute("href")
                    # Open new tab and switch to it
                    numWindowsBefore = len(self.webdriver.window_handles)
                    windowBefore = self.webdriver.current_window_handle
                    self.webdriver.switch_to.new_window('tab')
                    # Wait until tab is open
                    self.wait.until(EC.number_of_windows_to_be(numWindowsBefore + 1))
                    # Go to PM url
                    self.webdriver.get(linkURL)
                    # Wait until delete button exists
                    try:
                        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[value*='delete']")))
                    except:
                        print("[ABTorrents] delete button not found")
                    # Close tab and switch to original window
                    self.webdriver.close()
                    self.webdriver.switch_to.window(windowBefore)
        except Exception as err:
            print("[ABTorrents] error reading PMs", err)

    def quit(self, exitCode=0):
        # Exit browser
        self.webdriver.quit()


from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import HTTPConnection
import socket, select, ssl
from urllib.parse import urljoin, urlsplit, urlparse, parse_qs

# This class acts as an HTTP server that forwards requests to the ABTorrents selenium browser instance.
# It make the cardigan custom definition able to handle logins and search ABTorrents via the selenium instance
class ABTProwlarrHandler(BaseHTTPRequestHandler):
    def __init__(self, abt, *args, **kwargs):
        self.abt = abt
        # BaseHTTPRequestHandler calls do_GET **inside** __init__ !!!
        # So we have to call super().__init__ after setting attributes.
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        return
    
    # Process GET requests
    def do_GET(self):
        validPages = ["index.php", "browse.php", "pm_system.php", 'doLogin.py']
        if any(page in self.path for page in validPages):
            print(f"[ABTProwlarrHandler] requesting url: {self.path}")
            if "doLogin.py" in self.path:
                # Handle login
                response  = "<html><head><title>abtorrents-proxy</title></head><body>"
                if "doLogin.py?" not in self.path:
                    print(f"[ABTProwlarrHandler] requesting login form: {self.path}")
                    response += "<form action='/doLogin.py' method='post'>"
                    response += "<label for='username'>Username:</label>"
                    response += "<input type='text' id='username' name='username' placeholder='username'/>"
                    response += "<label for='password'>Password:</label>"
                    response += "<input type='password' id='password' name='password' placeholder='password'/>"
                    response += "<input type='submit' id='submit' name='submit' value='Submit'/>"
                    response += "</form>"
                else:
                    print(f"[ABTProwlarrHandler] attempting login: {self.path}")
                    try:
                        parsed = urlparse(self.path)
                        params = parse_qs(parsed.query)
                        if all(key in params for key in ['username','password']):
                            print(f"params: {params}")
                            # Try to login
                            if self.abt.doLogin(params["username"], params["password"]):
                                response += "<span id='login_success'>login success</span>"
                            else:
                                response += "<span id='login_failed'>login failed</span>"
                        else:
                            # Raise exception if content_length is 0
                            raise Exception
                    except:
                        response += "<span id='login_failed'>login exception</span>"
                # Send response
                response += "</body></html>"
                self.send_response(200)
                self.send_header("Content-type","text/html")
                self.end_headers()
                self.wfile.write(bytes(response, "utf-8"))
            else:
                # Get page source from selenium browser
                responseCode, responseHTML = self.abt.getPageSource(self.path)
                self.send_response(responseCode)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(bytes(responseHTML, "utf-8"))
        else:
            print(f"[ABTProwlarrHandler] requested INVALID page: {self.path}")
            self.send_response(500)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("requested invalid page", "utf-8"))

    # Process POST requests to /doLogin.py
    def do_POST(self):
        # Handle login (for some reason POST login does not work... hangs on self.rfile.read, so using GET for now
        """
        if self.path == "/doLogin.py":
            print(f"[ABTProwlarrHandler] attempting login: {self.path}")
            response  = "<html><head><title>abtorrents-proxy</title></head><body>"
            try:
                # Check if there is any form data
                content_length = int(self.headers["Content-Length"])
                if content_length:
                    # Parse the form data
                    content = self.rfile.read(content_length).decode("utf-8")
                    form = parse_qs(content)
                    # Get the username and password values
                    username = form.getvalue("username")
                    password = form.getvalue("password")
                    # Try to login
                    if self.abt.doLogin(username, password):
                        response += "<span id='login_success'>login success</span>"
                    else:
                        response += "<span id='login_failed'>login failed</span>"
                else:
                    # Raise exception if content_length is 0
                    raise Exception
            except:
                response += "<span id='login_failed'>login exception</span>"
            response += "</body></html>"
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes(response, "utf-8"))
        else:
            print(f"[ABTProwlarrHandler] requested INVALID page: {self.path}")
            self.send_response(500)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(bytes("requested invalid page", "utf-8"))
        """

# This class acts as an HTTP proxy that overwrites specific webserver addresses and ports.
# This is so the cardigan custom definition doesn't require changing the URL for different ctonainer hostnames.
# Instead you just setup a proxy and setup the custom indexer definition to use that proxy,
# which will overwrite the abtorrents.me domain.
class OverwriteProxyHandler(BaseHTTPRequestHandler):
    def __init__(self, overwrites, *args, **kwargs):
        self.overwrites = overwrites
        # BaseHTTPRequestHandler calls do_GET **inside** __init__ !!!
        # So we have to call super().__init__ after setting attributes.
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        return
    
    def do_GET(self):
        self.proxy_request('GET')

    def do_POST(self):
        self.proxy_request('POST')

    # Process CONNECT requests
    def do_CONNECT(self):
        self.connect_relay()
    
    def connect_relay(self):
        address = self.path.split(':', 1)
        address[1] = int(address[1]) or 443
        try:
            s = socket.create_connection(address, timeout=self.timeout)
        except Exception as e:
            self.send_error(502)
            return
        self.send_response(200, 'Connection Established')
        self.end_headers()

        conns = [self.connection, s]
        self.close_connection = 0
        while not self.close_connection:
            rlist, wlist, xlist = select.select(conns, [], conns, self.timeout)
            if xlist or not rlist:
                break
            for r in rlist:
                other = conns[1] if r is conns[0] else conns[0]
                data = r.recv(8192)
                if not data:
                    self.close_connection = 1
                    break
                other.sendall(data)

    def proxy_request(self, method):
        try:
            # Extract the webserver, port, and path from the request
            print(f"[OverwriteProxyHandler] proxy {method} requests: {self.path}")
            parts = urlsplit(self.path)

            netloc = parts.netloc.split(':')
            webserver, port = netloc[0], len(netloc)==2 and netloc[1] or 80
            
            path = self.path[self.path.index(parts.path):]
            
            if webserver in self.overwrites.keys():
                # Process overwrite
                webserver, port = self.overwrites[webserver]
                print(f"[OverwriteProxyHandler] overwriting {self.path} to http://{webserver}:{port}{path}")
                
                # Connect to the target server
                target_conn = HTTPConnection(webserver, int(port))

                # Forward the client request to the target server
                target_conn.request(method, path, headers=self.headers)
                target_response = target_conn.getresponse()

                # Send the target server's response back to the client
                self.send_response(target_response.status)
                for header, value in target_response.getheaders():
                    self.send_header(header, value)
                self.end_headers()

                self.wfile.write(target_response.read())
            else:
                self.send_error(500, f'[OverwriteProxyHandler] not in overwrite list: {webserver}')

        except Exception as e:
            self.send_error(500, f'[OverwriteProxyHandler] Internal Server Error: {str(e)}')

import signal, threading
from functools import partial

def signalHandler(args, signum=99999, frame=None):
    abt, abtProxyHandlerServer, overwriteProxyServer = args
    print(f"[*] received signal {signum}. shutting down.")
    print("[*] shutting down overwriteProxyServer")
    overwriteProxyServer.shutdown()
    print("[*] shutting down abtProwlarrServer")
    abtProxyHandlerServer.shutdown()
    print("[*] shutting down abt")
    abt.quit()

def runServer(server):
    server.serve_forever()

if __name__ == "__main__":
    print("[*] ABTorrents-proxy starting...")

    # Get ENV vars
    baseurl= "ABT_URL" in os.environ.keys() and os.environ["ABT_URL"] or "https://abtorrents.me/"
    proxyPort = "ABT_PROXYPORT" in os.environ.keys() and int(os.environ["ABT_PROXYPORT"]) or 8080

    # Setup ABTorrents instance
    abt = ABTorrents(driver, baseurl, './cookies.json', './captchaImages')
    
    # Login if ABT_USERNAME and ABT_PASSWORD exist in environment variables
    if ("ABT_USERNAME" in os.environ.keys()) and ("ABT_PASSWORD" in os.environ.keys()):
        abt.doLogin(os.environ["ABT_USERNAME"], os.environ["ABT_PASSWORD"])

    # Setup ABTProwlarrHandler instance
    abtProwlarrAddr = ('localhost', 8333)
    print("[*] abtProwlarrServer init [ %s:%d ]" % abtProwlarrAddr)
    abtProwlarrServer = ThreadingHTTPServer(abtProwlarrAddr, partial(ABTProwlarrHandler, abt))

    # Setup OverwriteProxyHandler instance
    overwriteProxyAddr = ('', proxyPort)
    overwrites = {
        'abtorrents.me': abtProwlarrAddr,
    }
    print("[*] overwriteProxyServer init [ %s:%d ]" % overwriteProxyAddr)
    overwriteProxyServer = ThreadingHTTPServer(overwriteProxyAddr, partial(OverwriteProxyHandler, overwrites))
    
    # Register the signal handler for SIGTERM
    signal.signal(signal.SIGTERM, partial(signalHandler, (abt, abtProwlarrServer, overwriteProxyServer)))
    signal.signal(signal.SIGINT, partial(signalHandler, (abt, abtProwlarrServer, overwriteProxyServer)))

    # Windows specific signal handler fix
    if sys.platform == "win32":
        import win32api
        win32api.SetConsoleCtrlHandler(partial(signalHandler, (abt, abtProwlarrServer, overwriteProxyServer)), True)

    # Create threads
    print("[*] creating threads")
    abtProwlarrThread = threading.Thread(target=runServer, args=(abtProwlarrServer,))
    overwriteProxyThread = threading.Thread(target=runServer, args=(overwriteProxyServer,))

    # Start threads
    abtProwlarrThread.start()
    print("[*] starting threads")
    overwriteProxyThread.start()

    # Wait for the server thread to finish
    abtProwlarrThread.join()
    overwriteProxyThread.join()

    print("[*] ABTorrents-proxy exiting...")
