from typing import Protocol

class Assistant(Protocol):
    async def invoke(): ...