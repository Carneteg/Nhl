.PHONY: test bootstrap sync dry-run audit export web
test:
	pytest -q
bootstrap:
	python -m nhlgm bootstrap:2025 --team ALL --season 20252026
dry-run:
	python -m nhlgm sync:all --team ALL --season 20252026 --dry-run
sync:
	python -m nhlgm sync:all --team ALL --season 20252026
audit:
	python -m nhlgm audit:cap
export:
	python -m nhlgm export:franchise
web:
	python -m nhlgm web
