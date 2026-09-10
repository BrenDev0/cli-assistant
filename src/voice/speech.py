import io
import wave

from openai import AsyncOpenAI

from src.core.settings import settings

from .audio import PLAYBACK_RATE, RECORD_RATE

TRANSCRIBE_MODEL = "gpt-4o-transcribe"
SPEAK_MODEL = "gpt-4o-mini-tts"
SPEAK_VOICE = "cedar" # echo, marin, cedar

MAX_SPEAK_CHARS = 4000

# a quarter second of audio per chunk: small enough that playback starts promptly,
# large enough that the next chunk is always there before the speakers run dry
CHUNK_BYTES = PLAYBACK_RATE // 2

SPEECH = {"client": None}


def _client() -> AsyncOpenAI:
    if SPEECH["client"] is None:
        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is not set -- add it to your .env to use voice mode."
            )

        SPEECH["client"] = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    return SPEECH["client"]


def _wav(pcm: bytes) -> io.BytesIO:
    buffer = io.BytesIO()
    # the API picks its decoder off the filename, and BytesIO has none of its own
    buffer.name = "speech.wav"

    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RECORD_RATE)
        out.writeframes(pcm)

    buffer.seek(0)
    return buffer


async def transcribe(pcm: bytes) -> str:
    result = await _client().audio.transcriptions.create(
        model=TRANSCRIBE_MODEL,
        file=_wav(pcm),
    )
    return result.text.strip()


async def synthesize(text: str):
    """Yields raw pcm as it arrives. Waiting for the whole file first cost about two
    seconds of silence before the reply started playing."""
    async with _client().audio.speech.with_streaming_response.create(
        model=SPEAK_MODEL,
        voice=SPEAK_VOICE,
        input=text[:MAX_SPEAK_CHARS],
        response_format="pcm",
    ) as response:
        async for chunk in response.iter_bytes(CHUNK_BYTES):
            yield chunk


async def warm() -> None:
    """The first request of a session pays dns and tls setup. Spending that here keeps
    it out of the first spoken turn."""
    client = _client()

    try:
        await client.models.list()
    except Exception:
        pass
