from launch.agent.setup.verify import (
    observation_for_verify_action,
    parse_verify_action,
)


def test_parse_verify_action_returns_none_for_unparseable_response():
    # A reply that contains no well-formed `Action:` block cannot be parsed
    # into a VerifyAction, so parse_verify_action returns None.
    assert parse_verify_action("Thought: the environment builds fine.") is None
    assert parse_verify_action("") is None


def test_observation_for_verify_action_handles_none_without_crashing():
    # None is an expected value (see the type hint VerifyAction | None); the
    # observation helper routes it back to the agent as a format reminder and
    # never touches the session, so the verify loop must not dereference the
    # action before this point.
    obs = observation_for_verify_action(None, None)
    assert "Action" in obs.content
