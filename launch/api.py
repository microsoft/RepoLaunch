from typing import Any, Literal
from launch.core.runtime import CommandResult, SetupRuntime
from launch.scripts.parser import run_parser

TestStatus = Literal['pass', 'fail', 'skip']

class LaunchedInstance:
    def __init__(self, instance: dict[str, Any], platform: Literal["linux", "windows"]):
        if (not (instance.get("instance_id", ""))) \
            or (not (instance.get("docker_image", ""))) \
            or (not (instance.get("rebuild_cmds", []))) \
            or (not (instance.get("test_cmds", []))) \
            or (not (instance.get("print_cmds", []))) \
            or (not (instance.get("log_parser", ""))):
                raise ValueError("instance dict must be result that has successfully passed both setup and organize stages")

        self.instance = instance
        self.container = SetupRuntime.from_launch_image(
            instance["docker_image"], 
            instance["instance_id"],
            platform=platform
        )
        self.instance_id = instance["instance_id"]
    
    def apply_patch(self, patch: str, verbose: bool = True) -> None:
        self.container.apply_patch(patch, verbose=verbose)
    
    def build(self, verbose: bool = True) -> tuple[bool, str]:
        res: CommandResult = self.container.send_command(";".join(self.instance["rebuild_cmds"]))
        if int(res.metadata.exit_code) != 0:
            if verbose:
                print(f"{self.instance_id} -- Build returned non-zero exit code. \nBuild log:\n{res.output}\n\n\n\n", flush=True)
            return (False, res.output)
        return (True, res.output)

    def test(self) -> str:
        self.container.send_command(";".join(self.instance["test_cmds"]))
        testlog: str = self.container.send_command(";".join(self.instance["print_cmds"])).output
        return testlog
    
    def parse_test_log(self, log: str) -> dict[str, TestStatus]:
        status = run_parser(self.instance["log_parser"], log)
        if not isinstance(status, dict):
            print(f"{self.instance_id} -- Warning: due to LLM hallucination test parser fails to return test::status mapping dict. Returning empty dict...", flush=True)
            return {}
        return status
    
    def build_test_parse(self, verbose: bool = True):
        success, build_log = self.build(verbose=verbose)
        if not success:
            print(f"{self.instance_id} -- Warning: Build returned non-zero exit code which may indicate failure.", flush=True)
        log: str = self.test()
        status: dict[str, TestStatus] = self.parse_test_log(log)
        return status
    
    def git_commit(self, msg: int) -> tuple[bool, str]:
        msg = msg.replace("\n", "    //").replace("\t", "    ")
        res: CommandResult = self.container.send_command(f"git commit -m '{msg}'")
        return (res.metadata.exit_code==0, res.output)
    
    def commit_image(self, image_name: str, tag: str) -> None:
        self.container.commit(image_name=image_name, tag=tag)

    def __del__(self):
        if hasattr(self, "container"):
            self.container.cleanup()