# HelpChain backend Makefile
# Usage examples:
#   make venv
#   make install
#   make run
#   make update-deps
#   make sync-deps
#   make clean

PY ?= python
VENV := .venv

# OS-specific activation script path
ifeq ($(OS),Windows_NT)
ACTIVATE := $(VENV)/Scripts/activate
SHELL := bash
else
ACTIVATE := $(VENV)/bin/activate
endif

.PHONY: venv install update-deps sync-deps run clean deps-tree

venv:
	$(PY) -m venv $(VENV)

install: venv
	. $(ACTIVATE); pip install -r requirements.txt

update-deps: venv
	. $(ACTIVATE); pip install --upgrade pip-tools; pip-compile requirements.in --output-file requirements.txt

sync-deps: venv
	. $(ACTIVATE); pip install --upgrade pip-tools; pip-sync requirements.txt

run: install
	. $(ACTIVATE); FLASK_APP=app.py FLASK_RUN_HOST=127.0.0.1 FLASK_RUN_PORT=5000 $(PY) app.py

clean:
	rm -rf $(VENV) __pycache__ */__pycache__

# Show an ASCII tree of dependencies versions (simple)
deps-tree: install
	. $(ACTIVATE); pip list --format=columns
