from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from launch.core.platforms.windows import (
    DEFAULT_WINDOWS_CONTAINER_NO_PROXY,
    WINDOWS_CONTAINER_NO_PROXY_ENV,
    WINDOWS_CONTAINER_PROXY_ENV,
    build_windows_container_environment,
)


class WindowsContainerProxyTest(unittest.TestCase):
    def test_default_does_not_inject_machine_local_proxy(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            environment = build_windows_container_environment()

        self.assertEqual(environment, {"TERM": "xterm-mono"})
        self.assertNotIn("HTTP_PROXY", environment)
        self.assertNotIn("http_proxy", environment)

    def test_explicit_proxy_populates_common_toolchain_spellings(self) -> None:
        proxy = "http://host.docker.internal:7897"
        with mock.patch.dict(
            os.environ,
            {WINDOWS_CONTAINER_PROXY_ENV: proxy},
            clear=True,
        ):
            environment = build_windows_container_environment()

        for key in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        ):
            self.assertEqual(environment[key], proxy)
        self.assertEqual(environment["NO_PROXY"], DEFAULT_WINDOWS_CONTAINER_NO_PROXY)
        self.assertEqual(environment["no_proxy"], DEFAULT_WINDOWS_CONTAINER_NO_PROXY)

    def test_host_proxy_is_used_only_when_explicitly_selected(self) -> None:
        host_proxy = "http://host.docker.internal:7897"
        with mock.patch.dict(
            os.environ,
            {
                "HTTP_PROXY": host_proxy,
                "HTTPS_PROXY": host_proxy,
                "ALL_PROXY": host_proxy,
            },
            clear=True,
        ):
            environment = build_windows_container_environment()

        self.assertEqual(environment, {"TERM": "xterm-mono"})
        self.assertNotIn("HTTP_PROXY", environment)

        with mock.patch.dict(
            os.environ,
            {WINDOWS_CONTAINER_PROXY_ENV: host_proxy},
            clear=True,
        ):
            environment = build_windows_container_environment()

        self.assertEqual(environment["HTTP_PROXY"], host_proxy)
        self.assertEqual(environment["HTTPS_PROXY"], host_proxy)

    def test_explicit_no_proxy_overrides_default(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                WINDOWS_CONTAINER_PROXY_ENV: "http://proxy.example:8080",
                WINDOWS_CONTAINER_NO_PROXY_ENV: "localhost,fakerepo",
            },
            clear=True,
        ):
            environment = build_windows_container_environment()

        self.assertEqual(environment["NO_PROXY"], "localhost,fakerepo")
        self.assertEqual(environment["no_proxy"], "localhost,fakerepo")


if __name__ == "__main__":
    unittest.main()