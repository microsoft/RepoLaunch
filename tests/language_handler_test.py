'''
# test the the combinations of
# 4 platforms: linux, windows, android and
# 9 languages: Python, C++, C, C#, Go, Rust, Java, JavaScript, TypeScript

# Your task is to test any combination all has the `correct output type` for methods:
# language, base_images, setup_environment, get_setup_instructions, cleanup_environment, get_test_cmd_instructions
'''

import pytest

from launch.utilities.language_handlers import get_language_handler


LANGUAGES = [
    "Python",
    "C++",
    "C",
    "C#",
    "Go",
    "Rust",
    "Java",
    "JavaScript",
    "TypeScript",
]
PLATFORMS = [
    "linux", 
    "windows", 
    "android", 
    #"macos"
]


class DummySession:
    def __init__(self):
        self.commands = []

    def send_command(self, command: str):
        self.commands.append(command)


def first_base_image(base_images: list[str] | dict[str, str]) -> str:
    if isinstance(base_images, dict):
        return next(iter(base_images))
    return base_images[0]


def assert_base_images_type(base_images: list[str] | dict[str, str]) -> None:
    assert isinstance(base_images, (list, dict))
    assert len(base_images) > 0
    if isinstance(base_images, list):
        assert all(isinstance(image, str) and image for image in base_images)
    else:
        assert all(isinstance(image, str) and image for image in base_images.keys())
        assert all(isinstance(description, str) and description for description in base_images.values())


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("platform", PLATFORMS)
def test_language_handler_output_types_for_platform(language, platform):
    handler = get_language_handler(language)
    session = DummySession()

    language_name = handler.language
    assert isinstance(language_name, str)
    assert language_name

    base_images = handler.base_images(platform=platform)
    assert_base_images_type(base_images)

    if language in ["Python"]:
        server = handler.setup_environment(session, date="2025-09-07T21:34:16Z")
        assert server is not None
        handler.cleanup_environment(session, server=server)

    setup_instructions = handler.get_setup_instructions(
        first_base_image(base_images),
        platform=platform,
    )
    assert isinstance(setup_instructions, str)
    assert setup_instructions.strip()

    test_cmd_instructions = handler.get_test_cmd_instructions()
    assert isinstance(test_cmd_instructions, str)
    assert test_cmd_instructions.strip()
