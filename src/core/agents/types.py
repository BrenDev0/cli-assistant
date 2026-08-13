from typing import Protocol

Message = tuple | dict

class Agent(Protocol):
    async def invoke(self, messages: list[Message]) -> str: ...