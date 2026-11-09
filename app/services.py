from collections import Counter, deque
from dataclasses import dataclass
from . import repository

CATEGORIES = ("Process", "Quality", "Technology", "Customer")
PRIORITIES = ("Low", "Medium", "High")
STATUSES = ("New", "In Progress", "Done")

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: tuple[str, ...]


def validate_item(title, category, priority):
    errors = []
    clean_title = title.strip()
    if not 3 <= len(clean_title) <= 100:
        errors.append("Title must contain between 3 and 100 characters.")
    if category not in CATEGORIES:
        errors.append("Choose a valid category.")
    if priority not in PRIORITIES:
        errors.append("Choose a valid priority.")
    return ValidationResult(not errors, tuple(errors))


def create_item(title, category, priority):
    result = validate_item(title, category, priority)
    if not result.valid:
        return None, result
    item_id = repository.add_item(title.strip(), category, priority)
    return item_id, result


def change_status(item_id, status):
    if status not in STATUSES:
        raise ValueError("Unsupported status")
    if not repository.update_status(item_id, status):
        raise LookupError("Improvement item not found")


def dashboard(status=None):
    items = repository.list_items(status)
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
