import asyncio
from pydantic import SecretStr
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from ..tools import executor

AVAILABLE_MODELS = {
    "openai": ["gpt-5-pro", "gpt-4o", "gpt-3.5-turbo"],
    "anthropic": ["claude-opus-4-6", "claude-sonnet-5"]
}

class LangchainAssistant:
    def __init__(
        self, 
        model: str, 
        api_key: str, 
        temperature: float = 0.0,
        tools: list | None = None
    ):
        self._model = model
        self._api_key = SecretStr(api_key)
        self._tools = tools
        self._temperature = temperature
        self.llm = self._get_model()    

    def _get_model(self):
        if self._model in AVAILABLE_MODELS["openai"]:
            llm = ChatOpenAI(
                model_name=self._model,
                api_key=self._api_key,
                temperature=self._temperature
            )

            if self._tools:
                llm = llm.bind_tools(self._tools)

            return llm

        if self._model in AVAILABLE_MODELS["anthropic"]:
            llm = ChatAnthropic(
                model_name=self._model,
                api_key=self._api_key,
                temperature=self._temperature
            )

            if self._tools:
                llm = llm.bind_tools(self._tools)

            return llm

        else: 
            raise ValueError(f"Model {self._model} not available")


    async def invoke(self, messages: list[tuple]):
        for _ in range(10):
            result = await self.llm.ainvoke(messages)
            if not result.tool_calls:
                content = result.content.strip() if result.content else ""
                messages.append(("assistant", content))
                return content

            messages.append(result)
            messages = await self._append_tool_results(tool_calls=result.tool_calls, messages=messages)

        raise RuntimeError("max iterations in invoke loop reached")


    async def _append_tool_results(self, tool_calls: list[dict], messages: list[tuple]):
        async def run_tool(tool_call: dict):
            result = await executor(tool_name=tool_call["name"], params=tool_call["args"])
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







        
