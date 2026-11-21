"""Add clearly fictional sample records without changing existing rows.

Run: python scripts/seed_realistic.py --as-of 2026-11-10
"""

import argparse
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path

MARKER = "Fictional demonstration record."
# title, category, priority, status, age in days, target turnaround, scenario
EXAMPLES = [
    (
        "Introduce a single service handover checklist",
        "Process",
        "High",
        "Done",
        84,
        28,
        "Shift handovers omit outstanding actions and escalation contacts. Trial a shared checklist covering ownership, customer impact and next update time. Success: every sampled handover has an owner and no overdue action is lost between shifts.",
    ),
    (
        "Standardise quality checks for account maintenance",
        "Quality",
        "High",
        "Done",
        78,
        30,
        "Reviewers apply different checks to account maintenance requests. Agree a risk-based checklist and calibrate reviewers using fictional cases. Success: consistent review outcomes and fewer requests returned for missing evidence.",
    ),
    (
        "Send acknowledgement messages for service requests",
        "Customer",
        "Medium",
        "Done",
        72,
        21,
        "Customers contact the team again because they do not know whether a request was received. Introduce a plain-language acknowledgement with a reference and expected response time. Success: fewer avoidable repeat contacts without exposing personal information.",
    ),
    (
        "Remove duplicate entry from daily service reporting",
        "Technology",
        "Medium",
        "Done",
        66,
        28,
        "Analysts copy the same figures into two reporting templates each morning. Generate a single validated extract with clear reconciliation checks. Success: eliminate duplicate typing while retaining an auditable source for every reported total.",
    ),
    (
        "Create an accessible guide to complaint progress",
        "Customer",
        "High",
        "Done",
        60,
        30,
        "Existing guidance uses complex language and does not explain the next step. Rewrite the progress guide in plain English and test its structure with keyboard navigation. Success: clearer expectations and fewer requests for clarification.",
    ),
    (
        "Publish ownership rules for misrouted requests",
        "Process",
        "Medium",
        "Done",
        55,
        21,
        "Requests transferred to the wrong queue can circulate without an agreed owner. Define first-contact ownership and a clear reassignment path. Success: each transferred request is accepted by a named team before the original team closes its action.",
    ),
    (
        "Add validation to the monthly exception report",
        "Quality",
        "Medium",
        "Done",
        49,
        21,
        "Missing categories and duplicate rows are discovered late in the monthly review. Add completeness and duplicate checks before submission. Success: exceptions are identified early and reviewers receive one reconciled report.",
    ),
    (
        "Replace manual service availability checks",
        "Technology",
        "Low",
        "Done",
        44,
        28,
        "The support team repeatedly checks several internal service pages by hand. Trial scheduled availability checks with clear alert thresholds. Success: actionable alerts reach the correct queue without generating excessive noise.",
    ),
    (
        "Reduce backlog in payment investigation handoffs",
        "Process",
        "High",
        "In Progress",
        38,
        28,
        "Payment investigation cases wait between first-line review and specialist assessment. Map the handoff, agree minimum evidence and pilot a daily triage slot. Success: reduce time waiting for allocation without bypassing required controls.",
    ),
    (
        "Improve incident update templates",
        "Customer",
        "High",
        "In Progress",
        33,
        21,
        "Service disruption updates vary in clarity and sometimes omit the next update time. Introduce consistent templates for impact, workaround and next communication. Success: customers receive useful updates at the promised interval.",
    ),
    (
        "Automate reconciliation of failed batch jobs",
        "Technology",
        "High",
        "In Progress",
        29,
        42,
        "Failed overnight jobs are reconciled using a manually maintained spreadsheet. Build a read-only exception extract and validate it against the source records. Success: every failure is accounted for and false positives are reviewed before rollout.",
    ),
    (
        "Calibrate service review scoring between teams",
        "Quality",
        "Medium",
        "In Progress",
        25,
        35,
        "Teams interpret service quality scoring differently, making comparisons unreliable. Run a calibration exercise with anonymised fictional examples and agreed scoring guidance. Success: reviewers reach consistent decisions and document reasons for exceptions.",
    ),
    (
        "Simplify approval routing for routine changes",
        "Process",
        "Medium",
        "In Progress",
        21,
        30,
        "Low-risk routine changes follow inconsistent approval paths and spend time in the wrong queue. Clarify the routing matrix while preserving mandatory approvals. Success: fewer reassignments and a clear escalation route for unusual cases.",
    ),
    (
        "Improve search in the colleague knowledge base",
        "Technology",
        "Medium",
        "In Progress",
        18,
        28,
        "Colleagues use several terms for the same process and struggle to find approved guidance. Add reviewed synonyms, retire duplicate articles and improve article titles. Success: common service questions return the correct current guidance in the first results.",
    ),
    (
        "Check accessibility of service request forms",
        "Customer",
        "Medium",
        "In Progress",
        14,
        21,
        "Some form instructions are unclear when navigating by keyboard or using a screen reader. Review labels, error summaries and focus order on the most-used forms. Success: a user can complete and correct the form without relying on a mouse or colour.",
    ),
    (
        "Introduce peer review for exception closure evidence",
        "Quality",
        "High",
        "In Progress",
        11,
        21,
        "Exception closure records sometimes lack evidence that the underlying issue was resolved. Pilot proportionate peer review for higher-risk closures. Success: sampled closures include a clear resolution, supporting evidence and confirmation that follow-up actions are complete.",
    ),
    (
        "Define escalation thresholds for ageing requests",
        "Process",
        "High",
        "New",
        9,
        7,
        "Ageing service requests are escalated inconsistently and may be noticed only at weekly review. Agree thresholds by impact and a daily exception view. Success: overdue requests have an explicit recovery action and escalation owner.",
    ),
    (
        "Detect duplicate customer contact records",
        "Quality",
        "High",
        "New",
        8,
        14,
        "Duplicate contact entries can lead to repeated follow-up work. Investigate safe duplicate detection using reference and timestamp rules with manual confirmation. Success: identify likely duplicates without automatically deleting legitimate separate contacts.",
    ),
    (
        "Provide clearer next steps after document submission",
        "Customer",
        "Medium",
        "New",
        6,
        21,
        "Customers do not know what happens after supporting documents are submitted. Review confirmation text and explain review stages and expected timings. Success: customers understand the next step and when they should contact the team again.",
    ),
    (
        "Create a dashboard for recurring service incidents",
        "Technology",
        "Medium",
        "New",
        5,
        28,
        "Recurring incidents are reviewed individually, making common causes difficult to identify. Propose a dashboard grouped by service and cause using anonymised aggregates. Success: reviewers can identify repeat issues and link them to an improvement action.",
    ),
    (
        "Review guidance for vulnerable customer referrals",
        "Customer",
        "High",
        "New",
        4,
        14,
        "Colleagues need clearer guidance on referring customers who require additional support. Review referral steps with the relevant policy owner using fictional scenarios. Success: colleagues can find the correct support route without collecting unnecessary sensitive details.",
    ),
    (
        "Measure avoidable transfers between service queues",
        "Process",
        "Low",
        "New",
        3,
        30,
        "The team cannot distinguish useful specialist referrals from avoidable transfers. Define transfer reason codes and a small weekly sample review. Success: the team can target the most common preventable causes with evidence.",
    ),
    (
        "Add freshness indicators to operational reports",
        "Technology",
        "Low",
        "New",
        1,
        21,
        "Users sometimes interpret yesterday's report as current because refresh times are not visible. Add a last-successful-refresh timestamp and a stale-data warning. Success: users can tell whether the figures are current before making an operational decision.",
    ),
    (
        "Align definitions of first-contact resolution",
        "Quality",
        "Low",
        "New",
        0,
        28,
        "Different teams count first-contact resolution differently. Agree a shared definition, exclusions and worked fictional examples. Success: reporting uses one transparent measure and limitations are explained alongside the figures.",
    ),
]


