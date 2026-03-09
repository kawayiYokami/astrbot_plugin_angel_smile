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
    utils_module = types.ModuleType("astrbot.core.utils")
    path_module = types.ModuleType("astrbot.core.utils.astrbot_path")

    logger = _FakeLogger()
    api_module.logger = logger

    def get_astrbot_data_path() -> str:
        return os.environ["ASTRBOT_TEST_DATA_PATH"]

    path_module.get_astrbot_data_path = get_astrbot_data_path

    sys.modules["astrbot"] = astrbot_module
    sys.modules["astrbot.api"] = api_module
    sys.modules["astrbot.core"] = core_module
    sys.modules["astrbot.core.utils"] = utils_module
    sys.modules["astrbot.core.utils.astrbot_path"] = path_module

