import os, sys, tempfile, pprint
import signal, threading, time
from functools import partial

os.environ['FOR_DISABLE_CONSOLE_CTRL_HANDLER'] = '1'

#import undetected_chromedriver as driver
from selenium import webdriver as driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import pickle
import cv2

def browserCloseTimeout(abt):
    # Check if the browser had any activity for the last
    # closeTimeout period, and if not close the browser
    while abt.timeoutThreadRunning:
        if ((time.time() - abt.lastCheckedOpen) > abt.closeTimeout):
            if abt.checkBrowserOpen():
                print("[browserCloseTimeout] closing browser")
                abt.closeBrowser()
        time.sleep(0.01)

class ABTorrents:
    def __init__(self, baseUrl, cookieFile, captchaTemplateDir, closeTimeout=5*60):
        # Save for later
        self.cookieFile = cookieFile
        self.baseUrl = baseUrl

        self.closeTimeout = closeTimeout
        self.lastCheckedOpen = time.time()
        self.timeoutThreadRunning = True
        self.timeoutThread = threading.Thread(target=browserCloseTimeout, args=(self,))
        self.timeoutThread.start()

        self.prepareCaptchaTemplates(captchaTemplateDir)

        # Configure chrome options
        self.chrome_options = driver.ChromeOptions()
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--headless=new')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--single-process')
        self.chrome_options.add_argument('--no-zygote')
        self.chrome_options.add_argument("--window-size=1280,720")

        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument("--disable-crash-reporter")
        self.chrome_options.add_argument("--disable-extensions")
        self.chrome_options.add_argument("--disable-renderer-backgrounding")
        self.chrome_options.add_argument("--disable-background-timer-throttling")
        self.chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        self.chrome_options.add_argument("--disable-client-side-phishing-detection")
        self.chrome_options.add_argument("--disable-crash-reporter")
        self.chrome_options.add_argument("--disable-oopr-debug-crash-dump")
        self.chrome_options.add_argument("--no-crash-upload")
        self.chrome_options.add_argument("--silent")
        self.chrome_options.add_argument('log-level=3')

    def openBrowser(self):
        # Open browser
        self.webdriver = driver.Chrome(options=self.chrome_options)

        # Setup wait for later
        self.wait = WebDriverWait(self.webdriver, 10)

        # Wait for it to open
        self.webdriver.get(self.baseUrl)
        #self.wait.until(EC.number_of_windows_to_be(1))
        
        # Wait for body tag again
        #self.wait.until(
        #    EC.presence_of_element_located((By.TAG_NAME, "body"))
        #)

        # Load cookies
        self.loadCookies()
        
        # Save the time for close timeout
        self.lastCheckedOpen = time.time()
    
    def checkBrowserOpen(self):
        try:
            # This will raise an exception if browser is not open
            temp = self.webdriver.window_handles
            # Save the time for close timeout
            self.lastCheckedOpen = time.time()
            return True
        except:
            return False

    def ensureBrowserOpen(self):
        # Make sure browser is open
        try:
            # This will raise an exception if browser is not open
            temp = self.webdriver.window_handles
        except Exception as e:
            self.openBrowser()
        finally:
            # Save the time for close timeout
            self.lastCheckedOpen = time.time()
    
    def closeBrowser(self):
        # Exit browser
        try:
            if self.checkBrowserOpen(): self.webdriver.quit()
        except:
            # Already closed
            pass
    
    def shutdown(self):
        self.timeoutThreadRunning = False
        self.closeBrowser()
    
    def saveCookies(self):
        if not self.checkBrowserOpen(): return

        print("[ABTorrents.saveCookies] saving cookies in " + self.cookieFile)
        pickle.dump(self.webdriver.get_cookies() , open(self.cookieFile,"wb"))
        pprint.pp(self.webdriver.get_cookies())

    def loadCookies(self):
        if not self.checkBrowserOpen(): return
        
        if os.path.exists(self.cookieFile) and os.path.isfile(self.cookieFile):
            print("[ABTorrents.loadCookies] loading cookies from " + self.cookieFile)
            cookies = pickle.load(open(self.cookieFile, "rb"))

            # Enables network tracking so we may use Network.setCookie method
            self.webdriver.execute_cdp_cmd('Network.enable', {})

            # Iterate through pickle dict and add all the cookies
            for cookie in cookies:
                # Fix issue Chrome exports 'expiry' key but expects 'expire' on import
                if 'expiry' in cookie:
                    cookie['expires'] = cookie['expiry']
                    del cookie['expiry']

                # Set the actual cookie
                self.webdriver.execute_cdp_cmd('Network.setCookie', cookie)

            # Disable network tracking
            self.webdriver.execute_cdp_cmd('Network.disable', {})
            return 1

        print("[ABTorrents.loadCookies] cookie file " + self.cookieFile + " does not exist.")
        return 0

    def prepareCaptchaTemplates(self, captchaTemplateDir):
        # Prepare template matching for each template image
        self.captchaTemplates = {}

        try:
            # Get a list of template paths
            self.captchaTemplateImages = [os.path.join(captchaTemplateDir,img) for img in os.listdir(captchaTemplateDir)]
            
            for templatePath in self.captchaTemplateImages:
                # Read image
                template = cv2.imread(templatePath, cv2.IMREAD_UNCHANGED)

                # Split the template into image and alpha components
                templateImg = template[:, :, :3]
                templateAlpha = template[:, :, 3]  # Alpha channel without normalization

                # Ensure the alpha channel has the correct depth
                templateAlpha = cv2.cvtColor(templateAlpha, cv2.COLOR_GRAY2BGR)

                # Extract icon name from path
                iconFn = os.path.split(templatePath)[1]
                iconName = os.path.splitext(iconFn)[0]

                # Add to dictionary
                self.captchaTemplates[iconName.lower()] = {
                    'img': templateImg,
                    'alpha': templateAlpha
                }
        except Exception as e:
            print(f"[ABTorrents.prepareCaptchaTemplates] error {e}")
        
        print(f"[ABTorrents.prepareCaptchaTemplates] {self.captchaTemplates.keys()}")

    def findMatchingIcon(self, inputImagePath, threshold=0.8):
        # Read the input image
        inputImage = cv2.imread(inputImagePath)

        # Initialize variables to store the best match information
        bestMatchValue = 0
        bestMatchTemplate = None

        # Perform matching for each template
        for template in self.captchaTemplates:
            # Perform matching considering alpha values
            result = cv2.matchTemplate(inputImage[:, :, :3],
                                       self.captchaTemplates[template]['img'],
                                       cv2.TM_CCOEFF_NORMED,
                                       mask=self.captchaTemplates[template]['alpha'])
            _, max_val, _, _ = cv2.minMaxLoc(result)

            # Check if the current template is a better match
            if max_val > bestMatchValue:
                bestMatchValue = max_val
                bestMatchTemplate = template

        # Check if the best match exceeds the threshold
        if bestMatchValue >= threshold:
            return bestMatchTemplate

        raise Exception("No match found!")
    
    def doLogin(self, username, password):
        print("[ABTorrents.doLogin]")
        self.ensureBrowserOpen()

        # Go to login page
        print("[ABTorrents.doLogin] go to login page")
        self.webdriver.get(urljoin(self.baseUrl, "/login.php"))
        
        # Make sure it actually the login page and not redirected to homepage
        print("[ABTorrents.doLogin] check if on login page")
        if "login.php" not in self.webdriver.current_url:
            print("[ABTorrents.doLogin] still not on login page")
            if "index.php" in self.webdriver.current_url:
                print("[ABTorrents.doLogin] on index.php, must be logged in already")
                self.checkPMs()
                return 1
            return 0
        
        # Wait for captcha images to load
        print("[ABTorrents.doLogin] waiting for captcha images to load...")
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "captchaImage"))
            )
        except:
            print("[ABTorrents.doLogin] no captchaImage elements found")
            return 0

        # Create temp directory for saving captcha images
        captchaMatches = []
        captchaTempDir = tempfile.mkdtemp()

        # Save captcha images in order and match to templates
        captchaImages = self.webdriver.find_elements(By.CLASS_NAME, "captchaImage")
        for img in captchaImages:
            imgFn = os.path.join(captchaTempDir, "captchaImage-%d.png" % captchaImages.index(img))
            img.screenshot(imgFn)
            try:
                matchingIcon = self.findMatchingIcon(imgFn) 
                captchaMatches.append(matchingIcon)
            except Exception as err:
                print("[ABTorrents.doLogin] error matching image (%s)" % imgFn, err)
                return 0

        # Get which icon we need to click on
        captchaText = self.webdriver.find_element(By.CLASS_NAME, "captchaText").text.lower()
        captchaToClick = captchaImages[captchaMatches.index(captchaText)]

        # Enter username and password
        print("[ABTorrents.doLogin] enering username and password...")
        usernameBox = self.webdriver.find_element(By.NAME, "username")
        passwordBox = self.webdriver.find_element(By.NAME, "password")
        usernameBox.send_keys(username)
        passwordBox.send_keys(password)

        # Check the "Remember Me?" checkbox
        print("[ABTorrents.doLogin] checking 'Remember Me?'...")
        remember = self.webdriver.find_element(By.NAME, "remember")
        if not remember.is_selected(): remember.click()

        # Click the correct captcha icon
        print(f"[ABTorrents.doLogin] clicking captcha icon {captchaText}...")
        captchaToClick.click()

        # Find the X and click to login
        print("[ABTorrents.doLogin] finding X...")
        currURL = self.webdriver.current_url
        submit = self.webdriver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='X']")
        print(f"[ABTorrents.doLogin] {submit}")
        time.sleep(2)
        print("[ABTorrents.doLogin] clicking X...")
        self.webdriver.execute_script("document.querySelector(\"input[type='submit'][value='X']\").form.submit();");
        time.sleep(5)
        #submit.click()
        
        print("[ABTorrents.doLogin] submitted login form, logout link to appear...")

        
        try:
            #print(f"[ABTorrents.doLogin] current_url: {self.webdriver.current_url}")
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='logout.php']"))
            )
            #WebDriverWait(self.webdriver, 5).until(EC.url_changes(currURL))
        except Exception as e:
            print(f"[ABTorrents.doLogin] login failed: {e}")
            return 0

        print("[ABTorrents.doLogin] login successful")
        
        # Save cookies
        self.saveCookies()

        # Check for PMs
        self.checkPMs()

        return 1
    
    def doLogout(self):
        self.ensureBrowserOpen()

        # Go to index page
        self.webdriver.get(urljoin(self.baseUrl, "/index.php"))

        try:
            # Wait for logout button to exist and click it
            logoutLink = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='logout.php']"))
            )
            logoutLink.click()
            print("[ABTorrents.doLogout] logout successful")
        except (NoSuchElementException, TimeoutException) as e:
            print("[ABTorrents.doLogout] logout failed: {e}")

    def getPageSource(self, path):
        self.ensureBrowserOpen()

        # Create return variables
        repsonseHTML = "Error fetching page source"
        responseCode = 500

        # Do nothing if on the login page
        if "login.php" in self.webdriver.current_url:
            responseHTML="redirected to login.php, you need to login first"
            print(f"[ABTorrents.getPageSource] {responseHTML}")
            return responseCode, responseHTML

        # Join the baseUrl and requested path 
        reqUrl = urljoin(self.baseUrl, path)
        print("[ABTorrents.getPageSource] getting page source for: %s" % reqUrl)

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
        self.ensureBrowserOpen()

        # Save current URL
        preCheckUrl = self.webdriver.current_url

        if "login.php" in self.webdriver.current_url:
            print(f"[ABTorrents.checkPMs] redirected to login.php, you need to login first")
            return 0

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
        self.ensureBrowserOpen()

        print("[ABTorrents.readPMs] reading unread PMs")
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
                    print("[ABTorrents.readPMs] reading new message: %s" % link.text)
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
                        print("[ABTorrents.readPMs] delete button not found")
                    # Close tab and switch to original window
                    self.webdriver.close()
                    self.webdriver.switch_to.window(windowBefore)
        except Exception as err:
            print("[ABTorrents.readPMs] error reading PMs", err)


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
                    response += "<form action='/doLogin.py' method='get'>"
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
                    except Exception as e:
                        response += f"<span id='login_failed'>login exception {e}</span>"
                        print(f"[ABTProwlarrHandler] login exception: {e}")
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
            
            print(f"[OverwriteProxyHandler]   webserver='{webserver}' port={port} path='{path}'")
            
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
                self.send_error(500, f"[OverwriteProxyHandler] not in overwrite list: '{webserver}'")

        except Exception as e:
            self.send_error(500, f'[OverwriteProxyHandler] Internal Server Error: {str(e)}')

