import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


from wechat_decrypt_tool import runtime_settings


class TestEnvFilePath(unittest.TestCase):
    """Regression for issue #87: frozen builds wrote `.env` into the signed bundle."""

    def test_dev_project_root_gets_env_file(self):
        with TemporaryDirectory() as td:
            (Path(td) / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            # 必须在 with 块内恢复 CWD：addCleanup 在方法结束后才执行，
            # 届时 Windows 无法删除仍被进程占用的临时目录（WinError 32）。
            prev = os.getcwd()
            os.chdir(td)
            try:
                cwd = Path.cwd()
                self.assertEqual(runtime_settings.get_env_file_path(), cwd / ".env")
            finally:
                os.chdir(prev)

    def test_frozen_build_never_writes_env(self):
        with TemporaryDirectory() as td:
            (Path(td) / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            prev = os.getcwd()
            os.chdir(td)
            try:
                cwd = Path.cwd()
                with patch.object(runtime_settings.sys, "frozen", True, create=True):
                    self.assertIsNone(runtime_settings.get_env_file_path())
                    self.assertIsNone(runtime_settings.write_backend_port_env_file(12345))
                    self.assertIsNone(runtime_settings.write_backend_host_env_file("0.0.0.0"))
                    self.assertIsNone(runtime_settings.write_mcp_token_env_file("t" * 32))
                self.assertFalse((cwd / ".env").exists())
            finally:
                os.chdir(prev)

    def test_explicit_env_file_override_wins_even_when_frozen(self):
        with TemporaryDirectory() as td:
            target = Path(td) / "custom.env"
            with patch.dict(os.environ, {runtime_settings.ENV_FILE_KEY: str(target)}):
                with patch.object(runtime_settings.sys, "frozen", True, create=True):
                    self.assertEqual(runtime_settings.get_env_file_path(), target)


if __name__ == "__main__":
    unittest.main()
