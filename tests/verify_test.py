from launch.agent.setup.verify import (
    observation_for_verify_action,
    parse_verify_action,
)


def test_parse_verify_action_return_value():
    # A reply that contains no well-formed `Action:` block cannot be parsed
    # into a VerifyAction, so parse_verify_action returns None.
    assert parse_verify_action("Thought: the environment builds fine.") is None
    assert parse_verify_action("") is None
    command_action = parse_verify_action("<command>ls</command>")
    assert command_action is not None
    assert command_action.action == "command"
    assert command_action.args == "ls"
    success_action = parse_verify_action("<issue>None</issue>")
    assert success_action is not None
    assert success_action.action == "issue"
    assert success_action.args == "none"
    issue_action = parse_verify_action("<issue>The repo is ONLY partially build.</issue>")
    assert issue_action is not None
    assert issue_action.action == "issue"
    assert issue_action.args == "the repo is only partially build."


def test_observation_for_verify_action_handles_none_without_crashing():
    # None is an expected value (see the type hint VerifyAction | None); the
    # observation helper routes it back to the agent as a format reminder and
    # never touches the session, so the verify loop must not dereference the
    # action before this point.
    obs = observation_for_verify_action(None, None)
    assert "Please using following format after `Action: `" in obs.content
