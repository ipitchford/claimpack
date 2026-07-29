# Contributing

This is a pre-release protocol experiment. The most useful contributions are
small, reproducible failures of the consumer or specification.

Please include:

- the exact protocol and package versions;
- a minimal inert fixture;
- expected `REJECT`, `DENY`, or `UNKNOWN` behavior;
- actual output and termination reason;
- whether any unsafe tool or side effect occurred; and
- the assurance wording that would be overstated if the defect remained.

Do not submit live secrets, malware, personal data, copyrighted source bundles,
or replay commands that must be executed to understand the report. Semantic
attack fixtures must be re-sealed so they reach policy evaluation; otherwise
they test only hash mismatch rejection.

Changes to status vocabulary must preserve separate issuer, date,
authentication, evidence dimension, and scope fields. A new aggregate
credibility or truth score is out of scope.

Run `make verify` before proposing a change. Add a failing adversarial test
first for security or qualification-fidelity defects.
