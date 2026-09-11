import re
import socket
import time
import subprocess
import threading
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as present
from selenium.webdriver.support.ui import WebDriverWait

from src.core.context import CURRENT_TASK
from src.core.settings import settings
from src.core.workspace import browser_dir

BROWSER = {"driver": None}

# Selenium is not thread safe and the executor runs tool calls concurrently, so two
# calls in one turn could otherwise interleave halfway through a page interaction.
_LOCK = threading.Lock()

# what Chrome uses when it is started with --remote-debugging-port and no number
DEFAULT_DEBUG_PORT = 9222

PAGE_TIMEOUT = 20
WHATSAPP_TIMEOUT = 60
MAX_TEXT = 6000

# WhatsApp filters the chat list as you type; this is how long that takes to settle
SEARCH_SETTLE = 2.0

# a conversation renders after its composer does
MESSAGES_TIMEOUT = 15

# a thread keeps filling in after its first bubble lands
BUBBLE_SETTLE = 1.5

UNSUPERVISED = (
    "Refused: {action} needs someone at the keyboard to approve it, and a background "
    "task runs with nobody there. Tell the user what you wanted to do and let them run "
    "it in the conversation instead."
)

# Read off a signed-in WhatsApp Web rather than assumed. Each list is tried in order,
# so one stale selector degrades to the next instead of to a crash.
#
# The lesson from getting these wrong twice: nothing may key off an English label. The
# search box is found by being the one text input in the sidebar, not by its aria-label,
# which on this account reads "Buscar un chat o iniciar uno nuevo".
WHATSAPP_SEARCH = (
    '#side input[type="text"]',
    'input[type="text"]',
)
WHATSAPP_ROWS = (
    "#pane-side [role='row']",
)
# only exists once a chat is open, which is why the chat list shows no editable box
WHATSAPP_INPUT = (
    '#main div[contenteditable="true"][data-tab="10"]',
    '#main [role="textbox"]',
    'footer div[contenteditable="true"]',
)
WHATSAPP_SEND = (
    'button[data-tab="11"]',
    'span[data-icon="send"]',
    'footer button[aria-label]',
)
WHATSAPP_QR = (
    "canvas[aria-label*='Scan']",
    "canvas[aria-label*='Escanea']",
    "div[data-ref]",
)
# every bubble carries "[time, date] Sender: ", which is both the timestamp and who
# wrote it -- more useful than guessing direction from a class that no longer exists
WHATSAPP_MESSAGES = (
    "#main [data-pre-plain-text]",
)
SENDER = re.compile(r"^\[[^\]]*\]\s*(.+?):\s*$")

WHATSAPP_INVALID = "div[data-animate-modal-body='true']"


def _driver():
    """The browser to work in: the user's own Chrome when they have made it reachable,
    otherwise one of ours.

    Attaching is better whenever it is available -- their Chrome already holds every
    session they are signed into, so WhatsApp Web needs no QR scan and neither does
    anything else. It is opt-in because Chrome only accepts a debugger connection if it
    was started with --remote-debugging-port, which is not how anyone opens a browser
    by habit. Without it we fall back to a profile of our own, which has to be signed
    into once but then persists.
    """
    if BROWSER["driver"] is not None:
        try:
            # a cheap round trip: the window may have been closed by hand since the
            # last call, and a dead driver fails every later tool with a stack trace
            BROWSER["driver"].current_url
            return BROWSER["driver"]
        except Exception:
            # not just WebDriverException: when chromedriver itself is gone the failure
            # surfaces from the http layer underneath it as a connection error
            BROWSER["driver"] = None

    options = Options()

    port = settings.CHROME_DEBUG_PORT.strip() or _debuggable_port()
    if port:
        # and nothing else: the launch-time options below are rejected outright when
        # attaching, because the browser they would have configured is already running
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    else:
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        profile = browser_dir()
        profile.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile}")
        options.add_argument("--profile-directory=Default")
        # not headless on purpose: a first sign-in needs a QR code or a password typed,
        # and the user should be able to see what is being done on their behalf

    try:
        BROWSER["driver"] = webdriver.Chrome(options=options)
    except WebDriverException as exc:
        if port:
            raise RuntimeError(
                f"Could not attach to Chrome on port {port}: {exc}. Start Chrome with "
                f"--remote-debugging-port={port}, or clear CHROME_DEBUG_PORT to let the "
                f"tools open their own window."
            ) from exc

        raise RuntimeError(
            f"Could not start Chrome: {exc}. If a Chrome is already open on this "
            f"profile, close it -- Chrome will not share a profile directory."
        ) from exc

    BROWSER["driver"].set_page_load_timeout(PAGE_TIMEOUT)
    return BROWSER["driver"]


