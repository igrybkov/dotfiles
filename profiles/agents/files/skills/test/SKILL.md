---
name: test
description: Generate tests for a function, class, or file
allowed-tools:
  - Read
  - Glob
  - Grep
  - Write
  - Edit
  - Bash(npm test:*)
  - Bash(pytest:*)
  - Bash(go test:*)
  - Bash(cargo test:*)
  - Bash(mix test:*)
  - Bash(bundle exec rspec:*)
  - Bash(ls:*)
---

# Test Generation Skill

Generate tests for the code the user specifies.

## Workflow

1. **Understand the code**
   - Read the file/function to be tested
   - Identify inputs, outputs, and side effects
   - Look for edge cases and error conditions

2. **Find existing test patterns**
   - Look for existing tests in the project to match style and conventions
   - Use the same testing framework already in use
   - Follow existing naming conventions

3. **Generate comprehensive tests**
   - Happy path: normal expected usage
   - Edge cases: empty inputs, boundaries, nulls
   - Error cases: invalid inputs, failure scenarios
   - If applicable: async behavior, timeouts, concurrency

4. **Test structure**
   - Clear test names that describe what's being tested
   - Arrange-Act-Assert pattern
   - One assertion per test when practical
   - Use mocks/stubs for external dependencies

5. **Write the tests**
   - Place tests in the appropriate location (follow project conventions)
   - If no test file exists, create one following project patterns

6. **Verify tests run**
   - Run the tests to make sure they pass
   - Fix any issues

## Common Test File Locations

- JavaScript/TypeScript: `__tests__/`, `*.test.ts`, `*.spec.ts`
- Python: `tests/`, `test_*.py`, `*_test.py`
- Go: `*_test.go` (same directory)
- Rust: `#[cfg(test)]` module or `tests/` directory

## Important Notes

- Ask the user which function/file to test if not specified
- Match existing test patterns in the codebase
