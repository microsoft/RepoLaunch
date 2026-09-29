import ast
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from launch.core.platforms.base import CommandResult
from launch.core.platforms.windows import WindowsRuntime


WINDOWS_RUNTIME = ROOT / "launch" / "core" / "platforms" / "windows.py"


class WindowsCommandCwdTests(unittest.TestCase):
    def test_windows_commands_explicitly_start_from_runtime_checkout(self):
        source_text = WINDOWS_RUNTIME.read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        send_command = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "send_command"
        )
        source = ast.get_source_segment(source_text, send_command)
        self.assertIsNotNone(source)
        assert source is not None
        self.assertIn("working_dir = self.working_dir.replace", source)
        self.assertIn("Set-Location -LiteralPath '{working_dir}'", source)
        self.assertIn("workdir=self.working_dir", source)

    def test_fresh_exec_preserves_a_directory_changed_by_the_prior_command(self):
        class FakeContainer:
            def __init__(self):
                self.calls = []
                self.locations = [r"C:\go\src\github.com\docker\docker", r"C:\go\src\github.com\docker\docker"]

            def exec_run(self, command, **kwargs):
                self.calls.append((command, kwargs))
                location = self.locations.pop(0)
                metadata = json.dumps({
                    "exit_code": 0,
                    "username": "u",
                    "hostname": "h",
                    "working_dir": location,
                    "py_interpreter_path": "",
                }, separators=(",", ":"))
                payload = f"ok\n###PS1JSON###\n{metadata}\n###PS1END###\n".encode("utf-8")
                return type("ExecResult", (), {"output": payload, "exit_code": 0})()

            def stop(self):
                pass

            def remove(self, force=False):
                pass

        runtime = object.__new__(WindowsRuntime)
        runtime.container = FakeContainer()
        runtime.command_timeout = 1
        runtime.stopped = False
        runtime.working_dir = r"C:\testbed"
        runtime.mnt_host = str(ROOT / "tmp")

        first: CommandResult = runtime.send_command(r"Set-Location C:\go\src\github.com\docker\docker")
        second: CommandResult = runtime.send_command("go test -json -v ./...")

        self.assertEqual(first.metadata.exit_code, 0)
        self.assertEqual(second.metadata.exit_code, 0)
        self.assertEqual(runtime.working_dir, r"C:\go\src\github.com\docker\docker")
        self.assertEqual(len(runtime.container.calls), 2)
        _, first_kwargs = runtime.container.calls[0]
        _, second_kwargs = runtime.container.calls[1]
        self.assertEqual(first_kwargs["workdir"], r"C:\testbed")
        self.assertEqual(second_kwargs["workdir"], r"C:\go\src\github.com\docker\docker")
        scripts = list((ROOT / "tmp").glob("windows-command-*.ps1"))
        self.assertEqual(scripts, [])
        runtime.stopped = True

    def test_fresh_exec_falls_back_to_runtime_checkout_without_prior_metadata(self):
        class FakeContainer:
            def __init__(self):
                self.calls = []

            def exec_run(self, command, **kwargs):
                self.calls.append((command, kwargs))
                metadata = json.dumps({
                    "exit_code": 0,
                    "username": "u",
                    "hostname": "h",
                    "working_dir": r"C:\\testbed",
                    "py_interpreter_path": "",
                }, separators=(",", ":"))
                payload = f"ok\n###PS1JSON###\n{metadata}\n###PS1END###\n".encode("utf-8")
                return type("ExecResult", (), {"output": payload, "exit_code": 0})()

            def stop(self):
                pass

            def remove(self, force=False):
                pass

        runtime = object.__new__(WindowsRuntime)
        runtime.container = FakeContainer()
        runtime.command_timeout = 1
        runtime.stopped = False
        runtime.working_dir = r"C:\testbed"
        runtime.mnt_host = str(ROOT / "tmp")

        result: CommandResult = runtime.send_command("Get-Location")

        self.assertEqual(result.metadata.exit_code, 0)
        self.assertEqual(len(runtime.container.calls), 1)
        command, kwargs = runtime.container.calls[0]
        self.assertEqual(kwargs["workdir"], r"C:\testbed")
        self.assertEqual(command[-1], r"C:\mnt_tmp\windows-command-" + command[-1].split("windows-command-", 1)[1])
        scripts = list((ROOT / "tmp").glob("windows-command-*.ps1"))
        self.assertEqual(scripts, [])
        runtime.stopped = True


if __name__ == "__main__":
    unittest.main()