"""
Docker runtime management for repository setup and command execution.

Provides containerized environment for repository testing with command execution,
file operations, and state management capabilities.
"""

from __future__ import annotations
from typing import Any

from launch.core.platforms.base import available_platforms
from launch.core.platforms.base import BaseRuntime

class SetupRuntime: 
    '''
    Public API for docker runtime
    link API to different platform implementations
    '''

    @staticmethod
    def from_launch_image(
        image_name: str,
        instance_id: str,
        platform: available_platforms = "linux",
        command_timeout: int = 30
    ) -> BaseRuntime:
        if platform == "linux":
            from launch.core.platforms.linux import LinuxRuntime
            return LinuxRuntime.start_runtime_from_launch_image(
                image_name,
                instance_id,
                command_timeout
            )
        elif platform == "windows":
            from launch.core.platforms.windows import WindowsRuntime
            return WindowsRuntime.start_runtime_from_launch_image(
                image_name,
                instance_id,
                command_timeout
            )
        elif platform == "android":
            from launch.core.platforms.android import AndroidRuntime
            return AndroidRuntime.start_runtime_from_launch_image(
                image_name,
                instance_id,
                command_timeout
            )
        elif platform == "macos":
            raise NotImplementedError("start MacOS container and boost into cli is still not supported.")
        else:
            raise ValueError(f"Container Platform {platform} unknown.")
        
    @staticmethod
    def from_base_image(
        image_name: str,
        instance: dict[str, Any],
        platform: available_platforms = "linux",
        command_timeout: int = 30,
    ) -> BaseRuntime:
        if platform == "linux":
            from launch.core.platforms.linux import LinuxRuntime
            return LinuxRuntime.start_runtime_from_base_image(
                image_name,
                instance,
                command_timeout
            )
        elif platform == "windows":
            from launch.core.platforms.windows import WindowsRuntime
            return WindowsRuntime.start_runtime_from_base_image(
                image_name,
                instance,
                command_timeout
            )
        elif platform == "android":
            from launch.core.platforms.android import AndroidRuntime
            return AndroidRuntime.start_runtime_from_base_image(
                image_name,
                instance,
                command_timeout
            )
        elif platform == "macos":
            raise NotImplementedError("start MacOS container and boost into cli is still not supported.")
        else:
            raise ValueError(f"Container Platform {platform} unknown.")