def signalHandler(args, signum=99999, frame=None):
    abt, abtProxyHandlerServer, overwriteProxyServer = args
    print(f"[*] received signal {signum}. shutting down.")
    print("[*] shutting down overwriteProxyServer")
    overwriteProxyServer.shutdown()
    print("[*] shutting down abtProwlarrServer")
    abtProxyHandlerServer.shutdown()
    print("[*] shutting down abt")
    abt.shutdown()
    return True

def runServer(server):
    server.serve_forever()

if __name__ == "__main__":
    print("[*] ABTorrents-proxy starting...")

    # Get ENV vars
    baseurl= "ABT_URL" in os.environ.keys() and os.environ["ABT_URL"] or "https://abtorrents.me/"
    proxyPort = "ABT_PROXYPORT" in os.environ.keys() and int(os.environ["ABT_PROXYPORT"]) or 8080

    # Setup ABTorrents instance
    abt = ABTorrents(baseurl, './cookies.json', './captchaImages')
    
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
        '': abtProwlarrAddr,
    }
    print("[*] overwriteProxyServer init [ %s:%d ]" % overwriteProxyAddr)
    print(f"[*] overwriteProxyServer overwrites: {overwrites}")
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
    abt.timeoutThread.join()

    print("[*] ABTorrents-proxy exiting...")
