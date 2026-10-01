TRANSACTION_REPORT_HEADER = ["Status", "Date", "Amount", "Account", "Description"]
UPLOAD_LOG_HEADER = [
    "Timestamp",
    "Month",
    "Files Uploaded",
    "Processed",
    "Added",
    "Duplicates",
    "Report File",
]


def build_transaction_report_rows(new_transactions, duplicate_transactions):
    rows = [TRANSACTION_REPORT_HEADER]

    for item in new_transactions:
        rows.append(build_transaction_report_row("ADDED", item))

    for item in duplicate_transactions:
        rows.append(build_transaction_report_row("DUPLICATE", item))

    return rows

def build_transaction_report_html(new_transactions, duplicate_transactions):
    if new_transactions:
        report_html = (
            "<h3>Added Transactions</h3>"
            "<table>"
            "<tr><th>Date</th><th>Amount</th><th>Account</th><th>Description</th></tr>"
        )

        report_html += build_transaction_rows_html(new_transactions, "added-row")
        report_html += "</table>"
    else:
        report_html = "<h3>Added Transactions</h3><p>No new transactions were added.</p>"

    report_html += "<h3>Skipped Duplicates</h3>"
    report_html += (
        "<table>"
        "<tr><th>Date</th><th>Amount</th><th>Account</th><th>Description</th></tr>"
    )

    report_html += build_transaction_rows_html(duplicate_transactions, "duplicate-row")
    report_html += "</table>"

    return report_html

def build_transaction_report_row(status, item):
    return [
        status,
        item["date"].strftime("%m/%d/%Y"),
        f"{float(item['amount']):.2f}",
        item["account"],
        item["description"],
    ]


def build_upload_log_row(
    timestamp,
    month,
    files_uploaded,
    processed_count,
    added_count,
    duplicate_count,
    report_filename,
):
    return [
        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        month,
        files_uploaded,
        processed_count,
        added_count,
        duplicate_count,
        report_filename,
    ]


def build_transaction_rows_html(transactions, row_class):
    rows_html = ""

    for item in transactions:
        rows_html += (
            f"<tr class='{row_class}'>"
            f"<td>{item['date'].strftime('%m/%d/%Y')}</td>"
            f"<td>{float(item['amount']):.2f}</td>"
            f"<td>{item['account']}</td>"
            f"<td>{item['description']}</td>"
            f"</tr>"
        )

    return rows_html