def seed(connection: sqlite3.Connection, as_of: date) -> int:
    """Insert a repeatable sample dataset and its simulated events atomically."""
    added = 0
    events = []
    with connection:
        for title, category, priority, status, age, target, scenario in EXAMPLES:
            if connection.execute(
                "SELECT 1 FROM improvement WHERE title=? AND description LIKE ?", (title, MARKER + "%")
            ).fetchone():
                continue
            created = datetime.combine(as_of - timedelta(days=age), time(8, 0))
            history = [(created, "Sample history: Request created")]
            if status != "New":
                history.append(
                    (created + timedelta(days=2, hours=1), "Sample history: Status changed to In Progress")
                )
                history.append(
                    (
                        created + timedelta(days=5, hours=2),
                        "Sample history: Initial review complete; pilot scope and success criteria agreed",
                    )
                )
            if status == "Done":
                history.append(
                    (
                        created + timedelta(days=target - 2, hours=3),
                        "Sample history: Pilot reviewed; agreed checks completed and status changed to Done",
                    )
                )
            updated = history[-1][0].isoformat(sep=" ")
            cursor = connection.execute(
                """INSERT INTO improvement
                (title,category,priority,status,created_at,description,due_date,updated_at,archived)
                VALUES (?,?,?,?,?,?,?,?,0)""",
                (
                    title,
                    category,
                    priority,
                    status,
                    created.isoformat(sep=" "),
                    MARKER + "\n\n" + scenario,
                    (created.date() + timedelta(days=target)).isoformat(),
                    updated,
                ),
            )
            events.extend((stamp.isoformat(sep=" "), cursor.lastrowid, message) for stamp, message in history)
            added += 1
        connection.executemany(
            "INSERT INTO activity(created_at,item_id,message) VALUES (?,?,?)", sorted(events)
        )
    return added


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "instance" / "improvements.sqlite",
    )
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("Database does not exist; initialise the application first.")
    with sqlite3.connect(args.database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        backup = args.database.with_name(
            "sample-backup-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".sqlite"
        )
        with sqlite3.connect(backup) as target:
            db.backup(target)
        print(f"Backup: {backup.name}")
        print(f"Added {seed(db, args.as_of)} fictional requests. Existing records retained.")


if __name__ == "__main__":
    main()
