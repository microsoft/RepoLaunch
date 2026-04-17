"""
LLM provider abstraction backed by LiteLLM.
"""
import os
from functools import wraps
from typing import Any, List

import litellm
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

# Silence LiteLLM provider-debug prints (e.g. repeated "Provider List" lines).
litellm.suppress_debug_info = True
litellm.turn_off_message_logging = True


def logged_invoke(invoke_func):
    """
    Decorator to log LLM interactions to files.
    
    Args:
        invoke_func: LLM invoke function to wrap
        
    Returns:
        Wrapped function that logs inputs and outputs
    """
    @wraps(invoke_func)
    def wrapper(self, messages: List[BaseMessage]) -> BaseMessage:  

        def _extract_usage_and_cost(message: BaseMessage) -> tuple[int | None, int | None, float | None]:
            usage_metadata = getattr(message, "usage_metadata", None) or {}
            response_metadata = getattr(message, "response_metadata", None) or {}

            input_tokens = usage_metadata.get("input_tokens")
            output_tokens = usage_metadata.get("output_tokens")
            cost = response_metadata.get("cost")

            token_usage = response_metadata.get("token_usage", {})
            if input_tokens is None:
                input_tokens = token_usage.get("prompt_tokens")
            if output_tokens is None:
                output_tokens = token_usage.get("completion_tokens")

            return input_tokens, output_tokens, cost


        if self.log_folder is None:
            response: BaseMessage = invoke_func(self, messages)
            return response
        
        log_folder = self.log_folder  # Dynamically get the log folder from the instance
        os.makedirs(log_folder, exist_ok=True)

        try:
            existing_files = [
                f for f in os.listdir(log_folder) if f.split(".")[0].isdigit()
            ]
            existing_numbers = [int(name.split(".")[0]) for name in existing_files]
            next_number = max(existing_numbers) + 1 if existing_numbers else 0
        except (OSError, ValueError):
            next_number = 0
        log_file_path = os.path.join(log_folder, f"{next_number}.md")

        response: BaseMessage = invoke_func(self, messages)
        input_tokens, output_tokens, cost = _extract_usage_and_cost(response)

        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write("##### LLM INPUT #####\n")
            f.write("\n".join([m.pretty_repr() for m in messages]))
            f.write("\n##### LLM OUTPUT #####\n")
            f.write(response.pretty_repr())
            f.write("\n\n##### LLM METRICS #####\n")
            f.write(f"- Input tokens: {input_tokens if input_tokens is not None else 'N/A'}\n")
            f.write(f"- Output tokens: {output_tokens if output_tokens is not None else 'N/A'}\n")
            f.write(f"- Cost (USD): ${cost:.8f}\n" if cost is not None else "- Cost (USD): N/A\n")
        return response
    return wrapper


class LLMProvider:
    """
    Unified LLM interface with logging and retry, using ``litellm.responses``.
    """

    def __init__(self, log_folder: str | None = "./llm_logs", **kwargs):
        """
        Initialize LLM provider.

        Args:
            log_folder (str | None): Directory for interaction logs, None disables logging.
            **kwargs: Arbitrary LiteLLM arguments passed to
                ``litellm.responses(input=messages, **kwargs)``.
        """
        self.log_folder = log_folder
        self.model_config = kwargs
        self.llm_instance = LiteLLMModel(**kwargs)

    @logged_invoke
    @retry(
        stop=stop_after_attempt(8),
        wait=wait_exponential_jitter(initial=20, max=120, jitter=3)
    )
    def invoke(self, messages: List[BaseMessage]) -> BaseMessage:
        """
        Invoke the LLM with messages, includes automatic retry and logging.
        
        Args:
            messages (List[BaseMessage]): List of conversation messages
            
        Returns:
            BaseMessage: LLM response message
        """
        return self.llm_instance.invoke(messages)


class LiteLLMModel:
    """LiteLLM model implementation."""

    def __init__(self, **kwargs):
        self.completion_args = kwargs

    def _to_litellm_message(self, message: BaseMessage) -> dict[str, Any]:
        role = "user"
        name = getattr(message, "name", None)
        tool_call_id = getattr(message, "tool_call_id", None)

        msg_type = getattr(message, "type", "")
        if msg_type == "system":
            role = "system"
        elif msg_type == "ai":
            role = "assistant"
        elif msg_type == "tool":
            role = "tool"

        payload: dict[str, Any] = {"role": role, "content": message.content}
        if name:
            payload["name"] = name
        if tool_call_id:
            payload["tool_call_id"] = tool_call_id

        if role == "assistant":
            tool_calls = getattr(message, "tool_calls", None)
            if tool_calls:
                payload["tool_calls"] = tool_calls
        return payload

    def _safe_completion_cost(self, response: Any, model: str | None = None) -> float:
        try:
            return float(litellm.completion_cost(completion_response=response, model=model))
        except Exception:
            return 0.0
    
    def invoke(self, messages: List[BaseMessage]) -> BaseMessage:
        payload = [self._to_litellm_message(message) for message in messages]
        from cloudgpt_aoai import get_openai_token_provider
        token_provider = get_openai_token_provider()
        response = litellm.responses(
            input=payload,
            api_base="https://cloudgpt-openai.azure-api.net/",
            api_version="2025-04-01-preview",
            azure_ad_token_provider=token_provider,
            **self.completion_args
        )

        # Extract text from responses API output
        content = ""
        for output_item in getattr(response, "output", []):
            if getattr(output_item, "type", None) == "message":
                for block in getattr(output_item, "content", []):
                    if getattr(block, "type", None) == "output_text":
                        content += block.text

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)
        cost = getattr(usage, "cost", None)

        return AIMessage(
            content=content,
            usage_metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            },
            response_metadata={
                "model": getattr(response, "model", self.completion_args.get("model")),
                "token_usage": {
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": total_tokens,
                },
                "cost": cost,
            },
        )

if __name__ == "__main__":
    model_config = {
        "model": "azure/gpt-4o",
        "temperature": 0.0,
    }
    llm = LLMProvider(log_folder="./llm_logs", **model_config)
    messages = [HumanMessage(content="What is the capital of France?")]
    res = llm.invoke(messages)
    print(res)