CHROME_PATHS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)


def _chrome_exe() -> str | None:
    from pathlib import Path

    for candidate in CHROME_PATHS:
        if Path(candidate).is_file():
            return candidate

    return None


def _chrome_running() -> bool:
    try:
        listed = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    return "chrome.exe" in listed.stdout.lower()


def browser_status() -> str:
    """Whether the user's own Chrome can be driven, and what to do when it cannot."""
    port = settings.CHROME_DEBUG_PORT.strip() or str(DEFAULT_DEBUG_PORT)

    if _debuggable_port() or (settings.CHROME_DEBUG_PORT.strip() and _port_open(int(port))):
        return f"attached: a Chrome is listening on {port}, so your own tabs and logins are usable"

    if _chrome_running():
        return (
            f"Chrome is open but not reachable. It only accepts automation when it was "
            f"started with --remote-debugging-port={port}, and adding the flag to a "
            f"Chrome that is already running does nothing. Close Chrome completely, then "
            f"run /browser again and it will be started for you."
        )

    exe = _chrome_exe()
    if exe is None:
        return "Chrome is not installed where expected; set CHROME_DEBUG_PORT and start it yourself."

    subprocess.Popen([exe, f"--remote-debugging-port={port}"])
    return (
        f"started your Chrome with automation enabled on port {port}. Your normal "
        f"profile, so everything you are signed into is there."
    )


