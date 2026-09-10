import asyncio
import re

from . import audio, speech
from .speech import transcribe

STATE = {"on": False}

MIN_RECORD_BYTES = 8000

# ten seconds of audio held ahead of the speakers. Synthesising a sentence only once the
# previous one had finished playing left three second silences between them.
PREFETCH_CHUNKS = 40

# the lookahead is what keeps "3.5" and "v1.2" from being spoken as two sentences: a
# terminator only ends one when whitespace actually follows it
SENTENCE_END = re.compile(r"[^.!?\n]*[.!?\n]+(?=\s)")


def is_on() -> bool:
    return STATE["on"]


async def toggle() -> bool:
    if not STATE["on"]:
        audio.check()
        await speech.warm()

    STATE["on"] = not STATE["on"]
    return STATE["on"]


async def listen(read) -> tuple[str | None, bool]:
    """Records until the next line is submitted. Anything typed wins and the audio is
    dropped, which is what keeps /voice and the other commands reachable without a mouse.

    Returns the text and whether it was spoken, or (None, False) when the reader reports
    that the user is leaving. The caller does the echoing: the box holds the typed line
    only until it is submitted, so a transcript has nothing on screen to stand for it.
    """
    with audio.recorder() as chunks:
        submitted = await read()

    if submitted is None:
        return None, False

    typed = submitted.strip()
    if typed:
        return typed, False

    pcm = b"".join(chunks)
    if len(pcm) < MIN_RECORD_BYTES:
        return "", False

    return await transcribe(pcm), True


class Speaker:
    """Speaks a reply while the model is still writing it. Sentences are queued as they
    complete, so the first one is already playing by the time the last one arrives."""

    def __init__(self):
        self._sentences: asyncio.Queue[str | None] = asyncio.Queue()
        self._pcm: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=PREFETCH_CHUNKS)
        self._pending = ""
        self._tasks = (
            asyncio.create_task(self._synthesize()),
            asyncio.create_task(self._play()),
        )

    def feed(self, text: str) -> None:
        self._pending += text

        # only the end of the last match is trustworthy: the pattern can start matching
        # partway through the buffer, so taking the matches themselves reorders the reply
        cut = max((match.end() for match in SENTENCE_END.finditer(self._pending)), default=0)
        if not cut:
            return

        ready, self._pending = self._pending[:cut].strip(), self._pending[cut:]

        if ready:
            self._sentences.put_nowait(ready)

    async def finish(self) -> None:
        if self._pending.strip():
            self._sentences.put_nowait(self._pending.strip())

        self._sentences.put_nowait(None)
        await asyncio.gather(*self._tasks)

    async def _synthesize(self) -> None:
        try:
            while (sentence := await self._sentences.get()) is not None:
                async for chunk in speech.synthesize(sentence):
                    await self._pcm.put(chunk)
        finally:
            # the player is waiting on this even if synthesis just died
            await self._pcm.put(None)

    async def _play(self) -> None:
        with audio.player() as player:
            while (chunk := await self._pcm.get()) is not None:
                await asyncio.to_thread(player.write, chunk)
