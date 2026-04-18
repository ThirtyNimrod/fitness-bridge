# Testing Guide — Fitness Bridge AI

The project uses `pytest` for quality assurance, organised into **Phases** to ensure a stable foundation before testing higher-level features.

## 1. How to Run Tests

### Standard Ordered Run
Runs all phases (00–07) in sequence, stopping on the first failure:

```bash
python scripts/run_tests.py
```

### Direct Pytest Run
Run specific phases or everything:

```bash
# All tests
pytest

# Specific phase
pytest tests/phase-tests/test_phase03_parsers.py -v
```

## 2. Phase Breakdown

| Phase | Scope | Description |
|---|---|---|
| **00** | Environment | Checks Python version, installed packages, and `.env` presence. |
| **01** | Foundation | Verifies database initialisation and disk caching logic. |
| **02** | Clients | Manual token refresh check (skips in CI). |
| **03** | Parsers | Unit tests for Hevy plaintext parsing logic. |
| **04** | Analysis | Validates Readiness, ACWR, and Strength algorithms. |
| **05** | Engine | Tests Sync Engine idempotency and Memory store persistence. |
| **06** | Guardrails | Verifies LLM input/output validation and safety filters. |
| **07** | Agents | Tests the LangGraph router and specialist tool integration. |

## 3. Adding New Tests

- **Location**: All tests must reside in `tests/phase-tests/`.
- **Naming**: Use the `test_phaseXX_*.py` pattern.
- **Isolation**: Use the `fresh_db` fixture from `conftest.py` for any test that touches the database. This ensures each test starts with an empty SQLite file.
- **Wait Time**: UI or Agent tests should use a generous timeout (e.g., 10s) as LangGraph and database operations can be slow in certain environments.

## 4. Instrumentation

To trace agent logic during tests, set `LANGSMITH_API_KEY` in your `.env`. This will upload detailed traces of every LangGraph node execution to your LangSmith dashboard.
