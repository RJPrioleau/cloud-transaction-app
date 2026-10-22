import gspread
from google.oauth2.service_account import Credentials

from transaction_processor import split_new_and_duplicate_transactions


def open_budget_worksheet(credentials_path, spreadsheet_name, month):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    client = gspread.authorize(credentials)
    spreadsheet = client.open(spreadsheet_name)
    return spreadsheet.worksheet(month)


def import_transactions_to_worksheet(worksheet, transactions):
    existing_rows = worksheet.get_all_values()
    new_transactions, duplicate_transactions = split_new_and_duplicate_transactions(
        existing_rows[68:], transactions
    )
    destination_row = find_first_empty_transaction_row(worksheet)

    if new_transactions:
        worksheet.batch_update(
            build_transaction_batch_updates(destination_row, new_transactions)
        )

    return new_transactions, duplicate_transactions


def find_first_empty_transaction_row(worksheet, start_row=69):
    current_row = start_row

    while worksheet.acell(f"H{current_row}").value:
        current_row += 1

    return current_row


def build_transaction_batch_updates(start_row, transactions):
    if not transactions:
        return []

    end_row = start_row + len(transactions) - 1

    return [
        {
            "range": f"H{start_row}:H{end_row}",
            "values": [[item["date"].strftime("%m/%d/%Y")] for item in transactions],
        },
        {
            "range": f"I{start_row}:I{end_row}",
            "values": [[item["budget_name"]] for item in transactions],
        },
        {
            "range": f"K{start_row}:K{end_row}",
            "values": [[item["amount"]] for item in transactions],
        },
        {
            "range": f"O{start_row}:O{end_row}",
            "values": [[item["account"]] for item in transactions],
        },
        {
            "range": f"P{start_row}:P{end_row}",
            "values": [[item["description"]] for item in transactions],
        },
    ]
