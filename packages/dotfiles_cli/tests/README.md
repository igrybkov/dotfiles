# Dotfiles CLI Tests

Comprehensive test suite for the dotfiles CLI package.

## Overview

This test suite provides comprehensive coverage of the dotfiles CLI functionality, including:

- **Unit tests** for individual modules and functions
- **Integration tests** for command workflows
- **Edge case testing** for error handling and boundary conditions

## Test Structure

```
packages/dotfiles_cli/tests/
├── __init__.py                  # Package marker
├── conftest.py                  # Shared fixtures and test configuration
├── test_constants.py            # Tests for constants module (30 tests)
├── test_utils.py                # Tests for utility functions (28 tests)
├── test_profiles.py             # Tests for profile selection/discovery (29 tests)
├── test_commands.py             # Tests for CLI commands (33 tests)
├── test_vault.py                # Tests for vault operations (24 tests)
├── test_types.py                # Tests for custom Click types (19 tests)
├── test_integration.py          # Integration tests (24 tests)
└── README.md                    # This file
```

**Total: 187+ tests**

## Running Tests

### Run all tests
```bash
mise x -- uv run pytest packages/dotfiles_cli/tests/ -v
```

### Run specific test file
```bash
mise x -- uv run pytest packages/dotfiles_cli/tests/test_utils.py -v
```

### Run specific test class or function
```bash
mise x -- uv run pytest packages/dotfiles_cli/tests/test_utils.py::TestCleanupOldLogs -v
mise x -- uv run pytest packages/dotfiles_cli/tests/test_utils.py::TestCleanupOldLogs::test_cleanup_keeps_recent_logs -v
```

### Run with coverage
```bash
mise x -- uv run pytest packages/dotfiles_cli/tests/ --cov=dotfiles_cli --cov-report=html
```

### Run only failed tests
```bash
mise x -- uv run pytest packages/dotfiles_cli/tests/ --lf
```

## Test Categories

### 1. Constants Tests (`test_constants.py`)

Tests for constant values and configuration:

- **TestConstants**: Validates all constant definitions
- **TestSudoTags**: Verifies SUDO_TAGS configuration
- **TestVaultTags**: Tests VAULT_TAGS configuration
- **TestPathConstants**: Validates path-related constants
- **TestConstantImmutability**: Ensures constants are usable

**Key Tests:**
- Verifies SUDO_TAGS contains expected values (mas, chsh) and non-sudo tags are excluded
- Validates VAULT_TAGS for secure operations
- Tests path constants are properly configured

### 2. Utility Tests (`test_utils.py`)

Tests for utility functions:

- **TestPreprocessLogfileArgs**: Logfile argument preprocessing
- **TestCleanupOldLogs**: Log file cleanup functionality
- **TestGenerateLogfileName**: Timestamped log file generation
- **TestShowDeprecationWarning**: Deprecation warning system
- **TestFzfSelect**: Interactive fzf selection
- **TestNumberedSelect**: Numbered selection fallback

**Key Tests:**
- Logfile argument handling with various flag combinations
- Old log file cleanup with configurable retention
- Deprecation warnings shown only once per session
- Interactive selection with fzf and numbered fallbacks

### 3. Profile Tests (`test_profiles.py`)

Tests for profile selection and discovery:

- **TestProfileSelection**: Profile selection resolution logic
- **TestParseProfileSelection**: Selection string parsing
- **TestGetProfileNames**: Profile discovery from filesystem
- **TestGetProfilePriority**: Profile priority assignment
- **TestGetProfileRolesPaths**: Profile roles directory discovery
- **TestProfileIntegration**: End-to-end profile workflows

**Key Tests:**
- Explicit profile selection: `common,work`
- Exclusion syntax: `-work` (all except work)
- All profiles: `all` or `all,-work`
- Default behavior (common only)
- Profile priority ordering

### 4. Command Tests (`test_commands.py`)

Tests for CLI commands:

