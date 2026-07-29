# badclaims adversarial corpus

These cases exercise the consumer boundary. A malformed package is
`REJECT`ed before any claim decision exists. A structurally valid package
with missing, stale, unauthenticated, disputed, or budget-exhausted evidence
must produce `UNKNOWN`; only a policy-accepted explicit adverse record
produces `DENY`.

All 12 cases listed in `cases.json` have exactly one executable `Gxx` test in
`tests/test_gauntlet.py`. The runner constructs its suite from that catalogue
and fails before testing if an ID is missing, duplicated, or undocumented.
Fixtures are synthesized inside temporary directories. They are not
distributed as live archives, and their replay text is never executed.

Run:

```sh
python3 gauntlet/run.py
```