def _port_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.3)
        try:
            probe.connect(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _debuggable_port() -> str:
    """The default debug port if a Chrome is listening on it, otherwise nothing.

    Probed rather than configured so that starting Chrome with the flag is the whole
    setup: there is no way to discover a browser that is not listening, but there is no
    reason to make someone also name the port when it is the standard one.
    """
    return str(DEFAULT_DEBUG_PORT) if _port_open(DEFAULT_DEBUG_PORT) else ""


def _tabs(driver) -> list[tuple[str, str, str]]:
    """Every open tab as (handle, title, url), leaving the active tab as it was."""
    was = driver.current_window_handle
    found = []

    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        found.append((handle, driver.title, driver.current_url))

    driver.switch_to.window(was)
    return found


def _focus(driver, fragment: str) -> str | None:
    """Switch to the first tab whose title or url contains the fragment."""
    wanted = fragment.lower()

    for handle, title, url in _tabs(driver):
        if wanted in title.lower() or wanted in url.lower():
            driver.switch_to.window(handle)
            return url

    return None


def _first(driver, selectors, timeout: int):
    """The first of several selectors to appear, so one stale selector is survivable."""
    end = WebDriverWait(driver, timeout, poll_frequency=0.5)
    for index, selector in enumerate(selectors):
        try:
            remaining = 2 if index < len(selectors) - 1 else timeout
            return WebDriverWait(driver, remaining, poll_frequency=0.3).until(
                present.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
        except TimeoutException:
            continue

    del end
    return None


def _visible(driver, selectors) -> bool:
    for selector in selectors:
        if driver.find_elements(By.CSS_SELECTOR, selector):
            return True
    return False


def _text(driver) -> str:
    body = driver.find_element(By.TAG_NAME, "body").text
    collapsed = re.sub(r"\n{3,}", "\n\n", body).strip()
    if len(collapsed) <= MAX_TEXT:
        return collapsed

    return collapsed[:MAX_TEXT] + f"\n\n[page truncated at {MAX_TEXT:,} characters]"


BLANK = ("about:blank", "chrome://newtab/", "chrome://new-tab-page/", "data:,")


def open_browser_page(url: str) -> str:
    """Opens in a new tab unless the current one is blank.

    Attached to the user's own Chrome, the current tab holds something they were
    reading. Navigating it away to run an errand loses their place, and it was not
    ours to spend.
    """
    with _LOCK:
        driver = _driver()

        if driver.current_url not in BLANK:
            driver.switch_to.new_window("tab")

        driver.get(url)
        return f"{driver.title}{chr(10)}{driver.current_url}{chr(10)}{chr(10)}{_text(driver)}"


def read_browser_page() -> str:
    with _LOCK:
        driver = BROWSER["driver"]
        if driver is None:
            return "No browser is open. Call OpenBrowserPage first."

        return f"{driver.title}\n{driver.current_url}\n\n{_text(driver)}"


ROLES = ("button", "link", "listitem", "row", "gridcell", "option", "menuitem", "tab")


def _clickable(driver, text: str):
    """Anything carrying the text that a person could click.

    Buttons and links alone were too narrow: WhatsApp's chat list is rows of
    div[role="listitem"], so asking to click a conversation matched nothing and came
    back looking like the page had not loaded.
    """
    wanted = text.replace('"', "")
    roles = " or ".join(f'@role="{role}"' for role in ROLES)

    matches = driver.find_elements(
        By.XPATH,
        f'//*[self::button or self::a or {roles} or @title]'
        f'[contains(normalize-space(.), "{wanted}")]',
    )

    # innermost first: an ancestor also "contains" the text, and clicking the whole
    # list when one row was meant is how the wrong conversation gets opened
    return sorted(matches, key=lambda el: len(el.text or ""))


def _click(driver, element) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    try:
        element.click()
    except WebDriverException:
        # an overlay or an animation can intercept the real click; the DOM one still lands
        driver.execute_script("arguments[0].click();", element)


def click_browser_element(text: str) -> str:
    if CURRENT_TASK.get():
        return UNSUPERVISED.format(action="clicking in the browser")

    with _LOCK:
        driver = BROWSER["driver"]
        if driver is None:
            return "No browser is open. Call OpenBrowserPage first."

        # matched on the visible label rather than a selector: it is what the user can
        # confirm from the approval prompt, and what survives a class name changing
        matches = _clickable(driver, text)
        if not matches:
            return f"Nothing on the page carries the text '{text}'."

        _click(driver, matches[0])
        return f"Clicked '{text}'. Now at {driver.current_url}"


def type_in_browser(text: str, then_enter: bool = False) -> str:
    if CURRENT_TASK.get():
        return UNSUPERVISED.format(action="typing in the browser")

    with _LOCK:
        driver = BROWSER["driver"]
        if driver is None:
            return "No browser is open. Call OpenBrowserPage first."

        target = driver.switch_to.active_element
        target.send_keys(text)
        if then_enter:
            target.send_keys(Keys.ENTER)

        return f"Typed {len(text)} characters{' and pressed enter' if then_enter else ''}."


def list_browser_tabs() -> str:
    """What is already open, so a task can reuse a signed-in tab instead of loading it."""
    with _LOCK:
        driver = BROWSER["driver"]
        if driver is None and (settings.CHROME_DEBUG_PORT.strip() or _debuggable_port()):
            # a reachable Chrome is worth attaching to just to look; without one, saying
            # so beats opening a window nobody asked for
            driver = _driver()

        if driver is None:
            return "No browser is open yet. Call OpenBrowserPage to start one."

        rows = [f"{index}. {title or '(untitled)'} -- {url}"
                for index, (_, title, url) in enumerate(_tabs(driver), start=1)]
        return f"{len(rows)} tab(s) open:{chr(10)}" + chr(10).join(rows)


def switch_browser_tab(match: str) -> str:
    with _LOCK:
        driver = BROWSER["driver"]
        if driver is None:
            return "No browser is open. Call OpenBrowserPage first."

        url = _focus(driver, match)
        if url is None:
            return f"No open tab has '{match}' in its title or url. Call ListBrowserTabs."

        return f"Switched to {url}{chr(10)}{chr(10)}{_text(driver)}"


def close_browser() -> str:
    with _LOCK:
        driver = BROWSER["driver"]
        if driver is None:
            return "No browser was open."

        driver.quit()
        BROWSER["driver"] = None
        return "Browser closed. The signed-in session is kept for next time."


def _open_whatsapp(driver):
    """WhatsApp Web, ready to use. Returns None when it is, or a line to hand back."""
    if _focus(driver, "web.whatsapp.com") is None:
        driver.get("https://web.whatsapp.com")

    if _first(driver, WHATSAPP_SEARCH, WHATSAPP_TIMEOUT) is not None:
        return None

    if _visible(driver, WHATSAPP_QR):
        return (
            "WhatsApp Web is not signed in. A QR code is on screen in the browser "
            "window -- ask the user to scan it from their phone, then try again."
        )

    return (
        f"WhatsApp Web did not finish loading within {WHATSAPP_TIMEOUT}s, or it changed "
        f"its markup and the selectors in src/tools/browser/tools.py need updating."
    )


CHAT_NAMES_JS = """
const rows = document.querySelectorAll(arguments[0]);
const out = [];
for (const row of rows) {
  const label = row.querySelector('span[title]');
  if (label) out.push(label.getAttribute('title'));
}
return out;
"""


def _search_chats(driver, name: str) -> list[str]:
    """Chat names matching a search, read off the list WhatsApp filters down.

    Collected in a single script rather than element by element: the list is
    virtualised, so rows are recycled as it filters and half the handles from a Python
    loop go stale before it reaches them.
    """
    box = _first(driver, WHATSAPP_SEARCH, 15)
    if box is None:
        return []

    box.click()
    box.send_keys(Keys.CONTROL, "a")
    box.send_keys(name)
    time.sleep(SEARCH_SETTLE)

    names = []
    for selector in WHATSAPP_ROWS:
        for found in driver.execute_script(CHAT_NAMES_JS, selector) or []:
            clean = (found or "").strip()
            if clean and clean not in names:
                names.append(clean)
        if names:
            break

    return names


def _open_chat(driver, name: str) -> bool:
    """Click the chat whose name matches exactly, then confirm the right one opened.

    Confirmed against the composer, not the header: this build leaves header span[title]
    empty, while the message box is labelled "Escribir un mensaje para <name>". The name
    is in it whatever the interface language, which is the part that has to be checked --
    the list reorders while it filters, so clicking by position can land on a neighbour.
    """
    clicked = False
    for _ in range(2):
        for selector in WHATSAPP_ROWS:
            for row in driver.find_elements(By.CSS_SELECTOR, selector):
                try:
                    titles = row.find_elements(By.CSS_SELECTOR, "span[title]")
                    if titles and (titles[0].get_attribute("title") or "").strip() == name:
                        _click(driver, titles[0])
                        clicked = True
                        break
                except StaleElementReferenceException:
                    # recycled underneath us; the outer retry re-reads the list
                    continue
            if clicked:
                break
        if clicked:
            break

    if not clicked:
        return False

    box = _first(driver, WHATSAPP_INPUT, 15)
    if box is None:
        return False

    label = box.get_attribute("aria-label") or ""
    return name.lower() in label.lower()


def _rank(found: list[str], name: str) -> tuple[list[str], list[str]]:
    """Split matches into the ones named that, and the rest.

    WhatsApp searches message bodies as well as chat names, so asking for one person
    comes back with every group that has ever mentioned them. A chat actually called
    what was asked for is not a candidate among those -- it is the answer.
    """
    wanted = name.strip().lower()
    exact = [row for row in found if row.strip().lower() == wanted]
    partial = [row for row in found if wanted in row.strip().lower() and row not in exact]
    return exact, partial


def find_whatsapp_chat(name: str) -> str:
    """Who WhatsApp thinks that name is, before anything is sent to them."""
    with _LOCK:
        driver = _driver()

        problem = _open_whatsapp(driver)
        if problem:
            return problem

        found = _search_chats(driver, name)
        if not found:
            return (
                f"No WhatsApp chat matches '{name}'. The name has to be as it appears in "
                f"the user's WhatsApp. If they are not a saved contact, ask the user for "
                f"the phone number instead."
            )

        exact, partial = _rank(found, name)

        # neither of these tells the caller to check with the user: the approval
        # prompt already shows them the resolved chat and the exact message, so asking
        # in the reply first is a second, worse confirmation of the same thing
        if len(exact) == 1:
            return f"'{exact[0]}' is a chat by that exact name. Send to it directly."

        if not exact and len(partial) == 1:
            return (
                f"No chat is named exactly '{name}'; the one close match is "
                f"'{partial[0]}'. Send to that name."
            )

        candidates = exact + partial or found
        listed = chr(10).join(f"- {row}" for row in candidates)
        note = "" if (exact or partial) else (
            f"{chr(10)}None of these is named '{name}' -- they matched on message "
            f"content, which WhatsApp searches too."
        )
        return (
            f"{len(candidates)} chat(s) match '{name}':{chr(10)}{listed}{note}{chr(10)}"
            f"{chr(10)}Ask the user which one, then pass that name exactly."
        )


MESSAGES_JS = """
const nodes = document.querySelectorAll(arguments[0]);
const out = [];
for (const node of nodes) {
  out.push([node.getAttribute('data-pre-plain-text'), node.innerText]);
}
return out;
"""


def read_whatsapp_chat(name: str, limit: int = 15) -> str:
    """Open a conversation and read its recent messages, each marked with who wrote it.

    Reading is not gated: nothing leaves the machine. It is still the same careful open
    as sending -- exact name preferred, and the chat confirmed once it is up -- because
    reading the wrong person's conversation is its own kind of wrong.
    """
    with _LOCK:
        driver = _driver()

        problem = _open_whatsapp(driver)
        if problem:
            return problem

        found = _search_chats(driver, name)
        if not found:
            return (
                f"No WhatsApp chat matches '{name}'. Call FindWhatsappChat to see what "
                f"is there."
            )

        exact, partial = _rank(found, name)
        chosen = exact[0] if exact else (partial[0] if len(partial) == 1 else None)
        if chosen is None:
            listed = ", ".join(partial or found)
            return (
                f"'{name}' matches more than one chat: {listed}. Ask the user which "
                f"one, then pass that name exactly."
            )

        if not _open_chat(driver, chosen):
            return f"Could not open the chat with '{chosen}', so nothing was read."

        # the composer appears before the conversation does, so opening a chat and
        # reading straight away finds an empty thread that fills a moment later
        bubbles = []
        deadline = time.monotonic() + MESSAGES_TIMEOUT
        while time.monotonic() < deadline and not bubbles:
            for selector in WHATSAPP_MESSAGES:
                bubbles = driver.execute_script(MESSAGES_JS, selector) or []
                if bubbles:
                    break
            if not bubbles:
                time.sleep(0.5)

        # the first bubble to render is rarely the whole thread, so once something is
        # there, give the rest a beat and take whichever read came back fuller
        if bubbles:
            time.sleep(BUBBLE_SETTLE)
            for selector in WHATSAPP_MESSAGES:
                more = driver.execute_script(MESSAGES_JS, selector) or []
                if len(more) > len(bubbles):
                    bubbles = more
                    break

        if not bubbles:
            return (
                f"The chat with '{chosen}' is open but no messages could be read from "
                f"it. WhatsApp Web may have changed its markup; the selectors are in "
                f"src/tools/browser/tools.py."
            )

        lines = []
        for pre, body in bubbles[-limit:]:
            match = SENDER.match((pre or "").strip())
            who = match.group(1) if match else chosen
            text = " ".join((body or "").split())
            if text:
                lines.append(f"{who}: {text}")

        if not lines:
            return f"The chat with '{chosen}' is open but the recent messages were empty."

        return f"Last {len(lines)} message(s) with {chosen}:{chr(10)}" + chr(10).join(lines)


def _looks_like_number(to: str) -> bool:
    return not re.search(r"[A-Za-z]", to) and len(re.sub(r"\D", "", to)) >= 8


def _digits(number: str) -> str:
    cleaned = re.sub(r"\D", "", number)
    if len(cleaned) < 8:
        raise ValueError(
            f"'{number}' is not a full phone number. WhatsApp needs it in international "
            f"form with the country code and no symbols, for example 521234567890."
        )
    return cleaned


def send_whatsapp_message(to: str, message: str) -> str:
    """One message to one chat, and only from the foreground.

    `to` is either a phone number or a chat name exactly as FindWhatsappChat returned
    it. A number goes through WhatsApp's own send?phone= URL, which needs no clicking
    and so cannot land on the wrong conversation. A name has to be picked out of the
    filtered chat list, so the open conversation's header is checked against the name
    before a single character is typed: the list reorders as it filters, and a message
    sent to the wrong person cannot be recalled.
    """
    if CURRENT_TASK.get():
        return UNSUPERVISED.format(action="sending a WhatsApp message")

    if _looks_like_number(to):
        return _send_to_number(_digits(to), message)

    return _send_to_chat(to, message)


def _send_to_number(number: str, message: str) -> str:
    with _LOCK:
        driver = _driver()

        # an already-open WhatsApp tab is reused rather than loaded again: the app takes
        # its time to boot, and a tab the user already has signed in is the fast path
        already = _focus(driver, "web.whatsapp.com") is not None
        driver.get(
            f"https://web.whatsapp.com/send?phone={number}&text={quote(message)}"
        )

        box = _first(driver, WHATSAPP_INPUT, 20 if already else WHATSAPP_TIMEOUT)
        if box is None:
            if _visible(driver, WHATSAPP_QR):
                return (
                    "WhatsApp Web is not signed in. A QR code is on screen in the "
                    "browser window -- ask the user to scan it from their phone, then "
                    "try again. The session is kept after that."
                )

            modal = driver.find_elements(By.CSS_SELECTOR, WHATSAPP_INVALID)
            if modal:
                return f"WhatsApp rejected the number {number}: {modal[0].text.strip()}"

            return (
                f"Could not find the WhatsApp message box within {WHATSAPP_TIMEOUT}s. "
                f"The page may still be loading, or WhatsApp Web changed its markup and "
                f"the selectors in src/tools/browser/tools.py need updating."
            )

        return _press_send(driver, box, message, number)


def _send_to_chat(name: str, message: str) -> str:
    with _LOCK:
        driver = _driver()

        problem = _open_whatsapp(driver)
        if problem:
            return problem

        found = _search_chats(driver, name)
        if not found:
            return (
                f"No WhatsApp chat matches '{name}'. Nothing was sent. Call "
                f"FindWhatsappChat to see what is there, or ask the user for a number."
            )

        exact, partial = _rank(found, name)
        if not exact:
            if len(partial) == 1:
                return (
                    f"No chat is named exactly '{name}'. The closest is '{partial[0]}' "
                    f"-- nothing was sent. Confirm that is the right person with the "
                    f"user, then send to that name."
                )

            listed = ", ".join(partial or found)
            return (
                f"'{name}' is not an exact chat name, so nothing was sent. Did you mean "
                f"one of these? {listed}. Pass one of them exactly as written."
            )

        if not _open_chat(driver, exact[0]):
            return (
                f"Opened a chat while looking for '{exact[0]}' but its header did not "
                f"match, so nothing was sent. Ask the user to open the conversation "
                f"themselves and try again."
            )

        box = _first(driver, WHATSAPP_INPUT, 15)
        if box is None:
            return (
                f"The chat with '{exact[0]}' is open but its message box could not be "
                f"found, so nothing was sent."
            )

        box.click()
        box.send_keys(message)
        return _press_send(driver, box, message, exact[0])


def _press_send(driver, box, message: str, recipient: str) -> str:
    send = _first(driver, WHATSAPP_SEND, 5)
    if send is not None:
        send.click()
    else:
        box.send_keys(Keys.ENTER)

    try:
        WebDriverWait(driver, 15).until(
            lambda d: message[:40] in d.find_element(By.TAG_NAME, "body").text
        )
    except TimeoutException:
        return (
            f"Pressed send to {recipient}, but the message did not appear in the "
            f"conversation. Ask the user to check the window before sending again."
        )

    return f"Sent to {recipient}: {message}"
