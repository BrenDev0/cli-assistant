import asyncio
from pydantic import SecretStr
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from src.tools.executor import executor
from src.core.agents.types import Message
from src.core import frontend
from src.core.settings import settings

# Every model here must support tool calling through bind_tools -- this agent is a
# tool-calling loop and a model that cannot call tools cannot do anything in it. That rules
# out the base completion models (babbage-002, davinci-002, gpt-3.5-turbo-instruct), the
# search-preview variants, and the -pro tiers, which are served over the Responses API
# rather than the chat completions path ChatOpenAI uses here.
# Dated snapshots (gpt-5.4-2026-03-05 and friends) are deliberately left out; the bare
# alias tracks them, and pinning belongs in config, not in the menu.
PROVIDERS = {
    # newest tier -- three same-version variants, characteristics unverified here
    "gpt-5.6-luna": "openai",
    "gpt-5.6-sol": "openai",
    "gpt-5.6-terra": "openai",
    "gpt-5.5": "openai",
    "gpt-5.4": "openai",
    "gpt-5.4-mini": "openai",
    "gpt-5.4-nano": "openai",
    "gpt-5.3-chat-latest": "openai",
    "gpt-5.2": "openai",
    "gpt-5.2-chat-latest": "openai",
    "gpt-5.1": "openai",
    "gpt-5.1-chat-latest": "openai",
    "gpt-5": "openai",
    "gpt-5-chat-latest": "openai",
    "gpt-5-mini": "openai",
    "gpt-5-nano": "openai",
    "gpt-4.1": "openai",
    "gpt-4.1-mini": "openai",
    "gpt-4.1-nano": "openai",
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "o4-mini": "openai",
    "o3": "openai",
    "o3-mini": "openai",
    "o1": "openai",
    "claude-opus-5": "anthropic",
    "claude-sonnet-5": "anthropic",
    "claude-haiku-4-5-20251001": "anthropic",
}


ACCEPTS_TEMPERATURE = {
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-haiku-4-5-20251001",
}

CLIENTS = {"openai": ChatOpenAI, "anthropic": ChatAnthropic}

KEY_FIELDS = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}

AVAILABLE_MODELS = sorted(PROVIDERS)


def provider_for(model: str) -> str:
    if model not in PROVIDERS:
        raise ValueError(
            f"Model '{model}' not available. Known models: {', '.join(AVAILABLE_MODELS)}"
        )
    return PROVIDERS[model]


def key_for(model: str) -> str:
    """The key is derived from the model, never passed in beside it -- otherwise an
    OpenAI key follows a switch to an Anthropic model and fails as a 401."""
    provider = provider_for(model)
    field = KEY_FIELDS[provider]
    key = getattr(settings, field, "")
    if not key:
        raise ValueError(f"{field} is not set -- required for {provider} model '{model}'.")
    return key


class LangchainAgent:
    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        temperature: float = 0.0,
        tools: list | None = None,
        max_iterations: int = 10
    ):
        self._max_iterations = max_iterations
        self._model = model
        self._api_key = SecretStr(api_key or key_for(model))
        self._tools = tools
        self._temperature = temperature
        self.llm = self._get_model()

    def _get_model(self):
        client = CLIENTS[provider_for(self._model)]

        kwargs = {"model_name": self._model, "api_key": self._api_key}
        if self._model in ACCEPTS_TEMPERATURE:
            kwargs["temperature"] = self._temperature

        llm = client(**kwargs)

        if self._tools:
            llm = llm.bind_tools(self._tools)

        return llm


    async def invoke(self, messages: list[Message]) -> str:
        tokens_used = 0
        for _ in range(self._max_iterations):
            result = await self.llm.ainvoke(messages)
            usage = getattr(result, "usage_metadata", None) or {}
            tokens_used += usage.get("total_tokens", 0)
            if not result.tool_calls:
                content = result.content.strip() if result.content else ""
                messages.append(("assistant", content))
                frontend.tokens(tokens_used)
                tokens_used = 0
                return content

            messages.append(result)
            messages = await self._append_tool_results(tool_calls=result.tool_calls, messages=messages)

        raise RuntimeError(f"max iterations ({self._max_iterations}) reached in invoke loop")


    async def _append_tool_results(self, tool_calls: list[dict], messages: list[Message]) -> list[Message]:
        async def run_tool(tool_call: dict):
            try:
                result = await executor(tool_name=tool_call["name"], params=tool_call["args"])
            except Exception as e:
                result = f"Error running tool '{tool_call['name']}': {e}"
            return tool_call["id"], result

        tool_results = await asyncio.gather(*(run_tool(call) for call in tool_calls))

        for id, rslt in tool_results:
            messages.append(
                {
                    "role": "tool",
                    "content": str(rslt),
                    "tool_call_id": id
                }
            )

        return messages