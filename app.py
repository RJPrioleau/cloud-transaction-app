import os
import gspread
import csv
import webbrowser
import threading
from budget_sheet import build_transaction_batch_updates
from transaction_processor import (
    detect_account_from_filename,
    process_transactions,
    split_new_and_duplicate_transactions,
)
from upload_report import (
    UPLOAD_LOG_HEADER,
    build_transaction_report_rows,
    build_upload_log_row,
)
from flask import Flask, request, send_from_directory
from datetime import datetime
from google.oauth2.service_account import Credentials
from werkzeug.utils import secure_filename


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
    return '''
    <html>
    <head>
        <title>Transaction Processor</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f5f5f5;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }

            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                width: 400px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.1);
                text-align: center;
            }

            h2 {
                margin-bottom: 20px;
            }

            input, select {
                width: 100%;
                padding: 10px;
                margin: 10px 0;
            }

            button {
                width: 100%;
                padding: 12px;
                background-color: #333;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
            }

            button:hover {
                background-color: #555;
            }
        </style>
    </head>

    <body>

        <div class="container">
            <h2>Transaction Processor</h2>

            <form method="POST" action="/upload" enctype="multipart/form-data">

                <label>Select Month</label>
                <select name="month" required>
                    <option value="" disabled>-- Select --</option>
                    <option value="TEST" selected>TEST</option>
                    <option value="MAR">MAR</option>
                    <option value="APR">APR</option>
                    <option value="MAY">MAY</option>
                    <option value="JUN">JUN</option>
                    <option value="JUL">JUL</option>
                    <option value="AUG">AUG</option>
                    <option value="SEP">SEP</option>
                    <option value="OCT">OCT</option>
                    <option value="NOV">NOV</option>
                    <option value="DEC">DEC</option>
                </select>

                <input type="file" name="file" multiple required>

                <button type="submit">Upload Transactions</button>

            </form>
        </div>

    </body>
    </html>
    '''


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

        all_transactions = []

        for file in files:
            if file.filename == "":
                continue

            original_filename = file.filename
            extension = os.path.splitext(original_filename)[1].lower()

            if extension not in ALLOWED_EXTENSIONS:
                return "Invalid file type detected. Please upload only .csv or .xlsx files."

            safe_filename = secure_filename(original_filename)
            filepath = os.path.join(upload_folder, safe_filename)
            file.save(filepath)

            detected_account = detect_account_from_filename(original_filename)

            if detected_account is None:
                return f"Could not detect account from filename: {original_filename}"

            transactions = process_transactions(filepath, detected_account, month)
            all_transactions.extend(transactions)

        all_transactions.sort(key=lambda item: item["date"])

        # ===== GOOGLE SHEETS =====
        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        if not os.path.isfile(CREDENTIALS_FILE):
            return f"""
            <html>
            <body style="font-family: Arial; padding: 20px;">
                <h2 style="color: red;">Google credentials are missing</h2>
                <p>Expected service account credentials at: {CREDENTIALS_FILE}</p>
                <br>
                <a href="/">Back to Upload</a>
            </body>
            </html>
            """

        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)

        sheet = client.open(SPREADSHEET_NAME)
        worksheet = sheet.worksheet(month)

        existing_rows = worksheet.get_all_values()

        new_transactions, duplicate_transactions = split_new_and_duplicate_transactions(
            existing_rows[68:],
            all_transactions,
        )

        total_added_amount = sum(float(item["amount"]) for item in new_transactions)
        total_duplicate_amount = sum(float(item["amount"]) for item in duplicate_transactions)
        main_destination_row = 69

        while worksheet.acell(f"H{main_destination_row}").value:
            main_destination_row += 1

        if new_transactions:
            start_row = main_destination_row
            worksheet.batch_update(build_transaction_batch_updates(start_row, new_transactions))

        # ===== REPORT FILE =====
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"transaction_report_{month}_{timestamp}.csv"
        report_path = os.path.join(report_folder, report_filename)

        with open(report_path, mode="w", newline="", encoding="utf-8") as report_file:
            writer = csv.writer(report_file)
            writer.writerows(build_transaction_report_rows(new_transactions, duplicate_transactions))

        # ===== LOGGING =====
        log_file_path = os.path.join(log_folder, "upload_log.csv")
        file_exists = os.path.isfile(log_file_path)

        with open(log_file_path, mode="a", newline="", encoding="utf-8") as log_file:
            log_writer = csv.writer(log_file)

            if not file_exists:
                log_writer.writerow(UPLOAD_LOG_HEADER)

            log_writer.writerow(
                build_upload_log_row(
                    datetime.now(),
                    month,
                    len(files),
                    len(all_transactions),
                    len(new_transactions),
                    len(duplicate_transactions),
                    report_filename,
                )
            )

        # ===== HTML OUTPUT =====
        # ===== ADDED TRANSACTIONS =====
        if new_transactions:
            report_html = (
                f"<h3>Added Transactions</h3>"
                f"<table>"
                f"<tr><th>Date</th><th>Amount</th><th>Account</th><th>Description</th></tr>"
            )

            for item in new_transactions:
                report_html += (
                    f"<tr class='added-row'>"
                    f"<td>{item['date'].strftime('%m/%d/%Y')}</td>"
                    f"<td>{float(item['amount']):.2f}</td>"
                    f"<td>{item['account']}</td>"
                    f"<td>{item['description']}</td>"
                    f"</tr>"
                )

            report_html += "</table>"

        else:
            report_html = "<h3>Added Transactions</h3><p>No new transactions were added.</p>"

        report_html += "<h3>Skipped Duplicates</h3>"
        report_html += (
            "<table>"
            "<tr><th>Date</th><th>Amount</th><th>Account</th><th>Description</th></tr>"
        )

        for item in duplicate_transactions:
            report_html += (
                f"<tr class='duplicate-row'>"
                f"<td>{item['date'].strftime('%m/%d/%Y')}</td>"
                f"<td>{float(item['amount']):.2f}</td>"
                f"<td>{item['account']}</td>"
                f"<td>{item['description']}</td>"
                f"</tr>"
            )

        report_html += "</table>"

        return f"""
        <html>
        <head>
            <title>Transaction Report</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    background-color: #f4f6f8;
                }}

                .header {{
                    background-color: #1f2937;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    font-size: 22px;
                    font-weight: bold;
                }}

                .container {{
                    max-width: 1000px;
                    margin: 30px auto;
                    padding: 20px;
                }}

                .card {{
                    background: white;
                    padding: 25px;
                    border-radius: 10px;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.08);
                }}

                h3 {{
                    margin-top: 30px;
                    color: #333;
                }}

                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }}

                th {{
                    background-color: #111827;
                    color: white;
                    padding: 10px;
                    text-align: left;
                }}

                td {{
                    padding: 10px;
                    border-bottom: 1px solid #eee;
                }}

                tr:hover {{
                    background-color: #f9fafb;
                }}

                .summary {{
                    margin-bottom: 20px;
                    font-size: 15px;
                    color: #444;
                }}

                .buttons {{
                    margin-top: 20px;
                }}

                .button {{
                    display: inline-block;
                    background-color: #2563eb;
                    color: white;
                    padding: 10px 16px;
                    text-decoration: none;
                    border-radius: 6px;
                    margin-right: 10px;
                    font-weight: 500;
                }}

                .button.secondary {{
                    background-color: #6b7280;
                }}

                .button:hover {{
                    opacity: 0.9;
                }}
                .added-row {{
                    background-color: #ecfdf5
                }}
                .duplicate-row {{
                    background-color: #fff1f2
                }}
            </style>
        </head>
        <body>

        <div class="header">
            Transaction Processor
        </div>

        <div class="container">
            <div class="card">
                <h2>Transaction Report</h2>

                <div class="summary">
                    Processed {len(all_transactions)} transactions from {len(files)} file(s) into <strong>{month}</strong>.<br>
                    Added: <strong>{len(new_transactions)}</strong> totaling <strong>${total_added_amount:.2f}</strong> |
                    Skipped duplicates: <strong>{len(duplicate_transactions)}</strong> totaling <strong>${total_duplicate_amount:.2f}</strong>
                </div>

                {report_html}

                <div class="buttons">
                    <a class="button" href="/download/{report_filename}">Download Report</a>
                    <a class="button secondary" href="/">Back</a>
                </div>
            </div>
        </div>

        </body>
        </html>
        """

    except Exception as e:
        return f"""
        <html>
        <body style="font-family: Arial; padding: 20px;">
            <h2 style="color: red;">Something went wrong</h2>
            <p>{str(e)}</p>
            <br>
            <a href="/">Back to Upload</a>
        </body>
        </html>
        """

@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory("reports", filename, as_attachment=True)

if __name__ == "__main__":
    if os.environ.get("PORT") is None:
        threading.Timer(1.5, open_browser).start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


