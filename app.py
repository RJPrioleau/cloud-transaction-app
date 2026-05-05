from flask import Flask, request
from transaction_processor import process_transactions
import os
from openpyxl import load_workbook
import gspread
from google.oauth2.service_account import Credentials


app = Flask(__name__)

@app.route("/")
def home():
    return '''
    <h2>Upload Transactions</h2>
    
    <form method="POST" action="/upload" enctype="multipart/form-data">

    <label>Choose month:</label>
    <select name="month">
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

    <br><br>

    <label>Choose file:</label>
    <input type="file" name="file" multiple>

    <br><br>

    <button type="submit">Upload and Process</button>
</form>
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

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)

    sheet = client.open("ANNUAL-BUDGET 2026 (MAR - Present)")
    worksheet = sheet.worksheet(month)

    main_destination_row = 69

    while worksheet.acell(f"H{main_destination_row}").value:
        main_destination_row += 1

    for item in all_transactions:
        worksheet.update([[item["date"].strftime("%m/%d/%Y")]], f"H{main_destination_row}")
        worksheet.update([[item["budget_name"]]], f"I{main_destination_row}")
        worksheet.update([[item["amount"]]], f"K{main_destination_row}")
        worksheet.update([[item["account"]]], f"O{main_destination_row}")
        worksheet.update([[item["description"]]], f"P{main_destination_row}")

        main_destination_row += 1

    destination_path = os.path.join(
        r"C:\Users\Jaypr\iCloudDrive\coding_Lessons_And_Examples\Automate_The_Boring_Stuff\BudgetSheetProject",
        "ANNUAL-BUDGET 2026 (MAR - Present).xlsx"
    )

    destination_wb = load_workbook(destination_path)
    destination_ws = destination_wb[month]

    main_destination_row = 69

    while destination_ws.cell(row=main_destination_row, column=8).value is not None:
        main_destination_row += 1

    for item in all_transactions:
        destination_ws.cell(row=main_destination_row, column=8).value = item["date"]
        destination_ws.cell(row=main_destination_row, column=9).value = item["budget_name"]
        destination_ws.cell(row=main_destination_row, column=11).value = item["amount"]
        destination_ws.cell(row=main_destination_row, column=15).value = item["account"]
        destination_ws.cell(row=main_destination_row, column=16).value = item["description"]

        main_destination_row += 1

    destination_wb.save(destination_path)

    return f"Processed {len(all_transactions)} transactions from {len(files)} file(s) into {month}."

if __name__ == "__main__":
    app.run(debug=True)

