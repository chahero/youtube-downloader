import os
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class ManageScriptTests(unittest.TestCase):
    def copy_project_files(self, temp_dir):
        root = Path(temp_dir)
        shutil.copy(Path("manage.sh"), root / "manage.sh")
        return root

    def run_manage(self, root, action, env=None):
        if shutil.which("bash") is None:
            self.skipTest("bash is required to exercise manage.sh")

        return subprocess.run(
            ["bash", "manage.sh", action],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_script_declares_service_monitor_actions(self):
        script = Path("manage.sh").read_text(encoding="utf-8")

        self.assertIn("redeploy()", script)
        self.assertIn("logs()", script)
        self.assertIn("health()", script)
        self.assertIn("redeploy)", script)
        self.assertIn("logs)", script)
        self.assertIn("health)", script)

    def test_health_checks_configured_local_port(self):
        with TemporaryDirectory() as temp_dir:
            root = self.copy_project_files(temp_dir)
            (root / ".env").write_text("PORT=5012\n", encoding="utf-8")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            curl_log = root / "curl-args.txt"
            (bin_dir / "curl").write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$@\" > curl-args.txt\n",
                encoding="utf-8",
            )
            os.chmod(bin_dir / "curl", 0o755)
            env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}

            result = self.run_manage(root, "health", env=env)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("OK http://127.0.0.1:5012/", result.stdout)
            self.assertIn("http://127.0.0.1:5012/", curl_log.read_text(encoding="utf-8"))

    def test_logs_prints_app_and_error_logs(self):
        with TemporaryDirectory() as temp_dir:
            root = self.copy_project_files(temp_dir)
            log_dir = root / "logs"
            log_dir.mkdir()
            (log_dir / "app.log").write_text("app line\n", encoding="utf-8")
            (log_dir / "error.log").write_text("error line\n", encoding="utf-8")

            result = self.run_manage(root, "logs")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("[app.log]", result.stdout)
            self.assertIn("app line", result.stdout)
            self.assertIn("[error.log]", result.stdout)
            self.assertIn("error line", result.stdout)

    def test_usage_lists_service_monitor_actions(self):
        with TemporaryDirectory() as temp_dir:
            root = self.copy_project_files(temp_dir)

            result = self.run_manage(root, "unsupported")

            self.assertEqual(result.returncode, 1)
            self.assertIn("redeploy", result.stdout)
            self.assertIn("logs", result.stdout)
            self.assertIn("health", result.stdout)


if __name__ == "__main__":
    unittest.main()
