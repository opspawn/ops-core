import click
import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Import command groups
from .commands import agent, workflow

@click.group()
@click.version_option(package_name='opscore-cli') # Assuming we'll package this later
@click.option('--api-url', envvar='OPSCORE_API_URL', help='Ops-Core API URL (can also be set via OPSCORE_API_URL env var).')
@click.option('--api-key', envvar='OPSCORE_API_KEY', help='Ops-Core API Key (can also be set via OPSCORE_API_KEY env var).')
@click.pass_context
def cli(ctx, api_url, api_key):
    """
    A CLI tool to interact with the Ops-Core API using the opscore-sdk.
    """
    if not api_url:
        # Default to localhost if not provided
        api_url = "http://localhost:8000"
        click.echo(f"Warning: OPSCORE_API_URL not set, defaulting to {api_url}", err=True)

    # Store config in context for commands to use
    ctx.ensure_object(dict)
    ctx.obj['API_URL'] = api_url
    ctx.obj['API_KEY'] = api_key # Can be None if not set/required

# Add command groups to the main cli group
cli.add_command(agent.agent_group)
cli.add_command(workflow.workflow_group)

if __name__ == '__main__':
    cli()