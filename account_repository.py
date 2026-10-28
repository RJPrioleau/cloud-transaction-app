from sqlalchemy import select
from account_models import PaymentAccount


def account_name(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise ValueError("Account name must contain 1–200 characters.")
    return value.strip()


def create_account(db, name):
    record = PaymentAccount(name=account_name(name))
    db.add(record)
    db.flush()
    return record


def rename_account(db, record, name):
    record.name = account_name(name)
    db.flush()


def list_accounts(db):
    return list(db.scalars(select(PaymentAccount).order_by(PaymentAccount.name, PaymentAccount.id)))