- **TestCLIStructure**: CLI command structure validation
- **TestPullCommand**: `dotfiles pull` command
- **TestPushCommand**: `dotfiles push` command
- **TestSyncCommand**: `dotfiles sync` command
- **TestEditCommand**: `dotfiles edit` command
- **TestCompletionCommand**: `dotfiles completion` command
- **TestInstallCommand**: `dotfiles install` command (main)
- **TestSudoTags**: Sudo password handling

**Key Tests:**
- Install with default tag (all)
- Install with multiple tags
- Install with --all flag
- Sudo password prompting for non-exempt tags
- Profile selection via --profile flag
- Dry-run mode with --check
- Sync workflow before install
- Log file handling

### 5. Vault Tests (`test_vault.py`)

Tests for vault operations and password management:

- **TestGetSecretsFile**: Secrets file path resolution
- **TestGetAllSecretLocations**: Secret location discovery
- **TestGetProfilesWithSecrets**: Profile secrets detection
- **TestRunAnsibleVault**: Ansible vault command execution
- **TestGetVaultId**: Vault ID assignment
- **TestGetVaultPasswordFile**: Password file path resolution
- **TestEnsureVaultPasswordPermissions**: File permission management
- **TestWriteVaultPasswordFile**: Password file creation
- **TestGetVaultPassword**: Password retrieval (file/1Password/prompt)
- **TestValidateVaultPassword**: Password validation
- **TestVaultIntegration**: End-to-end vault workflows

**Key Tests:**
- Secrets file resolution for builtin locations (common/work/personal)
- Profile-specific secrets (profiles/{name}/secrets.yml)
- Vault password from file, 1Password, or interactive prompt
- Vault password validation against encrypted files
- Multi-vault password support (vault IDs)
- File permissions (0o600) enforcement

### 6. Types Tests (`test_types.py`)

Tests for custom Click types:

- **TestAnsibleTagListType**: Dynamic tag discovery and validation
- **TestAnsibleHostListType**: Dynamic host/profile discovery
- **TestAliasedGroup**: Command aliases and prefix matching
- **TestSingletonInstances**: Singleton type instances
- **TestTypesIntegration**: Integration with Click commands

**Key Tests:**
- Tag discovery from playbook
- Tag exclusion (never, always)
- Host discovery from inventory
- Fallback hosts on error
- Shell completion support
- Command prefix matching
- Ambiguous prefix detection

### 7. Integration Tests (`test_integration.py`)

End-to-end integration tests:

- **TestInstallWorkflow**: Complete install workflows
- **TestSyncWorkflow**: Sync command workflows
- **TestProfileSelectionWorkflow**: Profile selection scenarios
- **TestVaultWorkflow**: Vault operation workflows
- **TestCommandAliases**: Command alias functionality
- **TestErrorHandling**: Error handling and recovery
- **TestLogfileHandling**: Log file creation and management
- **TestCompletionGeneration**: Shell completion generation
- **TestEndToEndScenarios**: Complete user scenarios

**Key Scenarios:**
- Fresh install: `dotfiles install --profile common,work --sync --all`
- Install dotfiles only (no sudo): `dotfiles install dotfiles`
- Install with sudo prompt: `dotfiles install brew`
- Update and push: `dotfiles pull && dotfiles push`
- Vault encrypt/decrypt workflow
- Profile selection and resolution
- Error recovery and graceful degradation

## Fixtures

### Core Fixtures (`conftest.py`)

- **cli_runner**: Click CLI test runner
- **temp_home**: Temporary home directory with $HOME set
- **temp_dotfiles_dir**: Complete dotfiles directory structure
- **mock_subprocess**: Mocked subprocess.call and subprocess.run
- **mock_ansible_runner**: Mocked ansible_runner for playbook execution
- **mock_getpass**: Mocked password prompts
- **mock_dotfiles_dir**: Mocked DOTFILES_DIR constant
- **isolated_env**: Isolated environment variables
- **mock_vault_operations**: Mocked vault password operations
- **sample_profiles_data**: Sample profile test data

