import click
import json
from opscore_sdk.client import OpsCoreClientSync
from opscore_sdk.exceptions import OpsCoreSDKError, OpsCoreApiError

# Helper function to create the SDK client from context
# Note: This is duplicated from agent.py. Consider refactoring into a shared util later.
def _get_client(ctx: click.Context) -> OpsCoreClientSync:
    """Creates an OpsCoreClientSync instance from click context."""
    api_url = ctx.obj['API_URL']
    api_key = ctx.obj.get('API_KEY') # Use .get() as API key might be optional
    return OpsCoreClientSync(base_url=api_url, api_key=api_key)

@click.group("workflow")
def workflow_group():
    """Commands for interacting with Ops-Core workflows."""
    pass

@workflow_group.command("trigger")
@click.argument("agent_id", type=str)
@click.argument("workflow_name", type=str)
@click.option("--payload", type=str, default=None, help="Optional JSON string payload for the workflow.")
@click.pass_context
def trigger_workflow(ctx: click.Context, agent_id: str, workflow_name: str, payload: str | None):
    """Trigger a workflow for a specific agent."""
    client = _get_client(ctx)
    parsed_payload = None
    if payload:
        try:
            parsed_payload = json.loads(payload)
            # Basic validation: SDK likely expects a dict, but could be other JSON types
            # Add more specific validation if needed based on SDK/API requirements
            if not isinstance(parsed_payload, dict):
                 click.echo("Warning: --payload was parsed but is not a JSON object (dictionary).", err=True)
        except json.JSONDecodeError as e:
            click.echo(f"Error parsing --payload JSON: {e}", err=True)
            return

    try:
        # Assuming the SDK's trigger_workflow handles the payload structure
        response = client.trigger_workflow(
            agent_id=agent_id,
            workflow_name=workflow_name,
            payload=parsed_payload
        )
        # The SDK might return some confirmation or workflow ID
        click.echo(f"Successfully triggered workflow '{workflow_name}' for agent '{agent_id}'.")
        if response: # Check if the SDK returned anything useful
             try:
                 # Attempt to pretty-print if it looks like structured data
                 click.echo("API Response:")
                 click.echo(json.dumps(response, indent=2))
             except TypeError:
                 # Fallback for non-serializable responses
                 click.echo(str(response))

    except OpsCoreApiError as e:
        click.echo(f"Error triggering workflow via API: {e.status_code} - {e.detail}", err=True)
    except OpsCoreSDKError as e:
        click.echo(f"SDK Error triggering workflow: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

# Add other workflow-related commands here if needed