# Fitness Bridge AI — Agent Instructions

This is a **Python AI fitness coaching platform** enhanced with specialized AI coding agents, skills, commands, and automated workflows from the [Everything Claude Code](https://github.com/anthropics/everything-claude-code) plugin.

**Version:** 1.0.0

## Core Principles

1. **Agent-First** — Delegate to specialized agents for domain tasks
2. **Test-Driven** — Write tests before implementation, 80%+ coverage required
3. **Security-First** — Never compromise on security; validate all inputs
4. **Immutability** — Prefer frozen dataclasses and NamedTuples, never mutate
5. **Plan Before Execute** — Plan complex features before writing code

## Available Agents

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| planner | Implementation planning | Complex features, refactoring |
| architect | System design and scalability | Architectural decisions |
| tdd-guide | Test-driven development | New features, bug fixes |
| code-reviewer | Code quality and maintainability | After writing/modifying code |
| security-reviewer | Vulnerability detection | Before commits, sensitive code |
| python-reviewer | Python code review (PEP 8, type hints) | All Python code changes |
| build-error-resolver | Fix build/import errors | When build fails |
| database-reviewer | SQLite/PostgreSQL specialist | Schema design, query optimization |
| doc-updater | Documentation and codemaps | Updating docs |
| docs-lookup | Documentation and API reference research | Library/API documentation questions |
| refactor-cleaner | Dead code cleanup | Code maintenance |
| e2e-runner | End-to-end testing | Critical user flows |
| performance-optimizer | Performance tuning | Optimization tasks |
| loop-operator | Autonomous loop execution | Run loops safely, monitor stalls |
| harness-optimizer | Harness config tuning | Reliability, cost, throughput |

## Agent Orchestration

Use agents proactively without user prompt:
- Complex feature requests → **planner**
- Code just written/modified → **code-reviewer** + **python-reviewer**
- Bug fix or new feature → **tdd-guide**
- Architectural decision → **architect**
- Security-sensitive code → **security-reviewer**
- Database changes → **database-reviewer**
- Autonomous loops / loop monitoring → **loop-operator**

Use parallel execution for independent operations — launch multiple agents simultaneously.

## Security Guidelines

**Before ANY commit:**
- No hardcoded secrets (API keys, passwords, tokens)
- All user inputs validated
- SQL injection prevention (parameterized queries)
- Error messages don't leak sensitive data
- `.env` file is in `.gitignore`

**Secret management:** NEVER hardcode secrets. Use `os.environ` with `python-dotenv`. Validate required secrets at startup. Rotate any exposed secrets immediately.

**If security issue found:** STOP → use security-reviewer agent → fix CRITICAL issues → rotate exposed secrets → review codebase for similar issues.

## Coding Style

**Immutability (CRITICAL):** Prefer `@dataclass(frozen=True)` and `NamedTuple`. Return new copies with changes applied.

**File organization:** Many small files over few large ones. 200–400 lines typical, 800 max. Organize by feature/domain. High cohesion, low coupling.

**Python standards:** PEP 8, type annotations on all functions, f-strings, `logging` not `print()`, `ruff` + `black` + `isort`.

**Error handling:** Handle errors at every level. User-friendly messages in Streamlit UI. Detailed server-side logging. Never silently swallow errors.

**Code quality checklist:**
- Functions small (<50 lines), files focused (<800 lines)
- No deep nesting (>4 levels)
- Proper error handling, no hardcoded values
- Readable, well-named identifiers

## Testing Requirements

**Minimum coverage: 80%**

Test types (all required):
1. **Unit tests** — Individual functions, utilities, parsers
2. **Integration tests** — API clients, SyncEngine, database operations
3. **E2E tests** — Critical Streamlit user flows

**TDD workflow (mandatory):**
1. Write test first (RED) — test should FAIL
2. Write minimal implementation (GREEN) — test should PASS
3. Refactor (IMPROVE) — verify coverage 80%+

## Development Workflow

1. **Plan** — Use planner agent, identify dependencies and risks, break into phases
2. **TDD** — Use tdd-guide agent, write tests first, implement, refactor
3. **Review** — Use code-reviewer + python-reviewer agents, address CRITICAL/HIGH issues
4. **Verify** — Run `python run_tests.py` and `bandit -r src/`
5. **Commit** — Conventional commits format, comprehensive PR summaries

## Git Workflow

**Commit format:** `<type>: <description>` — Types: feat, fix, refactor, docs, test, chore, perf, ci

**PR workflow:** Analyze full commit history → draft comprehensive summary → include test plan → push with `-u` flag.

## Project Structure

```
src/agents/      — AI coaching agents
src/analysis/    — Workout analysis logic
src/clients/     — API clients (Strava, Fitbit)
src/guardrails/  — Input validation and safety
src/memory/      — Conversation memory
src/parsers/     — Data parsing utilities
src/sync/        — SyncEngine for local caching
src/utils/       — Shared utilities
tests/           — Test suite (pytest)
ui/              — Streamlit UI components
.github/agents/  — AI coding agent definitions
.github/skills/  — Domain knowledge and workflows
.github/commands/ — Slash commands
.github/rules/   — Coding guidelines
```

## Success Metrics

- All tests pass with 80%+ coverage
- No security vulnerabilities
- Code is readable and maintainable
- Performance is acceptable
- User requirements are met
