from tavily import TavilyClient
from src.core.settings import settings

WEB = {"client": None}


def initialize_web_client():
    if not settings.TAVILY_API_KEY:
        raise RuntimeError(
            "TAVILY_API_KEY is not set -- add it to your .env to use the web tools."
        )

    WEB["client"] = TavilyClient(api_key=settings.TAVILY_API_KEY)


def _client() -> TavilyClient:
    if WEB["client"] is None:
        initialize_web_client()

    return WEB["client"]


def web_search(query: str):
    return _client().search(query)


def extract_web_pages(urls: list[str]):
    return _client().extract(urls=urls)


def crawl_web_pages(url: str, instructions: str):
    return _client().crawl(url=url, instructions=instructions)


def map_web_pages(url: str):
    return _client().map(url=url)


def web_research(topic: str):
    return _client().research(input=topic)
