# AGENTS.md — ColorLab Pro

## Project Overview

Python desktop app for display spectral data management & gamut analysis (LED/QD/CF R&D). PySide6 GUI + SQLAlchemy/SQLite backend.

**Source layout**: `src/colorlab_pro/` (src-layout, `pyproject.toml` [tool.setuptools.packages.find] where = ["src"])

## Quick Commands

```bash
# Install (must use venv — never global pip)
python -m venv .venv
.venv\Scripts\activate           # Windows
pip install -r requirements-dev.txt
pip install -e .

# Run
python scripts/run_app.py        # GUI via script (adds src/ to sys.path)
colorlab-pro-gui                 # GUI via entry point (installed package)
colorlab-pro --help              # CLI
run.bat                          # Windows convenience (activates venv + runs script)

# Verify code quality (run in order)
ruff check .                     # Lint — E501/B008 ignored; see ruff.toml
ruff format --check .            # Format check — 25 files currently non-compliant
pytest                           # All tests (fail_under=90 via pyproject.toml)
pytest -m unit                   # Unit only (fast, isolated)
pytest --cov                     # Coverage report
mypy src/                        # Type check (~77 historical issues — non-blocking)
```

⚠️ **ruff.toml is the source of truth for ruff config**, not the stale `[tool.ruff]` section in `pyproject.toml`. The `pyproject.toml` per-file-ignores are a legacy duplicate — always edit `ruff.toml`.

## Architecture (6 layers)

```
UI (PySide6) → Controller → Service → Engine (pure functions) → Repository → Database (SQLite/SQLAlchemy)
```

Key packages under `src/colorlab_pro/`:
- `engines/` — Pure algorithmic functions (spectrum, color, gamut, optimization). **High coverage target ≥ 80%.**
- `services/` — Business use-case orchestration, transaction boundaries.
- `controllers/` — UI ↔ Service bridge.
- `ui/` — PySide6 widgets, pages, dialogs, viewmodels, resources.
- `ui/webview_page.py` — Base class for pages backed by QWebEngineView + QWebChannel. Most workspace pages (spectrum, gamut, optimizer, white point) extend this.
- `database/` — SQLAlchemy ORM models, session factory, lightweight schema-version migration system (auto-backup before migration).
- `dto/` — Data transfer objects (dataclasses).
- `repositories/` — Data access abstraction.
- `importers/`, `exporters/` — CSV, XLSX, JSON formats.
- `config/` — `AppConfig` dataclass, loads from `~/.colorlab_pro/config.yaml` if present.
- `utils/` — `errors.py` (exception hierarchy: `ColorLabError` → `ValidationError` / `SpectrumImportError` / `ComputationError`), `logging.py` (loguru setup), `paths.py`, `validation.py`.

Entry points (`pyproject.toml [project.scripts]`):
- `colorlab-pro` → `colorlab_pro.cli:main`
- `colorlab-pro-gui` → `colorlab_pro.ui.app:main`

## Testing

- Framework: pytest + pytest-qt + pytest-cov
- Markers: `unit`, `integration`, `ui`, `slow`
- `pytest.ini` sets `pythonpath = src`, `testpaths = tests`, `addopts = -ra --strict-markers`
- Coverage config in `pyproject.toml`: source = `src/colorlab_pro`, **omit** `ui/*`, `cli.py`, `database/migrations.py`, `exporters/report_exporter.py`
- Shared fixtures in `tests/conftest.py` (standard 380–780 nm wavelengths, LED/CF spectra, D65 illuminant, etc.)
- Coverage target: **90%** (`fail_under = 90` in `pyproject.toml`)

## Code Style

- **ruff**: line-length 100, target py310, select `E/F/W/I/N/UP/B/A/C4/DTZ/PT/Q`; ignore `E501` (line length, handled by formatter) and `B008` (function call in default arg)
- **mypy**: non-strict, `no_implicit_optional` + `check_untyped_defs` enabled, several third-party stubs ignored (colour, shapely, PySide6, scipy, openpyxl, sqlalchemy)
- Naming: snake_case functions/vars, PascalCase classes, UPPER_SNAKE constants
- Docstrings: Google style, public functions require type annotations + Args/Returns
- Error handling: custom exceptions inherit `ColorLabError` (`utils/errors.py`), never bare `except:`
- Logging: `loguru`, module-level `logger.bind(module=__name__)`

## Critical Domain Rules

- **All Coverage/Match calculations in CIE 1931 xy space** (Decision D-016). Don't switch to u'v' for these.
- **numpy >=1.26,<2.3** — handle numpy 1.x/2.x compat via `hasattr(np, "trapezoid")` check (see `spectrum_normalizer.py:74`)
- **colour-science >=0.4.4,<0.5** — use `sd[wavelength]` (`__getitem__`), not `sd.value(wavelength)`
- **CIE data**: use `colour-science` library functions, never hardcode CIE 1931 CMFs
- Formulas (CIE XYZ, McCamy CCT, Lambert-Beer, Coverage/Match) are documented in `ai_context/DOMAIN_KNOWLEDGE.md` — consult it, don't guess

## Workflow Rules (from `docs/11_AI_Development_Guide.md`)

- One task at a time — track in `ai_context/CURRENT_TASK.md`
- After completing a task: update `CURRENT_TASK.md`, `PROJECT_STATUS.md`, `KNOWN_ISSUES.md`
- Non-trivial decisions → append to `docs/12_Decision_Log.md` with D-NNN prefix
- **Never modify existing content in `docs/01..11`** — only append sections or mark revisions
- **Never delete existing source files** without explicit confirmation
- Document priority on conflict: `docs/05` (API) > `docs/03` (Architecture) > `docs/07` (Coding) > `docs/10` (Roadmap) > `docs/01` (PRD) > `ai_context/DOMAIN_KNOWLEDGE.md` (domain science only)

## AI Coding Principles (from Ponytail)

Lazy means efficient, not careless. Before writing code, check:

1. Does this need to be built at all? (YAGNI)
2. Does the standard library already do this? Use it.
3. Does an already-installed dependency solve it? Use it.
4. Can this be one line? Make it one line.
5. Only then: write the minimum code that works.

**Rules:**
- No abstractions that weren't explicitly requested
- No new dependency if it can be avoided
- No boilerplate nobody asked for
- Deletion over addition. Boring over clever. Fewest files possible
- Question complex requests: "Do you actually need X, or does Y cover it?"
- Mark intentional simplifications with a `# ponytail:` comment naming the ceiling and upgrade path

**Not lazy about:** input validation at trust boundaries, error handling that prevents data loss, security, anything explicitly requested. Non-trivial logic leaves ONE runnable check behind (assert or small test file).

## Known Gotchas

- **mypy reports ~77 historical type issues** — these are pre-existing and don't block execution
- **Coverage floating-point noise**: shapely polygon intersection can produce values slightly > 100% (tolerance: `<= 100.0 + 1e-9`)
- **shapely 2.x**: `Polygon.contains()` requires `shapely.geometry.Point(x, y)`, not bare tuples
- **QSettings layout persistence**: gamut page splitter state saved/restored automatically via QSettings key `gamut_calculator_layout_v2`
- **pytest-qt markers**: UI tests require display; use `offscreen` platform plugin for headless CI
