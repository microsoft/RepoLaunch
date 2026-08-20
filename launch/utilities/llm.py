"""
LLM provider abstraction backed by LiteLLM.
"""
import logging
import os
from functools import wraps
from typing import Any, List, Literal

import litellm
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger(__name__)

# Silence LiteLLM provider-debug prints (e.g. repeated "Provider List" lines).
litellm.suppress_debug_info = True
litellm.turn_off_message_logging = True

SYSTEM_PROMPT = """
You are a software engineer. You are interacting with a shell terminal. 
Do not write commands that will kill the current shell process; otherwise if the shell process is killed, the current dialogue will be ended forcefully. For example, do not use `exit $EXIT_CODE` or `set -e` in your generated command. You should use the specified way in the action instruction below to perform each action or submit your result. 
Also, the shell terminal is non-interactive -- do not write commands that will prompt user to input anything in the execution process. Any interactive command that requires user input during execution will be killed. You should write shell commands that can run without user input in the middle; for example, you should write a command like `apt-get install lsof -y` instead of `apt-get install lsof`. 
"""

def update_accumulative_cost(
        d: dict[Literal["input_tokens", "output_tokens", "cost_usd"], int|float],
        response: BaseMessage) -> None:
    '''edit in-place'''
    i: int = response.usage_metadata['input_tokens']
    o: int = response.usage_metadata['output_tokens']
    c: float = response.usage_metadata['cost']
    d["input_tokens"] += i
    d["output_tokens"] += o
    d["cost_usd"] += c
    return

def form_llm_cost_log(response: BaseMessage) -> str:
    i: int = response.usage_metadata['input_tokens']
    o: int = response.usage_metadata['output_tokens']
    c: float = response.usage_metadata['cost']
    return f" -- <step_cost> input tokens: {i}, output tokens: {o}, cost usd: {c} </step_cost>"

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

        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write("##### LLM INPUT #####\n")
            f.write("\n".join([m.pretty_repr() for m in messages]))
            f.write("\n##### LLM OUTPUT #####\n")
            f.write(response.pretty_repr())
            f.write("\n\n##### LLM METRICS #####\n")
            f.write(f"- Input tokens: {response.usage_metadata['input_tokens']}\n")
            f.write(f"- Output tokens: {response.usage_metadata['output_tokens']}\n")
            f.write(f"- Cost (USD): ${response.usage_metadata['cost']}\n")
        return response
    return wrapper


class LLMProvider:
    """
    Unified LLM interface with logging and retry, using ``litellm.completion``.
    """

    def __init__(self, log_folder: str | None = "./llm_logs", **kwargs):
        """
        Initialize LLM provider.

        Args:
            log_folder (str | None): Directory for interaction logs, None disables logging.
            **kwargs: Arbitrary LiteLLM completion arguments passed to
                ``litellm.completion(messages=messages, **kwargs)``.
        """
        self.log_folder = log_folder
        self.model_config = kwargs
        self.llm_instance = LiteLLMModel(**kwargs)

    @logged_invoke
    @retry(
        stop=stop_after_attempt(8),
        wait=wait_exponential_jitter(initial=20, max=120, jitter=3),
        before_sleep=before_sleep_log(logger, logging.ERROR, exc_info=True)
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
        
        # If your LLM Provider requires user identity login, put it here!

        self.endpoint: Literal["completion", "responses"] = self.pre_flight_check()

    def pre_flight_check(self) -> Literal["completion", "responses"]:
        messages=[{"role":"user", "content":"hello!"}]
        try:
            litellm.completion(
                messages=messages, 
                **self.completion_args
            )
            return "completion"
        except:
            try:
                litellm.responses(
                    input=messages, 
                    **self.completion_args
                )
                return "responses"
            except:
                raise
    
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
    
    def invoke(self, messages: List[BaseMessage]) -> AIMessage:
        payload: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ] + [
            self._to_litellm_message(message) for message in messages
        ]

        if self.endpoint == "completion":
            content, input_tokens, output_tokens, total_tokens, cost = self.invoke_completion(payload)
        elif self.endpoint == "responses":
            content, input_tokens, output_tokens, total_tokens, cost = self.invoke_responses(payload)
        else:
            raise ValueError("Endpoint type is unknown!")

        return AIMessage(
            content=content,
            usage_metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost": cost,
            },
        )
    
    def invoke_completion(self, messages: list[dict[str, Any]]) -> tuple[str, int, int, int, float]:
        response = litellm.completion(
            messages=messages, 
            **self.completion_args
        )

        choice = response.choices[0].message
        content = choice.content if getattr(choice, "content", None) is not None else ""
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", None) or 0
        output_tokens = getattr(usage, "completion_tokens", None) or 0
        total_tokens = getattr(usage, "total_tokens", None) or 0
        cost = response._hidden_params.get("response_cost", None) or 0.0

        return (content, input_tokens, output_tokens, total_tokens, cost)
    
    def invoke_responses(self, messages: list[dict[str, Any]]) -> tuple[str, int, int, int, float]:
        response = litellm.responses(
            input=messages,
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
        input_tokens = getattr(usage, "input_tokens", None) or 0
        output_tokens = getattr(usage, "output_tokens", None) or 0
        total_tokens = getattr(usage, "total_tokens", None) or 0
        cost = response._hidden_params.get("response_cost", None) or 0.0

        return (content, input_tokens, output_tokens, total_tokens, cost)

if __name__ == "__main__":
    model_config = {
        "model": "openai/gpt-4o",
        "temperature": 0.0,
    }
    llm = LLMProvider(log_folder="./llm_logs", **model_config)
    messages = [HumanMessage(content="What is the capital of France?")]
    res = llm.invoke(messages)
    print(res)
