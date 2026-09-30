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
