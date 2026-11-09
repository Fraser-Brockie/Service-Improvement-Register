# SDLC and agile evidence

## Sprint 0 - requirements and analysis
Problem: a fictional internal team needs a lightweight way to record, prioritise and review service-improvement requests without exposing organisation, customer or employee identities.

Functional requirements: create an item; validate inputs; list and filter items; change status; show dashboard statistics; retrieve persistent data.
Non-functional requirements: simple local deployment; maintainability; accessibility-minded HTML; safe database access; deterministic tests; no organisation-identifying data.

## Design
Three layers are kept deliberately small: Flask routes/templates (presentation), service functions (business rules), and SQLite repository functions (persistence). The application-factory pattern allows isolated test configuration. SQLite suits the low-volume single-team scenario while preserving SQL retrieval evidence.

## Sprint 1 - minimum viable increment
Create factory, schema, repository, list/create workflow and validation.

## Sprint 2 - feedback-driven increment
Add status workflow, filtering and summary statistics after reviewing the MVP against acceptance criteria.

## Sprint 3 - verification and release candidate
Add unit/integration tests, error handlers, documentation and production-server command. Run regression tests and inspect repository history.

## Feedback loop
At the end of each sprint: demonstrate increment, compare against acceptance criteria, record one improvement, reprioritise backlog, then commit the coherent change. For an individual assessment, the 'reviewer' can be a tutor/peer; record genuine feedback in the appendix rather than inventing it.

## Definition of done
Feature has acceptance criteria, input validation, automated tests, no secrets/identifiers, readable code, and documentation updated.
