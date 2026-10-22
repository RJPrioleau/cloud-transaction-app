import os

from werkzeug.utils import secure_filename

from transaction_processor import detect_account_from_filename, process_transactions


def process_uploaded_files(files, upload_folder, month, allowed_extensions):
    """Return (sorted transactions, None), or ([], validation message).

    The caller creates the upload folder. Files are saved as they are processed;
    validation errors do not remove files saved earlier in the request.
    Parsing and storage exceptions propagate to the caller.
    """
    all_transactions = []

    for file in files:
        if file.filename == "":
            continue

        original_filename = file.filename
        extension = os.path.splitext(original_filename)[1].lower()

        if extension not in allowed_extensions:
            return [], "Invalid file type detected. Please upload only .csv or .xlsx files."

        safe_filename = secure_filename(original_filename)
        filepath = os.path.join(upload_folder, safe_filename)
        file.save(filepath)

        detected_account = detect_account_from_filename(original_filename)
        if detected_account is None:
            return [], f"Could not detect account from filename: {original_filename}"

        transactions = process_transactions(filepath, detected_account, month)
        all_transactions.extend(transactions)

    all_transactions.sort(key=lambda item: item["date"])
    return all_transactions, None
