.PHONY=check test

SCRIPTS=\
	scripts/btzen-battery \
	scripts/btzen-cancel \
	scripts/btzen-connect \
	scripts/btzen-ostc \
	scripts/btzen-sensor-tag \
	scripts/btzen-thingy52 \
	scripts/btzen-weight

check:
	mypy --strict --scripts-are-modules btzen $(SCRIPTS)

test:
	pytest -vv --cov=btzen btzen
