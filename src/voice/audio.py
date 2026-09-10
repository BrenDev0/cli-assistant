from collections import deque
from contextlib import contextmanager

import sounddevice as sd

RECORD_RATE = 16000
PLAYBACK_RATE = 24000

BLOCK_FRAMES = 1600
MAX_RECORD_SECONDS = 120
MAX_BLOCKS = MAX_RECORD_SECONDS * RECORD_RATE // BLOCK_FRAMES


@contextmanager
def recorder():
    """Captures the default mic for as long as the block runs, yielding raw int16 chunks.

    The mic is live from the moment the turn starts, so a user who walks away would
    otherwise hand Whisper an unbounded upload. The deque keeps only the most recent
    MAX_RECORD_SECONDS, which is the end of the recording -- the part they spoke.
    """
    chunks: deque[bytes] = deque(maxlen=MAX_BLOCKS)

    stream = sd.RawInputStream(
        samplerate=RECORD_RATE,
        channels=1,
        dtype="int16",
        blocksize=BLOCK_FRAMES,
        callback=lambda data, frames, time, status: chunks.append(bytes(data)),
    )

    with stream:
        yield chunks


@contextmanager
def player():
    stream = sd.RawOutputStream(samplerate=PLAYBACK_RATE, channels=1, dtype="int16")
    stream.start()

    try:
        yield stream
    finally:
        # stop() drains what is still queued -- abort() would cut off the last word
        stream.stop()
        stream.close()


def check() -> None:
    sd.check_input_settings(samplerate=RECORD_RATE, channels=1, dtype="int16")
    sd.check_output_settings(samplerate=PLAYBACK_RATE, channels=1, dtype="int16")
