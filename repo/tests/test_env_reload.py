from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.utils.env import load_project_env


class EnvReloadTests(unittest.TestCase):
    def test_load_project_env_can_override_selected_keys(self) -> None:
        project_root = ROOT / "tests" / "_tmp_env_reload"
        if project_root.exists():
            shutil.rmtree(project_root)
        project_root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(project_root, ignore_errors=True))

        env_file = project_root / ".env.local"
        env_file.write_text("XUEQIUTOKEN=new-token\nOTHER=value\n", encoding="utf-8")

        original = os.environ.get("XUEQIUTOKEN")
        os.environ["XUEQIUTOKEN"] = "old-token"
        self.addCleanup(
            lambda: os.environ.__setitem__("XUEQIUTOKEN", original)
            if original is not None
            else os.environ.pop("XUEQIUTOKEN", None)
        )
        self.addCleanup(lambda: os.environ.pop("OTHER", None))

        fake_env_py = project_root / "x" / "y" / "z" / "env.py"
        with patch("etl.utils.env.Path.resolve", return_value=fake_env_py):
            load_project_env(override=True, keys={"XUEQIUTOKEN"})

        self.assertEqual(os.environ.get("XUEQIUTOKEN"), "new-token")
        self.assertNotIn("OTHER", os.environ)


if __name__ == "__main__":
    unittest.main()
