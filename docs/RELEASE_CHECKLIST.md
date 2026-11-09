# Release candidate checklist
- [ ] `pytest -q` passes
- [ ] coverage reviewed; important branches tested
- [ ] no organisation/customer/employee identifiers in code, data, screenshots or Git history
- [ ] no secrets committed
- [ ] debug mode not used for public deployment
- [ ] run with `waitress-serve --call app:create_app` for a local production-like check
- [ ] accessibility/manual acceptance checks recorded
- [ ] repository URL inserted into report
- [ ] genuine peer/tutor code-review evidence inserted
