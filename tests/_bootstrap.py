import os
import sys
import types


class _FakeLogger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def debug(self, *args, **kwargs):
        return None


def install_fake_astrbot() -> None:
    astrbot_module = types.ModuleType("astrbot")
    api_module = types.ModuleType("astrbot.api")
    core_module = types.ModuleType("astrbot.core")
    message_module = types.ModuleType("astrbot.core.message")
    components_module = types.ModuleType("astrbot.core.message.components")
    utils_module = types.ModuleType("astrbot.core.utils")
    io_module = types.ModuleType("astrbot.core.utils.io")
    path_module = types.ModuleType("astrbot.core.utils.astrbot_path")

    logger = _FakeLogger()
    api_module.logger = logger

    class FunctionTool:
        """Fake FunctionTool base class for testing."""
        pass

    api_module.FunctionTool = FunctionTool

    event_module = types.ModuleType("astrbot.api.event")

    class AstrMessageEvent:
        pass

    event_module.AstrMessageEvent = AstrMessageEvent
    api_module.event = event_module

    def get_astrbot_data_path() -> str:
        return os.environ["ASTRBOT_TEST_DATA_PATH"]

    async def download_image_by_url(url: str) -> str:
        raise NotImplementedError("download_image_by_url not available in tests")

    class Plain:
        def __init__(self, text: str):
            self.text = text

    class Image:
        def __init__(self, path: str):
            self.path = path

        @classmethod
        def fromFileSystem(cls, path: str):
            return cls(path)

    components_module.Plain = Plain
    components_module.Image = Image

    path_module.get_astrbot_data_path = get_astrbot_data_path
    io_module.download_image_by_url = download_image_by_url

    sys.modules["astrbot"] = astrbot_module
    sys.modules["astrbot.api"] = api_module
    sys.modules["astrbot.api.event"] = event_module
    sys.modules["astrbot.core"] = core_module
    sys.modules["astrbot.core.message"] = message_module
    sys.modules["astrbot.core.message.components"] = components_module
    sys.modules["astrbot.core.utils"] = utils_module
    sys.modules["astrbot.core.utils.io"] = io_module
    sys.modules["astrbot.core.utils.astrbot_path"] = path_module
