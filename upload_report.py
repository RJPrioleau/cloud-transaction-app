import csv
import os
from decimal import Decimal


TRANSACTION_REPORT_HEADER = ["Status", "Date", "Amount", "Account", "Description", "Budget Name"]
UPLOAD_LOG_HEADER = [
    "Timestamp",
    "Month",
    "Files Uploaded",
    "Processed",
    "Added",
    "Duplicates",
    "Report File",
]


def build_budget_summary(new_transactions, duplicate_transactions):
    return _build_grouped_summary(new_transactions, duplicate_transactions, "budget_name")


def build_misc_review(new_transactions, duplicate_transactions):
    return _build_grouped_summary(
        [item for item in new_transactions if item["budget_name"] == "MISC"],
        [item for item in duplicate_transactions if item["budget_name"] == "MISC"],
        "description",
    )


def _build_grouped_summary(new_transactions, duplicate_transactions, group_field):
    summaries = {}
    for status, transactions in (("added", new_transactions), ("duplicate", duplicate_transactions)):
        for item in transactions:
            name = item[group_field]
            if name not in summaries:
                summaries[name] = {
                    group_field: name,
                    "added_count": 0,
                    "added_total": Decimal("0"),
                    "duplicate_count": 0,
                    "duplicate_total": Decimal("0"),
                }
            summaries[name][f"{status}_count"] += 1
            summaries[name][f"{status}_total"] += Decimal(str(item["amount"]))
    return sorted(summaries.values(), key=lambda row: (row[group_field].casefold(), row[group_field]))


def append_upload_log_csv(log_path, row):
    file_exists = os.path.isfile(log_path)

    with open(log_path, mode="a", newline="", encoding="utf-8") as log_file:
        writer = csv.writer(log_file)
        if not file_exists:
            writer.writerow(UPLOAD_LOG_HEADER)
        writer.writerow(row)


def write_transaction_report_csv(report_path, new_transactions, duplicate_transactions):
    with open(report_path, mode="w", newline="", encoding="utf-8") as report_file:
        writer = csv.writer(report_file)
        writer.writerows(build_transaction_report_rows(new_transactions, duplicate_transactions))


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
            "<tr><th>Date</th><th>Amount</th><th>Account</th><th>Description</th><th>Budget Name</th></tr>"
        )

        report_html += build_transaction_rows_html(new_transactions, "added-row")
        report_html += "</table>"
    else:
        report_html = "<h3>Added Transactions</h3><p>No new transactions were added.</p>"

    report_html += "<h3>Skipped Duplicates</h3>"
    report_html += (
        "<table>"
        "<tr><th>Date</th><th>Amount</th><th>Account</th><th>Description</th><th>Budget Name</th></tr>"
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
        item["budget_name"],
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
            f"<td>{item['budget_name']}</td>"
            f"</tr>"
        )

    return rows_html
