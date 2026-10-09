.PHONY: install install-dev test lint validate-data validate skill bootstrap

install:
	python -m pip install -e .

install-dev:
	python -m pip install -e ".[dev]"

test:
	python -m pytest -q

lint:
	python -m ruff check .

validate-data:
	python scripts/validate_public_dataset.py data/v1
	cd data/v1 && sha256sum -c CHECKSUMS.sha256

skill:
	bash scripts/install_skill.sh --source .cursor/skills/change2task

bootstrap:
	bash scripts/install.sh --source-root .

validate: test lint validate-data
