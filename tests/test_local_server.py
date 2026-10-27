import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from local_server import serve_local, source_fingerprint


class LocalServerTests(unittest.TestCase):
    def test_fingerprint_tracks_code_and_templates_but_excludes_private_runtime_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "templates").mkdir()
            source = root / "app.py"
            source.write_text("original", encoding="utf-8")
            initial = source_fingerprint(root)
            (root / "credentials.json").write_text("private placeholder", encoding="utf-8")
            (root / "logs").mkdir()
            (root / "logs/server.log").write_text("runtime output", encoding="utf-8")
            self.assertEqual(source_fingerprint(root), initial)
            source.write_text("changed", encoding="utf-8")
            changed = source_fingerprint(root)
            self.assertNotEqual(changed, initial)
            (root / "templates/page.html").write_text("new page", encoding="utf-8")
            self.assertNotEqual(source_fingerprint(root), changed)

    @patch("local_server.ExclusiveLocalServer")
    @patch("builtins.print")
    def test_status_reports_startup_fingerprint_and_server_closes_on_exit(self, print_output, server_class):
        app = Flask(__name__)
        with patch("local_server.source_fingerprint", return_value="startup-version") as fingerprint:
            serve_local(app)
            with patch("local_server.source_fingerprint", return_value="edited-files"):
                response = app.test_client().get("/_local/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["fingerprint"], "startup-version")
        self.assertEqual(response.json["application"], "cloud-transaction-app")
        fingerprint.assert_called_once_with()
        server_class.assert_called_once_with("127.0.0.1", 5000, app)
        server_class.return_value.server_close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
