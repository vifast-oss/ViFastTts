.PHONY: demo-ngochuyen test lint

demo-ngochuyen:
	./scripts/run_ngochuyen_demo.sh

test:
	.venv/bin/python -m pytest -q

lint:
	.venv/bin/ruff check .
