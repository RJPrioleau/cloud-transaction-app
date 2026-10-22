import io
import unittest
from unittest.mock import patch

from app import app


class UploadRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_home_page_shows_upload_form(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'action="/upload"', response.data)
        self.assertIn(b'multipart/form-data', response.data)

    def test_upload_without_file_asks_for_selection(self):
        response = self.client.post("/upload", data={"month": "SEP"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_data(as_text=True),
            "No file selected. Please select at least one file.",
        )

    @patch("app.os.makedirs")
    def test_upload_rejects_unsupported_file_type(self, make_directories):
        response = self.client.post(
            "/upload",
            data={"month": "SEP", "file": (io.BytesIO(b"example"), "export.txt")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_data(as_text=True),
            "Invalid file type detected. Please upload only .csv or .xlsx files.",
        )

    @patch("werkzeug.datastructures.FileStorage.save")
    @patch("app.os.makedirs")
    def test_upload_reports_unrecognized_account(self, make_directories, save_file):
        response = self.client.post(
            "/upload",
            data={"month": "SEP", "file": (io.BytesIO(b"example"), "unknown.csv")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_data(as_text=True),
            "Could not detect account from filename: unknown.csv",
        )


if __name__ == "__main__":
    unittest.main()