## Test Patterns

### Mocking External Dependencies

Tests mock external dependencies to ensure isolation and speed:

```python
with patch("subprocess.call") as mock_call, \
     patch("ansible_runner.run") as mock_run:
    # Test code
```

### Testing CLI Commands

Use Click's test runner for CLI command testing:

```python
result = cli_runner.invoke(cli, ["install", "dotfiles"])
assert result.exit_code == 0
assert "Expected output" in result.output
```

### Testing File Operations

Use pytest's `tmp_path` fixture for filesystem operations:

```python
def test_file_creation(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("content")
    assert test_file.exists()
```

### Testing Error Handling

Verify both success and error paths:

```python
# Test success
result = cli_runner.invoke(cli, ["command"])
assert result.exit_code == 0

# Test failure
with patch("subprocess.call", return_value=1):
    result = cli_runner.invoke(cli, ["command"])
    assert result.exit_code != 0
    assert "error message" in result.output
```

## Coverage Goals

The test suite aims for:

- **Line coverage**: >90%
- **Branch coverage**: >85%
- **Function coverage**: 100% of public APIs

Key areas with comprehensive coverage:

- Profile selection and resolution logic
- Sudo password handling (SUDO_TAGS)
- Vault operations and multi-password support
- Command-line argument parsing
- Error handling and recovery
- File operations and permissions

## Known Test Issues

Some tests may have minor issues (documented for tracking):

1. **Command name mismatch**: The CLI uses `config` instead of `config-profiles` (test needs update)
2. **Error output capture**: Some exceptions don't populate `result.output` in Click test runner
3. **Async operations**: Some tests involving shell interactions may be flaky

## Adding New Tests

When adding new functionality, follow these guidelines:

### 1. Unit Tests First

Create unit tests for individual functions:

```python
def test_new_function_success():
    """Test successful execution."""
    result = new_function(valid_input)
    assert result == expected_output

def test_new_function_error():
    """Test error handling."""
    with pytest.raises(ValueError):
        new_function(invalid_input)

def test_new_function_edge_cases():
    """Test edge cases."""
    assert new_function(None) is None
    assert new_function("") == ""
```

### 2. Integration Tests

Add integration tests for workflows:

```python
def test_complete_workflow(cli_runner, mock_ansible_runner):
    """Test complete user workflow."""
    # Setup
    # Execute
    # Verify
```

### 3. Update Fixtures

If you need new test fixtures, add them to `conftest.py`:

```python
@pytest.fixture
def new_fixture():
    """Description of fixture."""
    # Setup
    yield value
    # Teardown
```

## CI/CD Integration

Tests are run automatically in CI:

- On every pull request
- On every push to main
- Nightly for regression testing

CI configuration: `.github/workflows/ci.yml`

## Debugging Tests

### Run with verbose output
```bash
mise x -- uv run pytest packages/dotfiles_cli/tests/ -vv
```

### Show print statements
```bash
mise x -- uv run pytest packages/dotfiles_cli/tests/ -s
```

### Run specific test with debugger
```bash
mise x -- uv run pytest packages/dotfiles_cli/tests/test_utils.py::test_name --pdb
```

### Show test durations
```bash
mise x -- uv run pytest packages/dotfiles_cli/tests/ --durations=10
```

## Best Practices

1. **Test one thing at a time**: Each test should verify a single behavior
2. **Use descriptive names**: Test names should describe what they test
3. **Arrange-Act-Assert**: Structure tests with clear setup, execution, and verification
4. **Mock external dependencies**: Keep tests fast and isolated
5. **Test both success and failure paths**: Verify error handling
6. **Use fixtures for common setup**: Reduce duplication
7. **Document edge cases**: Explain why specific edge cases are tested

## Maintenance

- **Review tests** when updating code
- **Update fixtures** when adding new features
- **Refactor duplicated code** into fixtures or helper functions
- **Keep tests fast**: Slow tests get ignored
- **Monitor coverage**: Use `--cov` to track coverage trends
