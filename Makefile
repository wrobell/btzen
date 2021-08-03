.PHONY=check test

check:
	mypy btzen
	mypy scripts/btzen-sensor-tag
	mypy scripts/btzen-thingy52
	mypy scripts/btzen-weight
	mypy scripts/btzen-ostc

test:
	pytest -vv --cov=btzen btzen
