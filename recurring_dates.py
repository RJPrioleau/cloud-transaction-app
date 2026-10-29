"""Calendar anchors shared by bill and subscription schedules."""
import calendar
from datetime import date


def scheduled_dates(anchor, frequency, start, end):
    """Yield dates in [start, end), always calculated from the original anchor."""
    if frequency not in ("monthly", "yearly"):
        raise ValueError("Choose Monthly or Yearly recurrence.")
    step = 1 if frequency == "monthly" else 12
    first_month = anchor.year * 12 + anchor.month - 1
    start_month = start.year * 12 + start.month - 1
    index = max(0, (start_month - first_month) // step)
    while True:
        year, month = divmod(first_month + index * step, 12)
        month += 1
        if year > 9999:
            return
        day = date(year, month, min(anchor.day, calendar.monthrange(year, month)[1]))
        if day >= end:
            return
        if day >= start:
            yield day
        index += 1
