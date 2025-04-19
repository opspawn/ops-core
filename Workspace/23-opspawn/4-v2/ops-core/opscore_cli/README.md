# Ops-Core CLI (`opscore-cli`)

A command-line interface for interacting with the Ops-Core API using the `opscore-sdk`.

## Installation

1.  **Ensure Ops-Core is running:** This CLI interacts with a running Ops-Core instance.
2.  **Install Dependencies:** Navigate to the root directory of the `ops-core` project and install requirements:
    ```bash
    pip install -r requirements.txt
    ```
    *(This installs `click` and the `opscore-sdk` dependencies).*

## Configuration

The CLI requires the Ops-Core API URL and potentially an API Key. Configure these using environment variables:

```bash
export OPSCORE_API_URL="http://localhost:8000" # Replace with your Ops-Core API URL
export OPSCORE_API_KEY="your_api_key_here"   # Optional: Only needed if API key auth is enabled on Ops-Core
```

Alternatively, you can use a `.env` file in the directory where you run the commands, or pass `--api-url` and `--api-key` options directly. If `OPSCORE_API_URL` is not set, it defaults to `http://localhost:8000`.

## Usage

Run the CLI commands using `python -m opscore_cli.main`:

**Agent Commands:**

*   **Get Agent State:**
    ```bash
    python -m opscore_cli.main agent get-state <AGENT_ID>
    ```
    *Example:* `python -m opscore_cli.main agent get-state agent-123`

*   **Update Agent State:**
    ```bash
    python -m opscore_cli.main agent update-state <AGENT_ID> <STATE> [--details '{"key": "value"}']
    ```
    *   `<STATE>` must be one of: `idle`, `active`, `error`.
    *Example:* `python -m opscore_cli.main agent update-state agent-123 active --details '{"current_task": "processing data"}'`

**Workflow Commands:**

*   **Trigger Workflow:**
    ```bash
    python -m opscore_cli.main workflow trigger <AGENT_ID> <WORKFLOW_NAME> [--payload '{"input": "data"}']
    ```
    *Example:* `python -m opscore_cli.main workflow trigger agent-123 data_processing_workflow --payload '{"source_file": "/path/to/data.csv"}'`

**Help:**

Get help for the main command or specific subcommands:

```bash
python -m opscore_cli.main --help
python -m opscore_cli.main agent --help
python -m opscore_cli.main workflow trigger --help
```

## Development

*(Add development notes here if needed, e.g., running tests specific to the CLI)*