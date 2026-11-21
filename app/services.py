from collections import Counter, deque
from datetime import date
from enum import StrEnum
from dataclasses import dataclass
from . import repository

CATEGORIES = ("Process", "Quality", "Technology", "Customer")
PRIORITIES = ("Low", "Medium", "High")


class Status(StrEnum):
    NEW = "New"
    IN_PROGRESS = "In Progress"
    DONE = "Done"


STATUSES = tuple(status.value for status in Status)


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]


def validate_item(
    title: str, category: str, priority: str, description: str = "", due_date: str | None = None
) -> ValidationResult:
    errors = []
    clean_title = title.strip()
    if not 3 <= len(clean_title) <= 100:
        errors.append("Title must contain between 3 and 100 characters.")
    if category not in CATEGORIES:
        errors.append("Choose a valid category.")
    if priority not in PRIORITIES:
        errors.append("Choose a valid priority.")
    if len(description) > 5000:
        errors.append("Description must contain at most 5000 characters.")
    if due_date:
        try:
            parsed = date.fromisoformat(due_date)
            if parsed.isoformat() != due_date:
                raise ValueError("Use ISO date format")
        except ValueError:
            errors.append("Enter a valid due date.")
    return ValidationResult(not errors, tuple(errors))


def create_item(title, category, priority, description="", due_date=None):
    result = validate_item(title, category, priority, description, due_date)
    if not result.valid:
        return None, result
    item_id = repository.add_item(title.strip(), category, priority, description.strip(), due_date or None)
    return item_id, result


def change_status(item_id: int, status: str) -> None:
    if status not in STATUSES:
        raise ValueError("Unsupported status")
    item = repository.get_item(item_id)
    if item is None or item["archived"]:
        raise LookupError("Improvement item not found")
    if item["status"] == status:
        return
    if not repository.update_status(item_id, status):
        raise LookupError("Improvement item not found")


def dashboard(status=None, include_items=True):
    items = repository.list_items(status) if include_items else []
    grouped_rows = repository.summary_counts()
    status_totals = Counter()
    priority_totals = Counter()
    for row in grouped_rows:
        status_totals[row["status"]] += row["total"]
        priority_totals[row["priority"]] += row["total"]
    recent_titles = deque((row["title"] for row in items[:5]), maxlen=5)
    return {
        "items": items,
        "status_totals": dict(status_totals),
        "priority_totals": dict(priority_totals),
        "recent_titles": list(recent_titles),
    }


BANKING_FIELDS = {
    "business_area": ("Business area", ("Retail banking", "Business and commercial banking", "Insurance, pensions and investments", "Group operations", "Technology")),
    "customer_journey": ("Customer journey", ()),
    "channel": ("Affected channel", ("Mobile app", "Online banking", "Branch", "Telephone", "Colleague operations", "Multiple channels")),
    "owner": ("Accountable owner / team", ()),
    "risk_category": ("Risk category", ("Customer harm", "Operational resilience", "Fraud and financial crime", "Data and privacy", "Conduct", "Process and controls")),
    "customer_outcome": ("Expected customer or colleague outcome", ()),
    "success_measure": ("Success measure", ()),
    "baseline": ("Baseline", ()),
    "target": ("Target", ()),
    "actual": ("Actual result / evidence reference", ()),
    "approval_stage": ("Governance stage", ("Submitted", "Assessed", "Approved", "Implemented", "Validated")),
    "approver": ("Approver / review team", ()),
    "review_date": ("Review date", ()),
}


def validate_banking(values):
    errors = []
    for key, (label, options) in BANKING_FIELDS.items():
        value = values.get(key, "")
        if len(value) > 1000:
            errors.append(f"{label} must contain at most 1,000 characters.")
        if options and value and value not in options:
            errors.append(f"Choose a valid {label.lower()}.")
    if values.get("review_date"):
        try:
            parsed = date.fromisoformat(values["review_date"])
            if parsed.isoformat() != values["review_date"]:
                raise ValueError()
        except ValueError:
            errors.append("Enter a valid review date.")
    return ValidationResult(not errors, tuple(errors))
