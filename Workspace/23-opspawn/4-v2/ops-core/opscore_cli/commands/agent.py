import click
import json
from opscore_sdk.client import OpsCoreClientSync
from opscore_sdk.exceptions import OpsCoreSDKError, OpsCoreApiError
# AgentState enum is not defined in the SDK models, state is handled as string.

# Helper function to create the SDK client from context
def _get_client(ctx: click.Context) -> OpsCoreClientSync:
    """Creates an OpsCoreClientSync instance from click context."""
    api_url = ctx.obj['API_URL']
    api_key = ctx.obj.get('API_KEY') # Use .get() as API key might be optional
    return OpsCoreClientSync(base_url=api_url, api_key=api_key)

@click.group("agent")
def agent_group():
    """Commands for interacting with Ops-Core agents."""
    pass

@agent_group.command("get-state")
@click.argument("agent_id", type=str)
@click.pass_context
def get_state(ctx: click.Context, agent_id: str):
    """Get the current state of a specific agent."""
    client = _get_client(ctx)
    try:
        state_info = client.get_agent_state(agent_id=agent_id)
        # state_info is likely a TypedDict or similar structure from the SDK
        click.echo(json.dumps(state_info, indent=2))
    except OpsCoreApiError as e:
        click.echo(f"Error getting agent state from API: {e.status_code} - {e.detail}", err=True)
    except OpsCoreSDKError as e:
        click.echo(f"SDK Error getting agent state: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

@agent_group.command("update-state")
@click.argument("agent_id", type=str)
@click.argument("state", type=str) # State validation happens server-side or in SDK client
@click.option("--details", type=str, default=None, help="Optional JSON string with additional state details.")
@click.pass_context
def update_state(ctx: click.Context, agent_id: str, state: str, details: str | None):
    """Update the state of a specific agent."""
    client = _get_client(ctx)
    parsed_details = None
    if details:
        try:
            parsed_details = json.loads(details)
            if not isinstance(parsed_details, dict):
                click.echo("Error: --details must be a valid JSON object (dictionary).", err=True)
                return
        except json.JSONDecodeError as e:
            click.echo(f"Error parsing --details JSON: {e}", err=True)
            return

    try:
        # Assuming the SDK client and the API handle the state string validation.
        client.update_agent_state(agent_id=agent_id, state=state, details=parsed_details)
        click.echo(f"Successfully requested state update for agent '{agent_id}' to '{state}'.")
    except OpsCoreApiError as e:
        click.echo(f"Error updating agent state via API: {e.status_code} - {e.detail}", err=True)
    except OpsCoreSDKError as e:
        click.echo(f"SDK Error updating agent state: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

# Add other agent-related commands here if needed in the future