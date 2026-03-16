# AGENTS.md

Agent guidance for working in this repository.

## Project Snapshot

- Package name: `django-admin-list-charts`
- Primary Python package: `admin_list_charts/`
- Distribution entrypoint: `setup.py`
- Django app config: `admin_list_charts/apps.py`
- Core feature: `ListChartMixin` in `admin_list_charts/admin.py`
- Template override: `admin_list_charts/templates/admin_list_charts/change_list_with_chart.html`
- Bundled assets: `admin_list_charts/static/admin_list_charts/`
- Test suite: not present in this repository today
- Lint config: not present in this repository today
- CI config: not present in this repository today

## Source Of Truth

- Prefer existing implementation patterns over generic best practices.
- Keep this repo as a small reusable Django app package.
- Preserve compatibility implied by `setup.py` (`python_requires='>=3.12,<3.15'`, `Django>=5,<7`).
- Avoid introducing syntax that requires newer Python unless requested.
- Keep package metadata in sync with `admin_list_charts/__init__.py` and `setup.py`.

## Environment Setup

- Create venv: `python3 -m venv .venv`
- Activate venv: `source .venv/bin/activate`
- Upgrade packaging tools: `python -m pip install -U pip setuptools wheel`
- Install package editable: `python -m pip install -e .`
- Install build tool (optional): `python -m pip install build`

## Build Commands

- Preferred build: `python -m build`
- Legacy build: `python setup.py sdist bdist_wheel`
- Verify package metadata quickly: `python setup.py --name --version`
- Check included files in sdist/wheel after build from `dist/`

## Test Commands

There is currently no committed test suite.
Use the commands below when adding or running tests.

- Run all unittest tests: `python -m unittest discover -s tests -p "test_*.py"`
- Run one unittest module: `python -m unittest tests.test_admin`
- Run one unittest class: `python -m unittest tests.test_admin.ListChartMixinTests`
- Run one unittest test: `python -m unittest tests.test_admin.ListChartMixinTests.test_get_chart_period`

If pytest is introduced later:

- Run all pytest tests: `pytest`
- Run file: `pytest tests/test_admin.py`
- Run one test: `pytest tests/test_admin.py::TestListChartMixin::test_get_chart_period`

Django project-level testing (when using a host project):

- Run all app tests: `python manage.py test`
- Run app label tests: `python manage.py test admin_list_charts`
- Run one test case: `python manage.py test tests.test_admin.ListChartMixinTests`
- Run one test method: `python manage.py test tests.test_admin.ListChartMixinTests.test_get_chart_period`

## Lint / Format Commands

No lint or formatter is configured in-repo.
When needed, use conservative defaults and keep diffs small.

- Optional formatting check: `python -m pip install black && black --check admin_list_charts setup.py`
- Optional formatting apply: `black admin_list_charts setup.py`
- Optional lint check: `python -m pip install ruff && ruff check admin_list_charts setup.py`

Only run optional tools if requested or if the repo adopts them.
Do not add tool configs unless explicitly asked.

## Code Style Guidelines

### Imports

- Group imports in this order: stdlib, third-party, local.
- Keep one import per line unless naturally paired.
- Prefer explicit imports over wildcard imports.
- In Django code, import only model functions/classes you use.
- Remove unused imports in touched files.

### Formatting

- Use 4-space indentation in Python files.
- Follow existing quote style in touched file (currently mostly single quotes).
- Keep lines readable; avoid dense one-liners.
- Preserve existing template style unless intentionally refactoring.
- Do not reformat minified vendor assets.

### Types

- Existing code is largely untyped; match local style.
- Add type hints for new non-trivial functions when they improve clarity.
- Use typing compatible with Python 3.12+ if added.
- Avoid introducing type-only complexity for tiny functions.

### Naming

- Classes: `CapWords` (e.g., `ListChartMixin`).
- Functions/methods/variables: `snake_case`.
- Constants: `UPPER_SNAKE_CASE`.
- Template block/context keys should be descriptive (`chart_data`, `chart_period`).
- Keep public API names stable unless versioned change is requested.

### Django Patterns

- Keep mixins focused and side-effect-light.
- Preserve behavior of `changelist_view` contract.
- When extending admin views, return parent response when data is unavailable.
- Keep queryset annotation logic readable and database-friendly.
- Avoid adding project-specific assumptions into this reusable app.

### Error Handling

- Catch specific exceptions only (as in current `AttributeError`, `KeyError` pattern).
- Prefer graceful fallback over raising in admin rendering paths.
- Do not swallow unexpected exceptions silently without reason.
- Guard access to optional request/context fields.
- Keep error handling minimal and explicit.

### Templates and Frontend Assets

- Keep Django template inheritance intact.
- Use `{% load static %}` and static paths under app namespace.
- Avoid heavy inline JS changes unless necessary for behavior.
- Preserve compatibility with Django admin DOM conventions.
- Treat `chart.bundle.min.js` and `chart.min.css` as vendored files.

### Packaging

- If version changes, update `admin_list_charts/__init__.py` and verify `setup.py` uses it.
- Keep `MANIFEST.in` aligned with template/static inclusion needs.
- Do not remove package data flags unless replacing packaging strategy.

## Change Scope Guidance

- Prefer minimal diffs focused on the requested task.
- Avoid broad refactors in this small library unless asked.
- Keep backward compatibility for downstream Django projects.
- Add tests with feature changes when a test harness is available.
- Update `README.md` for user-visible behavior changes.

## Cursor / Copilot Rules Check

- `.cursorrules`: not found
- `.cursor/rules/`: not found
- `.github/copilot-instructions.md`: not found

If these files are added later, treat them as high-priority instructions and update this document accordingly.

## Quick File Map

- Core logic: `admin_list_charts/admin.py`
- App config: `admin_list_charts/apps.py`
- Package metadata: `admin_list_charts/__init__.py`
- Admin template: `admin_list_charts/templates/admin_list_charts/change_list_with_chart.html`
- Static CSS: `admin_list_charts/static/admin_list_charts/css/chart.min.css`
- Static JS: `admin_list_charts/static/admin_list_charts/js/chart.bundle.min.js`
- Packaging: `setup.py`, `MANIFEST.in`
