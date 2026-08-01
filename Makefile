.PHONY: compile evaluation test gauntlet generated seeds verify verify-optimized press-notice

compile:
	python3 -m compileall -q claimpack tools tests

test:
	python3 -m unittest discover -s tests -v

gauntlet:
	python3 gauntlet/run.py

generated:
	python3 -m tools.check_generated

evaluation:
	python3 -m tools.check_evaluation_generated

seeds:
	python3 -m claimpack validate examples/z20
	python3 -m claimpack validate examples/vr2-k4
	python3 -m claimpack validate examples/erdos848
	python3 -m claimpack validate examples/degree-difference-affine-slices
	python3 -m claimpack validate examples/exotic-affine-spheres-quadratic-cubic
	python3 -m claimpack validate examples/reducible-incidence-divisors-affine-slices

verify: compile generated evaluation seeds test gauntlet

verify-optimized:
	PYTHONOPTIMIZE=1 python3 -m unittest discover -s tests -v
	PYTHONOPTIMIZE=1 python3 gauntlet/run.py

press-notice:
	python3 tools/send_press_notice_email.py --dry-run \
		--inbox-id "sender@agentmail.to" \
		--to "recipient@example.org" \
		--title "Candidate notice" \
		--summary "Candidate release announcement." \
		--release-url "https://example.org/immutable-release"
