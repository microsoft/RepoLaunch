"""
Log parser generation agent for improving test output parsing accuracy.
"""
import json
from typing import Any, Literal

from langchain.schema import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from launch.agent.action_parser import ActionParser
from launch.agent.prompt import ReAct_prompt
from launch.agent.state import AgentState, auto_catch
from launch.scripts.parser import run_parser

system_msg: str = """You are a developer specializing in test output analysis and parsing. Your task is to examine the test output, evaluate the current parser, and generate an improved, fully robust parser.

You have access to:
- **Raw test output** from the previous stage: {test_output}
- **Draft parser script** from the previous stage: {current_parser}
- **Draft parser results**: {current_results}

Your goal is to write a parser that it correctly extracts *every* test case and its status.

## Your Tasks:
1. **Analyze Draft Parser**: Evaluate how well the draft parser extracts test case statuses from the test output
2. **Identify Improvement Opportunities**: Look for:
   - Missed test cases that should have been parsed
   - Incorrectly parsed test cases
   - Edge cases not handled properly
   - Parsing patterns that could be more robust

3. **Generate Improved Parser**: Create a reliable parser that:
   - Handles edge cases better
   - Robust to output format variations
   - Extracts granular test case information
   - Make it as simple as possible while being effective

# REQUIRED PARSER OUTPUT
Your final parser MUST return **only** a dictionary in this exact form:
{{"test_case_name": "pass", "another_test": "fail", "third_test": "skip"}}
The test statuses can only be in {{"pass", "fail", "skip"}}. Any kinds of fail of error should be taken as 'fail'.

## Hints for testcase extraction
Refer to the patterns below to identify test cases and their statuses.
XML (Maven, Gradle, JUnit, TestNG):
- Look for `<testsuite>` and `<testcase>` elements.
- Status rules: `<failure>` → fail, `<error>` → fail, `<skipped>` → skip, otherwise pass.
pytest:
- Lines like: `file.py::test_name PASSED/FAILED/SKIPPED/ERROR`.
unittest:
- Patterns such as: `TestClass.test_method ... ok/FAIL/ERROR`.
Jest:
- Symbols: `✓` pass, `✕` fail, `○` skip  
- Or keywords: `PASS` / `FAIL`.
Go test:
- Lines like: `--- PASS: TestName`, `--- FAIL: TestName`, `--- SKIP: TestName`.
Other frameworks:
- Look for consistent use of `PASS`, `FAIL`, or `SKIP` near test case names.

You need to finish this in {steps} steps.
"""


class ParseLogAction(BaseModel):
    """
    Analyze: Analyze the current parser performance and test output patterns
        <analyze>your analysis of current parser issues and improvement opportunities</analyze>
        
    Parse: Generate an improved parser script
        The input log argument is from the test log from the previous stage. The system automatically passes the test log as the input when you use the <python></python> action and gives you the result of the script.
        <python>def parser(log: str) -> dict[str, str]:
        # Your improved parser implementation
        import re
        results = {}
        # ... parsing logic ...
        return results</python>
        
    Submit: Submit the final improved parser
        <submit>final parser is ready and tested</submit>
    """

    action: Literal["analyze", "python", "submit"] = Field(
        "analyze", description="The action type"
    )
    args: Any = Field(None, description="The action arguments")


class ParseLogObservation(BaseModel):
    """Observation for the parse log action"""

    content: str = Field("", description="The content of the observation")
    is_stop: bool = Field(False, description="Whether stop the parse log loop")


class ParseLogActionParser(ActionParser):
    """Parser for parse log agent actions."""
    
    def parse(self, response: str) -> ParseLogAction | None:
        """Parse action from LLM response text."""
        response = self.clean_response(response)
        
        submit = self.extract_tag_content(response, "submit")
        if submit:
            return ParseLogAction(action="submit", args=submit)

        script = self.extract_tag_content(response, "python")
        if script:
            return ParseLogAction(action="python", args=script)

        analyze = self.extract_tag_content(response, "analyze")
        if analyze:
            return ParseLogAction(action="analyze", args=analyze)
            
        return None


def parse_parselog_action(response: str) -> ParseLogAction | None:
    """Parse parse log action from LLM response text."""
    parser = ParseLogActionParser()
    return parser.parse(response)


PARSELOG_CONVERSATION_WINDOW = 30


