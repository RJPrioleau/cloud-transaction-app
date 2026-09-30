TRANSACTION_REPORT_HEADER = ["Status", "Date", "Amount", "Account", "Description"]


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
