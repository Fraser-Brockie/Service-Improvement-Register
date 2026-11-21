"""Explicit, opt-in demonstration data. Existing records are never replaced."""

from datetime import date, timedelta
import click
from . import repository
from .services import create_item


def register_commands(app):
    @app.cli.command("seed-demo")
    def seed_demo():
        """Populate an empty database with fictional improvement requests."""
        if repository.get_item(1) or repository.search_items({}, 1)[1]:
            raise click.ClickException(
                "Demo seeding requires an empty database. Choose a separate DATABASE path."
            )
        examples = [
            ("Improve bereavement support handovers", "Process", "High", "In Progress"),
            ("Check payment failure notifications automatically", "Technology", "High", "New"),
            ("Make fraud reporting guidance easier to find", "Customer", "Medium", "Done"),
            ("Standardise complaint resolution reviews", "Quality", "Medium", "In Progress"),
            ("Reduce duplicate mortgage application entry", "Process", "High", "New"),
            ("Improve accessibility of mobile banking help", "Customer", "Medium", "New"),
            ("Create a branch payment support guide", "Technology", "Low", "Done"),
            ("Review vulnerable customer support exceptions", "Quality", "Low", "New"),
        ]
        for n, (title, category, priority, status) in enumerate(examples):
            item_id, _ = create_item(
                title,
                category,
                priority,
                "Fictional scenario: review the current approach, trial a small change and evaluate the outcome.",
                (date.today() + timedelta(days=n - 2)).isoformat(),
            )
            repository.update_banking(item_id, {
                "business_area": "Retail banking",
                "customer_journey": ["Bereavement support", "Payments", "Fraud reporting", "Complaints", "Mortgages", "Digital support", "Branch support", "Customer support"][n],
                "channel": "Multiple channels",
                "owner": "Fictional customer operations team",
                "risk_category": "Customer harm" if n % 2 else "Process and controls",
                "customer_outcome": "Make support clearer and reduce repeat customer contacts.",
                "success_measure": "Repeat contacts per 100 cases (fictional measure)",
                "baseline": "24 per 100 cases",
                "target": "12 per 100 cases",
                "approval_stage": "Validated" if status == "Done" else "Submitted",
                "approver": "Fictional service review team",
                "actual": "10 per 100 cases; fictional pilot evidence" if status == "Done" else "",
            })
            if status != "New":
                repository.update_status(item_id, status)
        click.echo("Created eight fictional demonstration requests.")
