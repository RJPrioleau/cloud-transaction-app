import csv
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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

    @patch("app.gspread.authorize")
    @patch("app.Credentials.from_service_account_file")
    def test_failed_sheet_write_does_not_create_report_or_log(
        self, load_credentials, authorize
    ):
        worksheet = Mock()
        worksheet.get_all_values.return_value = []
        worksheet.acell.return_value.value = ""
        worksheet.batch_update.side_effect = RuntimeError("Worksheet write rejected")
        authorize.return_value.open.return_value.worksheet.return_value = worksheet

        original_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary_directory:
            try:
                os.chdir(temporary_directory)
                Path("credentials.json").write_text("{}", encoding="utf-8")
                with patch("app.CREDENTIALS_FILE", "credentials.json"):
                    response = self.client.post(
                        "/upload",
                        data={
                            "month": "SEP",
                            "file": (
                                io.BytesIO(
                                    b"Date,Description,Amount\n"
                                    b"09/01/2026,SHELL SERVICE,-42.10\n"
                                ),
                                "SoFi Checking-2695.csv",
                            ),
                        },
                    )

                html = response.get_data(as_text=True)
                self.assertIn("Something went wrong", html)
                self.assertIn("Worksheet write rejected", html)
                self.assertNotIn("Download Report", html)
                worksheet.batch_update.assert_called_once()
                self.assertEqual(list(Path("reports").iterdir()), [])
                self.assertEqual(list(Path("logs").iterdir()), [])
            finally:
                os.chdir(original_directory)

    @patch("app.gspread.authorize")
    @patch("app.Credentials.from_service_account_file")
    def test_duplicate_only_upload_skips_sheet_write_and_still_produces_report(
        self, load_credentials, authorize
    ):
        existing_row = [""] * 16
        existing_row[7] = "09/02/2026"
        existing_row[10] = "5.99"
        existing_row[14] = "SoFi Checking (2695)"
        existing_row[15] = "APPLE.COM/BILL"
        worksheet = Mock()
        worksheet.get_all_values.return_value = [[] for _ in range(68)] + [existing_row]
        worksheet.acell.return_value.value = ""
        authorize.return_value.open.return_value.worksheet.return_value = worksheet

        original_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary_directory:
            try:
                os.chdir(temporary_directory)
                Path("credentials.json").write_text("{}", encoding="utf-8")
                with patch("app.CREDENTIALS_FILE", "credentials.json"):
                    response = self.client.post(
                        "/upload",
                        data={
                            "month": "SEP",
                            "file": (
                                io.BytesIO(
                                    b"Date,Description,Amount\n"
                                    b"09/02/2026,APPLE.COM/BILL,-5.99\n"
                                ),
                                "SoFi Checking-2695.csv",
                            ),
                        },
                    )

                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn("Processed 1 transactions", html)
                self.assertIn("Added: <strong>0</strong>", html)
                self.assertIn("Skipped duplicates: <strong>1</strong>", html)
                self.assertIn("No new transactions were added.", html)
                self.assertNotIn("<tr class='added-row'>", html)
                self.assertIn("<tr class='duplicate-row'>", html)
                worksheet.batch_update.assert_not_called()

                report_paths = list(Path("reports").glob("*.csv"))
                self.assertEqual(len(report_paths), 1)
                with report_paths[0].open(newline="", encoding="utf-8") as report_file:
                    self.assertEqual(list(csv.reader(report_file)), [
                        ["Status", "Date", "Amount", "Account", "Description"],
                        ["DUPLICATE", "09/02/2026", "5.99", "SoFi Checking (2695)", "APPLE.COM/BILL"],
                    ])
                with Path("logs/upload_log.csv").open(newline="", encoding="utf-8") as log_file:
                    log_rows = list(csv.reader(log_file))
                self.assertEqual(len(log_rows), 2)
                self.assertEqual(log_rows[1][1:6], ["SEP", "1", "1", "0", "1"])
                self.assertEqual(log_rows[1][6], report_paths[0].name)
            finally:
                os.chdir(original_directory)

    @patch("app.gspread.authorize")
    @patch("app.Credentials.from_service_account_file")
    def test_upload_writes_only_new_transactions_and_reports_duplicates(
        self, load_credentials, authorize
    ):
        existing_row = [""] * 16
        existing_row[7] = "09/02/2026"
        existing_row[10] = "5.99"
        existing_row[14] = "SoFi Checking (2695)"
        existing_row[15] = "APPLE.COM/BILL"
        worksheet = Mock()
        worksheet.get_all_values.return_value = [[] for _ in range(68)] + [existing_row]
        worksheet.acell.return_value.value = ""
        authorize.return_value.open.return_value.worksheet.return_value = worksheet

        bank_export = (
            b"Date,Description,Amount\n"
            b"09/02/2026,APPLE.COM/BILL,-5.99\n"
            b"09/01/2026,SHELL SERVICE,-42.10\n"
        )
        original_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary_directory:
            try:
                os.chdir(temporary_directory)
                # Authentication is mocked; this placeholder satisfies the local file check.
                Path("credentials.json").write_text("{}", encoding="utf-8")
                with patch("app.CREDENTIALS_FILE", "credentials.json"):
                    response = self.client.post(
                        "/upload",
                        data={
                            "month": "SEP",
                            "file": (io.BytesIO(bank_export), "SoFi Checking-2695.csv"),
                        },
                    )

                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn("Processed 2 transactions", html)
                self.assertIn("Added: <strong>1</strong>", html)
                self.assertIn("Skipped duplicates: <strong>1</strong>", html)
                self.assertIn("<td>SHELL SERVICE</td>", html)
                self.assertIn("<td>APPLE.COM/BILL</td>", html)

                worksheet.batch_update.assert_called_once_with([
                    {"range": "H69:H69", "values": [["09/01/2026"]]},
                    {"range": "I69:I69", "values": [["Gas"]]},
                    {"range": "K69:K69", "values": [[42.1]]},
                    {"range": "O69:O69", "values": [["SoFi Checking (2695)"]]},
                    {"range": "P69:P69", "values": [["SHELL SERVICE"]]},
                ])
                report_paths = list(Path("reports").glob("*.csv"))
                self.assertEqual(len(report_paths), 1)
                with report_paths[0].open(newline="", encoding="utf-8") as report_file:
                    self.assertEqual(list(csv.reader(report_file)), [
                        ["Status", "Date", "Amount", "Account", "Description"],
                        ["ADDED", "09/01/2026", "42.10", "SoFi Checking (2695)", "SHELL SERVICE"],
                        ["DUPLICATE", "09/02/2026", "5.99", "SoFi Checking (2695)", "APPLE.COM/BILL"],
                    ])
                with Path("logs/upload_log.csv").open(newline="", encoding="utf-8") as log_file:
                    log_rows = list(csv.reader(log_file))
                self.assertEqual(len(log_rows), 2)
                self.assertEqual(log_rows[1][1:6], ["SEP", "1", "2", "1", "1"])
                self.assertEqual(log_rows[1][6], report_paths[0].name)
                self.assertIn(f'/download/{report_paths[0].name}', html)
            finally:
                os.chdir(original_directory)


if __name__ == "__main__":
    unittest.main()