@auto_catch
def generate_log_parser(state: AgentState, max_steps: int = 20) -> dict:
    """
    Agent for generating improved log parsers based on test output analysis.
    
    Args:
        max_steps (int): Maximum number of steps allowed
        state (AgentState): Current agent state with test results
        
    Returns:
        dict: Updated state with improved parser and results
    """

    improved_parser: str = ""
    framework_detected: str = ""
    analysis_result: str = ""
    improved_test_status: dict[str, Literal['pass', 'fail', 'skip']] = {}
    def observation_for_parselog_action(
        state: AgentState, action: ParseLogAction | None
    ) -> ParseLogObservation:
        """Execute parse log action and return observation."""
        nonlocal improved_parser, framework_detected, analysis_result, improved_test_status

        if not action or not action.action:
            content = f"""Please use the following format to make a valid action choice:\n{ParseLogAction.__doc__}"""
            return ParseLogObservation(content=content, is_stop=False)
            
        if action.action == "analyze":
            analysis_result = action.args
            content = f"Analysis completed: {action.args}\n\nNow try to write the parser."
            return ParseLogObservation(content=content, is_stop=False)
            
        elif action.action == "python":
            improved_parser = action.args

            if not improved_parser:
                content = "No parser script available to test. Please create a parser first."
                return ParseLogObservation(content=content, is_stop=False)
                
            # Get test output from previous stage
            test_output = state.get("test_output", "")
            if not test_output:
                # This should not happen as we store test_output in state at the beginning of generate_log_parser, but just in case...
                raise ValueError("No test output available from previous stage to test against.")
                
            # Test the improved parser
            try:
                result = run_parser(improved_parser, test_output)
                if not isinstance(result, dict):
                    content = f"Your python parser script should return a dict[str, Literal['pass', 'fail', 'skip']]. However, your script returned type {type(result)}. Please adjust your parser script to make sure it returns the correct format."
                    return ParseLogObservation(content=content, is_stop=False)
                improved_test_status = result
                truncated_result = json.dumps(result, indent=2)
                if len(truncated_result) > 10000:
                    truncated_result = truncated_result[:10000] + "\n...result truncated due to length..."
                
                # Compare with original results if available
                original_results = state.get("test_status", {})
                if original_results:
                    new_count = len(result)
                    old_count = len(original_results)
                    content = f"""Test results for improved parser:
{truncated_result}

Comparison with original parser:
- Original parser found: {old_count} test cases
- Improved parser found: {new_count} test cases
- Difference: {new_count - old_count} test cases

Please analyze if this is an improvement and submit if satisfied."""
                else:
                    content = f"""Test results for improved parser:
{truncated_result}

Parser executed successfully. Please analyze the results and submit if satisfied."""
                    
            except Exception as e:
                content = f"Error testing parser: {str(e)}\nPlease fix the parser and try again."
                
            return ParseLogObservation(content=content, is_stop=False)
            
        
        elif action.action == "submit":
            if not improved_parser:
                content = "No improved parser available to submit. Please create a parser with <python></python> action first."
                return ParseLogObservation(content=content, is_stop=False)
            
            if not improved_test_status:
                content = f"Your last parser did not return any test case: {improved_test_status}. Please adjust your parser to make it able to extract test case names and their statuses from test log with <python></python> action."
                return ParseLogObservation(content=content, is_stop=False) 
            
            return ParseLogObservation(content=action.args, is_stop=True)

        return ParseLogObservation(content="Unknown action", is_stop=False)

    if state["exception"]:
        raise state["exception"]

    session = state["session"]
    llm = state["llm"]
    logger = state["logger"]
    
    # Get data from previous testall stage
    test_output = ""
    current_parser = ""
    current_results = {}
    
    # Rerun test commands and print commands to get fresh test output
    test_commands = state.get("test_commands", [])
    print_commands = state.get("print_commands", [])

    if test_commands:
        for cmd in test_commands:
            logger.info(f"Rerunning test command: {cmd}")
            session.send_command(cmd)
    
    if print_commands:
        for cmd in print_commands:
            logger.info(f"Running print command: {cmd}")
            result = session.send_command(cmd)
            test_output += result.output

    
    if "parser" in state:
        current_parser = state.get("parser", "")
    
    if "test_status" in state:
        current_results = state.get("test_status", {})

    logger.info("-" * 10 + "Start parse log conversation" + "-" * 10)
    
    messages = [
        SystemMessage(
            system_msg.format(
                test_output=test_output[:15000] + "..." if len(test_output) > 15000 else test_output,
                current_parser=current_parser,
                current_results=json.dumps(current_results, indent=2)[:2000] + "..." if len(json.dumps(current_results, indent=2)) > 2000 else json.dumps(current_results, indent=2),
                steps=max_steps,
            )
        ),
        HumanMessage(
            ReAct_prompt.format(
                tools=ParseLogAction.__doc__,
                project_structure=state.get("repo_structure", ""),
                docs=state.get("docs", ""),
            )
        ),
    ]
    
    prefix_messages = len(messages)
    step = 0
    answer = None
    
    # Store test_output in state for testing
    state["test_output"] = test_output
    
    while step < max_steps:
            
        step += 1
        
        # Use conversation window to avoid context overflow
        if len(messages) < PARSELOG_CONVERSATION_WINDOW + prefix_messages:
            input_messages = messages
        else:
            input_messages = (
                messages[:prefix_messages] + messages[-PARSELOG_CONVERSATION_WINDOW:]
            )
            
        response = llm.invoke(input_messages)
        logger.info("\n" + response.pretty_repr())
        messages.append(response)
        
        action = parse_parselog_action(response.content)
        observation = observation_for_parselog_action(state, action)
        
        if observation.is_stop:
            answer = observation.content
            break
            
        message = HumanMessage(f"Observation:\n{observation.content}")
        logger.info("\n" + message.pretty_repr())
        messages.append(message)

    logger.info("-" * 10 + "End parse log conversation" + "-" * 10)
    
    # Use the final improved parser if success else keep the old test status if the new parser does not return any result
    if improved_test_status:
        final_test_status = improved_test_status
        final_parser = improved_parser
    else:
        final_test_status = state.get("test_status", {})
        final_parser = state.get("parser", "")
    
    return {
        "messages": messages,
        "parser": final_parser,
        "framework_detected": framework_detected,
        "analysis_result": analysis_result,
        "test_status": final_test_status,
        "success": bool(final_test_status and final_parser),
        "test_output": test_output,
    }