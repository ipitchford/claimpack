.PHONY: compile test gauntlet generated seeds verify

compile:
	python3 -m compileall -q claimpack tools tests

test:
	python3 -m unittest discover -s tests -v

gauntlet:
	python3 gauntlet/run.py

generated:
	python3 -m tools.check_generated

seeds:
	python3 -m claimpack validate examples/z20
	python3 -m claimpack validate examples/vr2-k4
	python3 -m claimpack validate examples/erdos848

verify: compile generated seeds test gauntlet
