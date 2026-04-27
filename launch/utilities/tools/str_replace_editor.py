import os
import time
from typing import Any, Optional

from launch.core.runtime import SetupRuntime
from launch.agent.action_parser import ActionParser


class Editor(ActionParser):
    action_prompt = """
# String_replace: replace a sub-string with a new sub-string in an existing file. 
    <replace>
        <path>Absolute file path starting from /testbed, C:\\ etc.</path>
        <old_string>Existing sub-string in this file to be replaced. Should have exactly one and only one match in this file.</old_string>
        <new_string>the new sub-string to replace the old sub-string</new_string>
    </replace>
    For example:
    <replace>
        <path>/testbed/src/column/calc.py</path>
        <old_string>    using = router.db_for_read(self.remote_field.model, instance=model_instance)
    qs = self.remote_field.model._default_manager.using(using).filter(
        self.remote_field.field_name
    )
    qs = qs.complex_filter(self.get_limit_choices_to())</old_string>
        <new_string>    using = router.db_for_read(self.remote_field.model, instance=model_instance)
    qs = self.remote_field.model._base_manager.using(using).filter(
        self.remote_field.field_name
    )
    qs = qs.complex_filter(self.get_limit_choices_to())</new_string>
    </replace>

# Create_file: create a new file and git add that file so that it will appear in git diff HEAD. 
    Note if the file path exists and you want to overwrite it, you need to delete it with a command `rm` first before using the create file action.
    <create>
        <path>Absolute file path starting from /testbed, C:\\ etc.</path>
        <content>File content</content>
    </create>
    For example:
    <create>
        <path>/testbed/minimal.mod</path>
        <content>module github.com/docker/cli
go 1.25.0
tool golang.org/x/mod/modfile // for module compatibility check
require (
	dario.cat/mergo v1.0.2
	github.com/containerd/errdefs v1.0.0
	github.com/containerd/log v0.1.0
	github.com/containerd/platforms v1.0.0-rc.2
	github.com/cpuguy83/go-md2man/v2 v2.0.7
	golang.org/x/text v0.35.0
	gotest.tools/v3 v3.5.2
	tags.cncf.io/container-device-interface v1.1.0
)
require (
	github.com/Azure/go-ansiterm v0.0.0-20250102033503-faa5f7b0171c // indirect
	github.com/Microsoft/go-winio v0.6.2 // indirect
	google.golang.org/genproto/googleapis/api v0.0.0-20260209200024-4cfbd4190f57 // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20260209200024-4cfbd4190f57 // indirect
	google.golang.org/grpc v1.79.3 // indirect
	google.golang.org/protobuf v1.36.11 // indirect
)</content>
    </create>
"""

    def __init__(self, container: SetupRuntime):
        self.container = container
        self.mnt_container = container.mnt_container.rstrip("\\").rstrip("/")
        self.mnt_host = container.mnt_host.rstrip("\\").rstrip("/")
    
    def parse(self, response: str) -> Optional[Any]:
        path = self.extract_tag_content(response, "path")
        old_string = self.extract_tag_content(response, "old_string")
        new_string = self.extract_tag_content(response, "new_string")
        content = self.extract_tag_content(response, "content")
        return {
            "path": path,
            "old_string": old_string,
            "new_string": new_string,
            "content": content,
        }
    
    def parse_str_replace(self, response: str) -> dict[str, Any]:
        args = self.parse(response)
        if not args:
            raise
        if (args["path"] is None) or (not args["path"].strip()):
            return {
                "success": False,
                "observation": "The <path></path> field of the string replace action is missing or empty, please generate a string replace with file path, old_string and new_string"
            }
        if (args["old_string"] is None) or (not args["old_string"].strip()):
            return {
                "success": False,
                "observation": "The <old_string></old_string> field of the string replace action is missing or empty, please generate a string replace with file path, old_string and new_string"
            }
        if (args["new_string"] is None):# or (not args["new_string"].strip()): --might be intentional deletion
            return {
                "success": False,
                "observation": "The <new_string></new_string> field of the string replace action is missing or empty, please generate a string replace with file path, old_string and new_string"
            }
        return {
            "success": True,
            "path": args["path"],
            "old_string": args["old_string"],
            "new_string": args["new_string"],
        }
    
    def parse_create_file(self, response: str) -> dict[str, Any]:
        args = self.parse(response)
        if not args:
            raise
        if (args["path"] is None) or (not args["path"].strip()):
            return {
                "success": False,
                "observation": "The <path></path> field of the create file action is missing or empty, please generate a file create action with file path and content"
            }
        if (args["content"] is None) or (not args["content"].strip()):
            return {
                "success": False,
                "observation": "The <content></content> field of the create file action is missing or empty, please generate a file create action with file path and content"
            }
        return {
            "success": True,
            "path": args["path"],
            "content": args["content"]
        }
    
    @staticmethod
    def temp_file()->str:
        import uuid
        return f"{uuid.uuid4()}.txt"
    
    @staticmethod
    def _read_with_encoding_problem(path: str) -> str:
        for encoding in ["utf-8", "utf-16", "utf-16-le", "utf-16-be", "latin-1"]:
            try:
                with open(path, encoding=encoding) as f:
                    s = f.read()
                return s
            except (UnicodeDecodeError, UnicodeError):
                pass
        else:
            with open(path, encoding="utf-8", errors="ignore") as f:
                s = f.read()
            return s
    
    @classmethod
    def safe_read_from_host(cls, path: str) -> str:
        '''
        container file write ops to the mounted / swap folder takes time to sync to the host, so time.sleep is needed.
        '''
        for trial in range(5):
            time.sleep(16)
            if os.path.exists(path):
                break
        s = cls._read_with_encoding_problem(path)
        return s
    
    def _path_exists(self, container_path: str) -> bool:
        res = self.container.send_command(f"ls {container_path}")
        if res.metadata.exit_code == 0:
            return True
        else:
            return False
    
    def _is_file(self, container_path: str) -> bool:
        test_file = f"[ -f {container_path} ]" if self.container.platform == "linux" else f"if (!(Test-Path '{container_path}' -PathType Leaf)) {{throw}}"
        res = self.container.send_command(test_file)
        if res.metadata.exit_code == 0:
            return True
        else:
            return False
    
    def _get_file_from_container(self, container_path: str) -> dict[str, Any]:
        '''
        path not exist: return False, error message
        path exists: return True, path on host
        '''
        if not self._path_exists(container_path):
            return {
                "success": False,
                "error": f"{container_path} does not exist. Cannot edit it. Check again!"
            }
        if not self._is_file(container_path):
            return {
                "success": False,
                "error": f"{container_path} is directory. Cannot edit on directory. Check again!"
            }
        swap_file = self.temp_file()
        container_mnt_path = os.path.join(self.mnt_container, swap_file)
        host_mnt_path = os.path.join(self.mnt_host, swap_file)
        self.container.send_command(f"cp {container_path} {container_mnt_path}")
        return {
                "success": True,
                "container_path": container_mnt_path,
                "host_path": host_mnt_path,
            }
    
    def _write_back(self, swap_path: str, target_path: str, old_swap: Optional[str] = None):
        self.container.send_command(f"rm {target_path}")
        self.container.send_command(f"cp {swap_path} {target_path}")
        self.container.send_command(f"rm {swap_path}")
        if old_swap:
            self.container.send_command(f"rm {old_swap}")
        return
    
    def str_replace(self, path: str, old_str: str, new_str: str) -> str:
        res = self._get_file_from_container(path)
        if not res["success"]:
            return res["error"]
        content = self.safe_read_from_host(res["host_path"])
        if old_str not in content:
            self.container.send_command(f"rm {res['container_path']}")
            return f"Error: your old_string is not found in the file {path}. Please check the file content again!"
        if content.count(old_str) > 1:
            self.container.send_command(f"rm {res['container_path']}")
            return f"Error: your old_string has multiple matches in the file {path}. Please extend the range covered by the old string so that it matches exactly with one specific position in the file!"
        start_idx = content.find(old_str)
        content = content.replace(old_str, new_str)
        new_swap = self.temp_file()
        new_host_path = os.path.join(self.mnt_host, new_swap)
        new_container_path = os.path.join(self.mnt_container, new_swap)
        with open(new_host_path, "w", encoding="utf-8") as f:
            f.write(content)
        self._write_back(new_container_path, path, old_swap=res["container_path"])
        end_idx = start_idx + len(new_str)
        observation = (
            "......\n"
            + "\n".join(content[:start_idx].splitlines()[-10:])
            + new_str 
            + "\n".join(content[end_idx:].splitlines()[:10])
            + "\n......"
        )
        return f"File edit is successful. New file content around the edit location:\n{observation}"

    def create_file(self, path: str, content: str) -> str:
        exists = self._path_exists(path)
        is_file = self._is_file(path)
        if is_file:
            return f"The file {path} exists. If you really want to overwrite it, delete this file using a shell command `rm`, then use the create tool to create a new file."
        if exists and (not is_file):
            return f"Path {path} is a directory. Cannot create file on an existing directory path."
        swap_file = self.temp_file()
        with open(os.path.join(self.mnt_host,swap_file), "w", encoding="utf-8") as f:
            f.write(content)
        self._write_back(os.path.join(self.mnt_container,swap_file), path)
        observation = f"File created successfully at {path}.\n"
        if ("testbed" in path) or ((not path.strip().startswith("C:")) and (not path.strip().startswith("/"))):
            self.container.send_command(f"git add {path}")
            observation += f"File {path} is tracked by git.\n"
        return observation
    
    def get_time_stamp(self, path: str) -> float|None:
        """Return file modification time as epoch seconds (float), or None."""
        if not self._path_exists(path):
            return None
        if self.container.platform == "windows":
            cmd = f'(Get-Item "{path}").LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss.ff")'
        else:
            cmd = f"stat -c %Y {path}"
        res = self.container.send_command(cmd)
        if res.metadata.exit_code != 0:
            return None
        lines = res.output.strip().splitlines()
        if len(lines)<=1:
            return None
        
        for raw in lines:
            try:
                # Linux: epoch seconds e.g. "1713100800"
                tsp = float(raw)
                print(tsp)
                return tsp
            except ValueError:
                pass
        # Windows: "yyyy-MM-dd HH:mm:ss.ffffff"
        from datetime import datetime
        for raw in lines:
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(raw, fmt)
                    tsp = dt.timestamp()
                    print(tsp)
                    return tsp
                except ValueError:
                    continue
        return None

