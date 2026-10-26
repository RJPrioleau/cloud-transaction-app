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

    @patch("app.open_budget_worksheet")
    @patch("app.os.makedirs")
    @patch("app.process_uploaded_files", return_value=([], None))
    def test_missing_credentials_shows_configured_path_without_connecting(
        self, process_files, make_directories, open_worksheet
    ):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_path = str(Path(temporary_directory) / "missing-credentials.json")
            with patch("app.CREDENTIALS_FILE", missing_path):
                response = self.client.post(
                    "/upload",
                    data={
                        "month": "SEP",
                        "file": (io.BytesIO(b"example"), "SoFi Checking-2695.csv"),
                    },
                )

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Google credentials are missing", html)
        self.assertIn(f"Expected service account credentials at: {missing_path}", html)
        self.assertIn('<a href="/">Back to Upload</a>', html)
        open_worksheet.assert_not_called()

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

    @patch("budget_sheet.gspread.authorize")
    @patch("budget_sheet.Credentials.from_service_account_file")
    def test_multiple_files_are_sorted_and_deduplicated_together(
        self, load_credentials, authorize
    ):
        worksheet = Mock()
        worksheet.get_all_values.return_value = []
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
                            "file": [
                                (
                                    io.BytesIO(
                                        b"Date,Description,Amount\n"
                                        b"09/03/2026,SHELL SERVICE,-42.10\n"
                                    ),
                                    "SoFi Checking-2695-first.csv",
                                ),
                                (
                                    io.BytesIO(
                                        b"Date,Description,Amount\n"
                                        b"09/01/2026,APPLE.COM/BILL,-5.99\n"
                                        b"09/03/2026,SHELL SERVICE,-42.10\n"
                                    ),
                                    "SoFi Checking-2695-second.csv",
                                ),
                            ],
                        },
                    )

                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn("Processed 3 transactions from 2 file(s)", html)
                self.assertIn("Added: <strong>2</strong>", html)
                self.assertIn("Skipped duplicates: <strong>1</strong>", html)
                worksheet.batch_update.assert_called_once_with([
                    {"range": "H69:H70", "values": [["09/01/2026"], ["09/03/2026"]]},
                    {"range": "I69:I70", "values": [["Apple Music"], ["Gas"]]},
                    {"range": "K69:K70", "values": [[5.99], [42.1]]},
                    {"range": "O69:O70", "values": [["SoFi Checking (2695)"]] * 2},
                    {"range": "P69:P70", "values": [["APPLE.COM/BILL"], ["SHELL SERVICE"]]},
                ])
                report_paths = list(Path("reports").glob("*.csv"))
                self.assertEqual(len(report_paths), 1)
                with report_paths[0].open(newline="", encoding="utf-8") as report_file:
                    rows = list(csv.reader(report_file))
                self.assertEqual([row[0] for row in rows[1:]], ["ADDED", "ADDED", "DUPLICATE"])
                self.assertEqual([row[1] for row in rows[1:]], ["09/01/2026", "09/03/2026", "09/03/2026"])
                with Path("logs/upload_log.csv").open(newline="", encoding="utf-8") as log_file:
                    log_rows = list(csv.reader(log_file))
                self.assertEqual(len(log_rows), 2)
                self.assertEqual(log_rows[1][1:6], ["SEP", "2", "3", "2", "1"])
            finally:
                os.chdir(original_directory)

    @patch("budget_sheet.gspread.authorize")
    @patch("budget_sheet.Credentials.from_service_account_file")
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
                self.assertIn('<a href="/">Back to Upload</a>', html)
                self.assertNotIn("Download Report", html)
                worksheet.batch_update.assert_called_once()
                self.assertEqual(list(Path("reports").iterdir()), [])
                self.assertEqual(list(Path("logs").iterdir()), [])
            finally:
                os.chdir(original_directory)

    @patch("budget_sheet.gspread.authorize")
    @patch("budget_sheet.Credentials.from_service_account_file")
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

    @patch("budget_sheet.gspread.authorize")
    @patch("budget_sheet.Credentials.from_service_account_file")
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
                self.assertIn("totaling <strong>$42.10</strong>", html)
                self.assertIn("totaling <strong>$5.99</strong>", html)
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


class ResetTestRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def confirmation_data(self):
        response = self.client.get("/reset-test")
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as state:
            token = state["reset_test_token"]
        return {"token": token, "confirmed": "yes"}

    @patch("app.open_budget_worksheet")
    def test_confirmation_page_never_connects_to_sheets(self, open_worksheet):
        response = self.client.get("/reset-test")
        self.assertIn(b"69", response.data)
        self.assertIn(b"383", response.data)
        self.assertIn(b'name="confirmed"', response.data)
        open_worksheet.assert_not_called()

    @patch("app.open_budget_worksheet")
    def test_unconfirmed_invalid_and_live_month_requests_never_connect(self, open_worksheet):
        self.assertEqual(self.client.post("/reset-test", data={}).status_code, 400)
        for case in ("missing_token", "wrong_token", "missing_confirmation", "live_month"):
            with self.subTest(case=case):
                data = self.confirmation_data()
                if case == "missing_token":
                    data.pop("token")
                elif case == "wrong_token":
                    data["token"] = "wrong"
                elif case == "missing_confirmation":
                    data.pop("confirmed")
                else:
                    data["month"] = "SEP"
                self.assertEqual(self.client.post("/reset-test", data=data).status_code, 400)
        open_worksheet.assert_not_called()

    @patch("app.clear_test_imports", return_value=5)
    @patch("app.open_budget_worksheet")
    @patch("app.os.path.isfile", return_value=True)
    def test_confirmed_reset_targets_test_and_cannot_be_replayed(
        self, file_exists, open_worksheet, clear_imports
    ):
        from app import CREDENTIALS_FILE, SPREADSHEET_NAME
        data = self.confirmation_data()
        response = self.client.post("/reset-test", data=data)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"have been cleared", response.data)
        open_worksheet.assert_called_once_with(CREDENTIALS_FILE, SPREADSHEET_NAME, "TEST")
        clear_imports.assert_called_once_with(open_worksheet.return_value)
        self.assertEqual(self.client.post("/reset-test", data=data).status_code, 400)
        clear_imports.assert_called_once()

    @patch("app.clear_test_imports", side_effect=RuntimeError("Reset rejected"))
    @patch("app.open_budget_worksheet")
    @patch("app.os.path.isfile", return_value=True)
    def test_failed_reset_does_not_report_success(self, file_exists, open_worksheet, clear_imports):
        data = self.confirmation_data()
        response = self.client.post("/reset-test", data=data)
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Reset rejected", response.data)
        self.assertNotIn(b"have been cleared", response.data)


class ReportDownloadTests(unittest.TestCase):
    def test_download_returns_csv_contents_as_attachment(self):
        report_bytes = b"Status,Date,Amount,Account,Description\r\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_folder = Path(temporary_directory) / "reports"
            report_folder.mkdir()
            (report_folder / "example.csv").write_bytes(report_bytes)

            with patch.object(app, "root_path", temporary_directory):
                with app.test_client().get("/download/example.csv") as response:
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data, report_bytes)
                    self.assertEqual(
                        response.headers["Content-Disposition"],
                        "attachment; filename=example.csv",
                    )

    def test_download_rejects_missing_report_and_parent_directory_path(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            (Path(temporary_directory) / "reports").mkdir()
            (Path(temporary_directory) / "outside.csv").write_text(
                "outside report folder", encoding="utf-8"
            )

            with patch.object(app, "root_path", temporary_directory):
                for url in ("/download/missing.csv", "/download/..%2Foutside.csv"):
                    with self.subTest(url=url):
                        with app.test_client().get(url) as response:
                            self.assertEqual(response.status_code, 404)
                            self.assertNotIn(b"outside report folder", response.data)


if __name__ == "__main__":
    unittest.main()
