from datetime import date, datetime
from sqlalchemy import select
from account_models import PaymentAccount, AccountBalance


def account_name(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise ValueError("Account name must contain 1–200 characters.")
    return value.strip()


def account_details(kind, purpose):
    if kind not in ("account", "vault"):
        raise ValueError("Choose Account or Vault.")
    if purpose is not None and not isinstance(purpose, str):
        raise ValueError("Enter a purpose with at most 200 characters.")
    purpose = (purpose or "").strip() or None
    if purpose and len(purpose) > 200:
        raise ValueError("Enter a purpose with at most 200 characters.")
    if kind == "vault" and not purpose:
        raise ValueError("Enter this vault's intended purpose.")
    return purpose


def create_account(db, name, kind="account", purpose=None):
    purpose = account_details(kind, purpose)
    record = PaymentAccount(name=account_name(name), kind=kind, purpose=purpose)
    db.add(record)
    db.flush()
    return record


def rename_account(db, record, name):
    record.name = account_name(name)
    db.flush()


def list_accounts(db):
    return list(db.scalars(select(PaymentAccount).order_by(PaymentAccount.name, PaymentAccount.id)))


def update_account(db, record, name, kind, purpose=None):
    purpose = account_details(kind, purpose)
    record.name, record.kind, record.purpose = account_name(name), kind, purpose
    db.flush()


def record_balance(db, account, amount_cents, balance_date, note=None, today=None):
    if type(amount_cents) is not int or not 0 <= amount_cents <= 9223372036854775807:
        raise ValueError("Enter a nonnegative balance in whole cents.")
    if not isinstance(balance_date, date) or isinstance(balance_date, datetime):
        raise ValueError("Enter a valid balance date.")
    if balance_date > (today or date.today()):
        raise ValueError("A recorded balance cannot have a future date.")
    if note is not None and (not isinstance(note, str) or len(note.strip()) > 200):
        raise ValueError("Balance note must contain at most 200 characters.")
    record = AccountBalance(account_id=account.id, amount_cents=amount_cents,
                            balance_date=balance_date, note=(note or "").strip() or None)
    db.add(record)
    db.flush()
    return record


def balance_history(db, account_id):
    return list(db.scalars(select(AccountBalance).where(AccountBalance.account_id == account_id)
                           .order_by(AccountBalance.balance_date.desc(), AccountBalance.id.desc())))


def latest_balances(db):
    """Newest as-of date wins; the latest entry wins corrections on that date."""
    result = {}
    for record in db.scalars(select(AccountBalance).order_by(
            AccountBalance.balance_date.desc(), AccountBalance.id.desc())):
        result.setdefault(record.account_id, record)
    return result
