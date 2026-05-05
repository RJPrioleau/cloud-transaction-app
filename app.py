import os
import gspread
import csv
import webbrowser
from transaction_processor import process_transactions
from flask import Flask, request, render_template, send_from_directory
from openpyxl import load_workbook
from datetime import datetime
from google.oauth2.service_account import Credentials



def normalize_amount(value):
    value = str(value).replace("$", "").replace(",", "").strip()

    try:
        return f"{float(value):.2f}"
    except ValueError:
        return value.lower()


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
                    <option value="">-- Select --</option>
                    <option value="TEST">TEST</option>
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

def detect_account_from_filename(filename):
    if "Savings•3475" in filename:
        return "SoFi Savings (3475)"

    if "Checking•2695" in filename:
        return "SoFi Checking (2695)"

    return None



@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("file")

    if not files or files[0].filename == "":
        return "No file selected. Please select at least one file."

    month = request.form["month"]

    upload_folder = "uploads"
    report_folder = "reports"
    os.makedirs(report_folder, exist_ok=True)


    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    total_count = 0
    all_transactions = []
    for file in files:

        if file.filename == "":
            continue

        if not (file.filename.endswith(".csv") or file.filename.endswith(".xlsx")):
            return "Invalid file type detected. Please upload only .csv or .xlsx files."

        filepath = os.path.join(upload_folder, file.filename)
        file.save(filepath)

        detected_account = detect_account_from_filename(file.filename)

        if detected_account is None:
            return f"Could not detect account from filename: {file.filename}"

        transactions = process_transactions(filepath, detected_account, month)
        all_transactions.extend(transactions)
    all_transactions.sort(key=lambda item: item["date"])

    existing_keys = set()
    new_transactions = []
    duplicate_transactions = []

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)

    sheet = client.open("ANNUAL-BUDGET 2026 (MAR - Present)")
    worksheet = sheet.worksheet(month)

    existing_keys = set()

    existing_rows = worksheet.get_all_values()

    for row in existing_rows[68:]:
        if len(row) < 16:
            continue

        existing_date = row[7]
        existing_amount = normalize_amount(row[10])
        existing_account = row[14]
        existing_description = row[15]

        key = (
            str(existing_date).strip().lower(),
            str(existing_amount).strip().lower(),
            str(existing_account).strip().lower(),
            str(existing_description).strip().lower(),
        )

        existing_keys.add(key)

    new_transactions = []
    duplicate_transactions = []

    for item in all_transactions:
        key = (
            item["date"].strftime("%m/%d/%Y").strip().lower(),
            normalize_amount(item["amount"]),
            str(item["account"]).strip().lower(),
            str(item["description"]).strip().lower(),
        )

        if key in existing_keys:
            duplicate_transactions.append(item)
        else:
            new_transactions.append(item)
            existing_keys.add(key)

    main_destination_row = 69

    while worksheet.acell(f"H{main_destination_row}").value:
        main_destination_row += 1

    rows_to_write = []

    for item in new_transactions:
        rows_to_write.append([
            item["date"].strftime("%m/%d/%Y"),
            item["budget_name"],
            "",
            item["amount"],
            "",
            "",
            "",
            item["account"],
            item["description"],
        ])

    if rows_to_write:
        worksheet.update(
            rows_to_write,
            f"H{main_destination_row}:P{main_destination_row + len(rows_to_write) - 1}"
        )

    destination_path = os.path.join(
        r"C:\Users\Jaypr\iCloudDrive\coding_Lessons_And_Examples\Automate_The_Boring_Stuff\BudgetSheetProject",
        "ANNUAL-BUDGET 2026 (MAR - Present).xlsx"
    )

    destination_wb = load_workbook(destination_path)
    destination_ws = destination_wb[month]

    main_destination_row = 69

    while destination_ws.cell(row=main_destination_row, column=8).value is not None:
        main_destination_row += 1

    for item in new_transactions:
        destination_ws.cell(row=main_destination_row, column=8).value = item["date"]
        destination_ws.cell(row=main_destination_row, column=9).value = item["budget_name"]
        destination_ws.cell(row=main_destination_row, column=11).value = item["amount"]
        destination_ws.cell(row=main_destination_row, column=15).value = item["account"]
        destination_ws.cell(row=main_destination_row, column=16).value = item["description"]

        main_destination_row += 1

    destination_wb.save(destination_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"transaction_report_{month}_{timestamp}.csv"
    report_path = os.path.join(report_folder, report_filename)

    report_html = (
        f"<p>Processed {len(all_transactions)} transactions from {len(files)} file(s) into {month}.</p>"
        f"<p>Added: {len(new_transactions)}<br>"
        f"Skipped duplicates: {len(duplicate_transactions)}</p>"
        f"<h3>Added Transactions</h3>"
        f"<table>"
        f"<tr><th>Date</th><th>Amount</th><th>Account</th><th>Description</th></tr>"
    )

    for item in new_transactions:
        report_html += (
            f"<tr>"
            f"<td>{item['date'].strftime('%m/%d/%Y')}</td>"
            f"<td>{float(item['amount']):.2f}</td>"
            f"<td>{item['account']}</td>"
            f"<td>{item['description']}</td>"
            f"</tr>"
        )

    report_html += "</table>"

    report_html += "<h3>Skipped Duplicates</h3>"
    report_html += (
        "<table>"
        "<tr><th>Date</th><th>Amount</th><th>Account</th><th>Description</th></tr>"
    )

    for item in duplicate_transactions:
        report_html += (
            f"<tr>"
            f"<td>{item['date'].strftime('%m/%d/%Y')}</td>"
            f"<td>{float(item['amount']):.2f}</td>"
            f"<td>{item['account']}</td>"
            f"<td>{item['description']}</td>"
            f"</tr>"
        )

    report_html += "</table>"

    with open(report_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        # Header
        writer.writerow(["Status", "Date", "Amount", "Account", "Description"])

        # Added transactions
        for item in new_transactions:
            writer.writerow([
                "ADDED",
                item["date"].strftime("%m/%d/%Y"),
                f"{float(item['amount']):.2f}",
                item["account"],
                item["description"],
            ])

        # Duplicate transactions
        for item in duplicate_transactions:
            writer.writerow([
                "DUPLICATE",
                item["date"].strftime("%m/%d/%Y"),
                f"{float(item['amount']):.2f}",
                item["account"],
                item["description"],
            ])

    report_html += f'<br><a class="button" href="/download/{report_filename}">Download Report</a>'
    report_html += '<br><br><a class="button" href="/">Back to Upload</a>'

    return f"""
    <html>
    <head>
        <title>Transaction Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                padding: 30px;
                background-color: #f5f5f5;
            }}
            h2 {{
                color: #333;
            }}
            .section {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                max-width: 1000px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
                margin-bottom: 25px;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 10px;
                text-align: left;
            }}
            th {{
                background-color: #eee
            }}
            .button {{
                display: inline-block;
                background-color: #333;
                color: white;
                padding: 10px 14px;
                text-decoration: none;
                border-radius: 6px;
                margin-top: 10px;
            }}
            .button:hover {{
                background-color: #555;
            }}
        </style>
    </head>
    <body>

    <h2>Transaction Report</h2>

    <div class="section">
    {report_html}
    </div>

    </body>
    </html>
    """

@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory("reports", filename, as_attachment=True)

if __name__ == "__main__":
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        webbrowser.open("http://127.0.0.1:5000")

    app.run(debug=True)

