from pydantic import BaseModel, Field


class OpenBrowserPage(BaseModel):
    """Open a URL in the user's own Chrome window and return the page's visible text.

    The window is real and visible, running a profile that keeps its signed-in sessions
    between runs, so anything the user is logged into stays logged in. Use this when a
    task needs a site the user is authenticated on -- WebSearch and ExtractWebPages are
    better for public pages, being far faster and needing no browser.
    """
    url: str = Field(description="Full URL including scheme, for example 'https://web.whatsapp.com'")


class ReadBrowserPage(BaseModel):
    """Re-read the visible text of the page already open in the browser.

    Use after clicking or typing to see what changed, rather than opening the URL again.
    """


class ClickBrowserElement(BaseModel):
    """Click the first button or link whose visible text contains what you give.

    Needs the user's approval. Matched on visible label rather than a CSS selector, so
    the approval prompt shows them the same words they would see on the page.
    """
    text: str = Field(description="Visible text on the button or link, for example 'Continue' or 'Add to cart'")


class TypeInBrowser(BaseModel):
    """Type into whichever field on the page currently has focus.

    Needs the user's approval. Click the field first if it is not already focused.
    """
    text: str = Field(description="The text to type")
    then_enter: bool = Field(default=False, description="Press enter afterwards, for a search box or a message field")


class FindWhatsappChat(BaseModel):
    """Look up who a name matches in the user's WhatsApp before sending anything.

    Call this first whenever the user names a person rather than giving a number. It
    returns the matching chat names exactly as WhatsApp has them, which is what
    SendWhatsappMessage needs.

    When it resolves to a single chat, go straight on and send -- do not ask the user to
    confirm the contact first. They approve the send itself, with the resolved chat name
    and the full message in front of them, so asking beforehand only makes them say yes
    twice. Ask only when it genuinely comes back with several.
    """
    name: str = Field(description="The person as the user referred to them, for example 'John Doe'")


class SendWhatsappMessage(BaseModel):
    """Send one WhatsApp message to one person through WhatsApp Web.

    Needs the user's approval, and refuses to run inside a background task: a sent
    message cannot be recalled, so it never happens with nobody at the keyboard.

    This is the WhatsApp account signed into the browser, which is a different sender
    from the CRM's WhatsApp channel. GoHighLevel sends over the WhatsApp Business API,
    which only allows a free-form message inside 24 hours of the contact's own last
    message and requires an approved template outside that window. This tool has no such
    limit, so it is the route for a first approach or a conversation that has gone cold
    -- but the message arrives from the browser's number, not the CRM's, so say which
    you are using if there is any doubt.

    `to` is either a phone number, or a chat name exactly as FindWhatsappChat returned
    it -- do not guess a name, because a near miss is a message to the wrong person.
    Looking the number up among the user's CRM contacts is a good way to get one; that
    is reading contact data, and is unrelated to which channel sends.

    The first use asks the user to scan a QR code in the browser window; after that the
    session persists. Send one message per call -- to message several people, confirm
    the list with the user and then call this once each, so every message is approved
    on its own and a mistake stops at one.
    """
    to: str = Field(description="A phone number in full international form ('521234567890'), or an exact chat name from FindWhatsappChat")
    message: str = Field(description="The message text, exactly as it should be sent")


class CloseBrowser(BaseModel):
    """Close the browser window. The signed-in sessions are kept for next time."""


class ListBrowserTabs(BaseModel):
    """List every tab open in the browser, with its title and URL.

    Check this before opening a page the user is likely to already have open and signed
    into. Reusing that tab is faster than loading the site again, and on a site that has
    to be logged into it is the difference between working and being shown a login page.
    """


class SwitchBrowserTab(BaseModel):
    """Switch to the first open tab whose title or URL contains what you give, and read it.

    Use after ListBrowserTabs to work in a tab that is already signed in.
    """
    match: str = Field(description="Part of the tab's title or URL, for example 'whatsapp' or 'gmail'")


class ReadWhatsappChat(BaseModel):
    """Open a WhatsApp conversation and read its recent messages.

    Each line is marked with who sent it, so "the last thing I sent them" is answerable
    without guessing. Use this rather than clicking the chat list by hand: it opens the
    conversation the same careful way sending does, checking the header matches before
    reading anything.
    """
    name: str = Field(description="The chat name, ideally exactly as FindWhatsappChat returned it")
    limit: int = Field(default=15, description="How many of the most recent messages to return")
