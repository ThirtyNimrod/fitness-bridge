# Rules

## Must Always
- Delegate to specialized agents for domain tasks.
- Write tests before implementation and verify critical paths.
- Validate inputs and keep security checks intact.
- Prefer immutable updates over mutating shared state.
- Follow established repository patterns before inventing new ones.
- Keep contributions focused, reviewable, and well-described.
- Use type annotations on all Python function signatures.
- Use `logging` module instead of `print()`.
- Use `timezone.utc` (from `datetime.timezone`) for UTC timestamps to avoid `datetime.UTC` errors.

## Must Never
- Include sensitive data such as API keys, tokens, secrets, or absolute/system file paths in output.
- Submit untested changes.
- Bypass security checks or validation hooks.
- Duplicate existing functionality without a clear reason.
- Ship code without checking the relevant test suite.
- Use `print()` in production code.
- Use bare `except:` clauses.
- Use mutable default arguments.

## Agent Format
- Agents live in `.github/agents/*.md`.
- Each file includes YAML frontmatter with `name`, `description`, `tools`, and `model`.
- File names are lowercase with hyphens and must match the agent name.
- Descriptions must clearly communicate when the agent should be invoked.

## Skill Format
- Skills live in `.github/skills/<name>/SKILL.md`.
- Each skill includes YAML frontmatter with `name` and `description`.
- Skill bodies should include practical guidance, tested examples, and clear "When to Use" sections.

## Hook Format
- Hooks use matcher-driven JSON registration and shell or Node entrypoints.
- Matchers should be specific instead of broad catch-alls.
- Exit `1` only when blocking behavior is intentional; otherwise exit `0`.
- Error and info messages should be actionable.

## Commit Style
- Use conventional commits such as `feat:`, `fix:`, `docs:`, `test:`, `refactor:`.
- Keep changes modular and explain user-facing impact in the PR summary.
