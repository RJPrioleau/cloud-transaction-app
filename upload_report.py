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
