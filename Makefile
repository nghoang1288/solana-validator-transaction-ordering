.PHONY: all run test docker-build docker-run clean

all: run

run:
	./run_experiment.sh --cohort-eval --dry-run

test:
	PYTHONPATH=. python3 -m unittest tests/test_safety.py

docker-build:
	docker compose build

docker-run:
	docker compose up

clean:
	rm -rf __pycache__ */__pycache__ .pytest_cache
