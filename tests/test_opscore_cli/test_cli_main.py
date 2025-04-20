import pytest
from click.testing import CliRunner
from opscore_cli.main import cli
from unittest.mock import patch

# Fixture for the CliRunner
@pytest.fixture
def runner():
    # Initialize with mix_stderr=False to allow checking result.stderr
    return CliRunner(mix_stderr=False)

def test_cli_invokes_without_error(runner):
    """Test that the CLI runs without crashing when called with no arguments."""
    result = runner.invoke(cli)
    # Expect it to show help message by default, exit code 0
    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.output

def test_cli_help_option(runner):
    """Test the --help option."""
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.output
    assert "A CLI tool to interact with the Ops-Core API" in result.output
    assert "agent" in result.output # Check if agent group is listed
    assert "workflow" in result.output # Check if workflow group is listed

# We need to mock the importlib.metadata.version call for --version
# as 'opscore-cli' is not actually installed as a package during tests.
@patch('importlib.metadata.version', return_value='0.1.0-test')
def test_cli_version_option(mock_version, runner):
    """Test the --version option."""
    result = runner.invoke(cli, ['--version'])
    assert result.exit_code == 0
    assert "cli, version 0.1.0-test" in result.output

def test_cli_api_url_default(runner):
    """Test that API URL defaults to localhost if not provided."""
    # Use 'agent get-state' as a command that requires context setup
    # We need to mock the client creation to avoid errors during context setup test
    with patch('opscore_cli.commands.agent._get_client') as mock_get_client:
        # Pass empty env, explicitly clearing potential external OPSCORE_API_KEY
        result = runner.invoke(cli, ['agent', 'get-state', 'test-agent'], env={'OPSCORE_API_KEY': ''})
        assert result.exit_code == 0 # Command itself might fail, but context setup should work
        assert "Warning: OPSCORE_API_URL not set, defaulting to http://localhost:8000" in result.stderr
        # Check if the context passed to the mocked client has the default URL
        mock_get_client.assert_called_once()
        call_context = mock_get_client.call_args[0][0] # Get the click context passed to _get_client
        assert call_context.obj['API_URL'] == "http://localhost:8000"
        assert call_context.obj['API_KEY'] is None

def test_cli_api_url_env_var(runner):
    """Test reading API URL from environment variable."""
    test_url = "http://test-env.com:1234"
    with patch('opscore_cli.commands.agent._get_client') as mock_get_client:
        # Explicitly clear potential external OPSCORE_API_KEY for this test
        result = runner.invoke(cli, ['agent', 'get-state', 'test-agent'], env={'OPSCORE_API_URL': test_url, 'OPSCORE_API_KEY': ''})
        assert result.exit_code == 0
        assert "Warning: OPSCORE_API_URL not set" not in result.stderr # No warning
        mock_get_client.assert_called_once()
        call_context = mock_get_client.call_args[0][0]
        assert call_context.obj['API_URL'] == test_url
        assert call_context.obj['API_KEY'] is None

def test_cli_api_url_option_override(runner):
    """Test that --api-url option overrides environment variable."""
    env_url = "http://test-env.com:1234"
    opt_url = "http://test-opt.com:5678"
    with patch('opscore_cli.commands.agent._get_client') as mock_get_client:
        # Explicitly clear potential external OPSCORE_API_KEY for this test
        result = runner.invoke(cli, ['--api-url', opt_url, 'agent', 'get-state', 'test-agent'], env={'OPSCORE_API_URL': env_url, 'OPSCORE_API_KEY': ''})
        assert result.exit_code == 0
        assert "Warning: OPSCORE_API_URL not set" not in result.stderr
        mock_get_client.assert_called_once()
        call_context = mock_get_client.call_args[0][0]
        assert call_context.obj['API_URL'] == opt_url # Option takes precedence
        assert call_context.obj['API_KEY'] is None

def test_cli_api_key_env_var(runner):
    """Test reading API Key from environment variable."""
    test_key = "test-api-key-env"
    with patch('opscore_cli.commands.agent._get_client') as mock_get_client:
        result = runner.invoke(cli, ['agent', 'get-state', 'test-agent'], env={'OPSCORE_API_KEY': test_key})
        assert result.exit_code == 0
        mock_get_client.assert_called_once()
        call_context = mock_get_client.call_args[0][0]
        assert call_context.obj['API_KEY'] == test_key

def test_cli_api_key_option_override(runner):
    """Test that --api-key option overrides environment variable."""
    env_key = "test-api-key-env"
    opt_key = "test-api-key-opt"
    with patch('opscore_cli.commands.agent._get_client') as mock_get_client:
        result = runner.invoke(cli, ['--api-key', opt_key, 'agent', 'get-state', 'test-agent'], env={'OPSCORE_API_KEY': env_key})
        assert result.exit_code == 0
        mock_get_client.assert_called_once()
        call_context = mock_get_client.call_args[0][0]
        assert call_context.obj['API_KEY'] == opt_key # Option takes precedence