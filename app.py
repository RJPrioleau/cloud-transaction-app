import os
import webbrowser
import threading
from budget_sheet import import_transactions_to_worksheet, open_budget_worksheet
from upload_processing import process_uploaded_files
from upload_report import (
    append_upload_log_csv,
    write_transaction_report_csv,
    build_upload_log_row,
    build_transaction_report_html,
)
from flask import Flask, render_template, request, send_from_directory
from datetime import datetime


SPREADSHEET_NAME = os.environ.get(
    "BUDGET_SPREADSHEET_NAME",
    "ANNUAL-BUDGET 2026 (MAR - Present)",
)
CREDENTIALS_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}



def open_browser():
    webbrowser.open("http://127.0.0.1:5000")
app = Flask(__name__)

@app.route("/")
def home():
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload():
    try:
        files = request.files.getlist("file")

        if not files or files[0].filename == "":
            return "No file selected. Please select at least one file."

        month = request.form["month"]

        upload_folder = "uploads"
        report_folder = "reports"
        log_folder = "logs"

        os.makedirs(upload_folder, exist_ok=True)
        os.makedirs(report_folder, exist_ok=True)
        os.makedirs(log_folder, exist_ok=True)

        all_transactions, validation_error = process_uploaded_files(
            files, upload_folder, month, ALLOWED_EXTENSIONS
        )
        if validation_error is not None:
            return validation_error

        # ===== GOOGLE SHEETS =====
        if not os.path.isfile(CREDENTIALS_FILE):
            return render_template(
                "missing_credentials.html", credentials_path=CREDENTIALS_FILE
            )

        worksheet = open_budget_worksheet(CREDENTIALS_FILE, SPREADSHEET_NAME, month)

        new_transactions, duplicate_transactions = import_transactions_to_worksheet(
            worksheet,
            all_transactions,
        )

        total_added_amount = sum(float(item["amount"]) for item in new_transactions)
        total_duplicate_amount = sum(float(item["amount"]) for item in duplicate_transactions)

        # ===== REPORT FILE =====
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"transaction_report_{month}_{timestamp}.csv"
        report_path = os.path.join(report_folder, report_filename)

        write_transaction_report_csv(report_path, new_transactions, duplicate_transactions)

        # ===== LOGGING =====
        log_file_path = os.path.join(log_folder, "upload_log.csv")
        append_upload_log_csv(
            log_file_path,
            build_upload_log_row(
                datetime.now(),
                month,
                len(files),
                len(all_transactions),
                len(new_transactions),
                len(duplicate_transactions),
                report_filename,
            ),
        )

        # ===== HTML OUTPUT =====
        report_html = build_transaction_report_html(
            new_transactions,
            duplicate_transactions,
        )

        return render_template(
            "report.html",
            processed_count=len(all_transactions),
            file_count=len(files),
            month=month,
            added_count=len(new_transactions),
            duplicate_count=len(duplicate_transactions),
            total_added_amount=total_added_amount,
            total_duplicate_amount=total_duplicate_amount,
            report_html=report_html,
            report_filename=report_filename,
        )

    except Exception as e:
        return render_template(
            "upload_error.html", error_message=str(e)
        )

@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory("reports", filename, as_attachment=True)

if __name__ == "__main__":
    if os.environ.get("PORT") is None:
        threading.Timer(1.5, open_browser).start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


