from launch.core.workflow import define_organize_workflow, define_setup_workflow


def _workflow_nodes(workflow):
    return set(workflow.get_graph().nodes)


def _workflow_edges(workflow):
    return {
        (edge.source, edge.target, edge.data, edge.conditional)
        for edge in workflow.get_graph().edges
    }


def _workflow_branches(workflow):
    return {
        source: {
            branch_name: dict(branch.ends)
            for branch_name, branch in branches.items()
        }
        for source, branches in workflow.builder.branches.items()
    }


def test_setup_workflow_shape_is_preserved():
    workflow = define_setup_workflow()

    assert _workflow_nodes(workflow) == {
        "__start__",
        "locate_related_file",
        "select_base_image",
        "start_bash_session",
        "setup",
        "verify",
        "save_result",
        "__end__",
    }
    assert _workflow_edges(workflow) == {
        ("__start__", "locate_related_file", None, False),
        ("locate_related_file", "select_base_image", None, False),
        ("select_base_image", "start_bash_session", None, False),
        ("start_bash_session", "setup", None, False),
        ("setup", "verify", None, False),
        ("verify", "save_result", "return", True),
        ("verify", "setup", "continue", True),
        ("save_result", "__end__", None, False),
    }
    assert _workflow_branches(workflow) == {
        "verify": {
            "condition": {
                "return": "save_result",
                "continue": "setup",
            },
        },
    }


def test_organize_workflow_shape_includes_testone_by_default():
    workflow = define_organize_workflow()

    assert _workflow_nodes(workflow) == {
        "__start__",
        "locate_related_file",
        "container",
        "rebuild",
        "testall",
        "parselog",
        "testone",
        "save_result",
        "__end__",
    }
    assert _workflow_edges(workflow) == {
        ("__start__", "container", None, True),
        ("__start__", "locate_related_file", None, True),
        ("locate_related_file", "container", None, False),
        ("container", "rebuild", None, False),
        ("rebuild", "save_result", "return", True),
        ("rebuild", "testall", "continue", True),
        ("testall", "save_result", "return", True),
        ("testall", "parselog", "continue", True),
        ("parselog", "save_result", "return", True),
        ("parselog", "testone", "continue", True),
        ("testone", "save_result", None, False),
        ("save_result", "__end__", None, False),
    }
    assert _workflow_branches(workflow) == {
        "__start__": {
            "condition": {
                "container": "container",
                "locate_related_file": "locate_related_file",
            },
        },
        "rebuild": {
            "condition": {
                "return": "save_result",
                "continue": "testall",
            },
        },
        "testall": {
            "condition": {
                "return": "save_result",
                "continue": "parselog",
            },
        },
        "parselog": {
            "condition": {
                "return": "save_result",
                "continue": "testone",
            },
        },
    }


def test_organize_workflow_shape_can_skip_testone():
    workflow = define_organize_workflow(get_pertest_cmd=False)

    assert _workflow_nodes(workflow) == {
        "__start__",
        "locate_related_file",
        "container",
        "rebuild",
        "testall",
        "parselog",
        "save_result",
        "__end__",
    }
    assert _workflow_edges(workflow) == {
        ("__start__", "container", None, True),
        ("__start__", "locate_related_file", None, True),
        ("locate_related_file", "container", None, False),
        ("container", "rebuild", None, False),
        ("rebuild", "save_result", "return", True),
        ("rebuild", "testall", "continue", True),
        ("testall", "save_result", "return", True),
        ("testall", "parselog", "continue", True),
        ("parselog", "save_result", "continue", True),
        ("save_result", "__end__", None, False),
    }
    assert _workflow_branches(workflow) == {
        "__start__": {
            "condition": {
                "container": "container",
                "locate_related_file": "locate_related_file",
            },
        },
        "rebuild": {
            "condition": {
                "return": "save_result",
                "continue": "testall",
            },
        },
        "testall": {
            "condition": {
                "return": "save_result",
                "continue": "parselog",
            },
        },
        "parselog": {
            "condition": {
                "return": "save_result",
                "continue": "save_result",
            },
        },
    }
