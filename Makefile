.PHONY: clean-pyc clean-build docs generate-versions

clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info
	rm -fr __pycache__/ .eggs/ .cache/ .tox/

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

generate-versions:
	python3 generate_versions.py

lint:
	uv run ruff check src 

format:
	uv run ruff format src

build: generate-versions
	uv build

install: build
	uv pip install -e .

git:
	git push --all
	git push --tags

check:
	uv pip check

dev-setup:
	uv sync --dev

dist: generate-versions
	uv build
	uvx uv-publish@latest --repo pypi

test-dist: generate-versions
	uv build
	uvx uv-publish@latest --repo testpypi

release: clean check dist git
