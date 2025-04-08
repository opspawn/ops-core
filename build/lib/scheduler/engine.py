"""
In-memory implementation of the task scheduling engine for Ops Core.

This provides a basic, non-persistent scheduler suitable for development
and testing. It interacts with a metadata store to manage task states.
"""

import asyncio
import logging
import os # Added for environment variable access
import traceback
import uuid
from typing import Any, Dict, Optional

# Import dramatiq and broker configuration
import dramatiq
from ops_core.tasks import broker # Ensure broker is initialized

# Import dependencies container and getters
from ops_core.dependencies import get_metadata_store, get_mcp_client

from ops_core.metadata.store import InMemoryMetadataStore, TaskNotFoundError # Keep for type hints if needed
from ops_core.models import Task, TaskStatus
from ops_core.mcp_client.client import OpsMcpClient # Keep for type hints if needed
from ops_core.mcp_client.proxy_tool import MCPProxyTool

# Attempt agentkit imports
try:
    from agentkit.core.agent import Agent
    from agentkit.tools.registry import ToolRegistry
    from agentkit.memory.short_term import ShortTermMemory # Added
    from agentkit.planning.simple_planner import SimplePlanner # Added
except ImportError as e:
    Agent = None # Set to None if agentkit not available
    ToolRegistry = None
    ShortTermMemory = None # Added
    SimplePlanner = None # Added
    logging.warning(
        "Could not import agentkit. Agent execution will be skipped. "
        "Ensure agentkit package is installed."
    )

logger = logging.getLogger(__name__)


async def _run_agent_task_logic(
    task_id: str,
    task_input_data: Dict[str, Any],
    metadata_store: InMemoryMetadataStore,
    mcp_client: Optional[OpsMcpClient]
):
    """Core logic for executing an agent task."""
    # Use passed dependencies
    # Use module-level Agent and ToolRegistry directly
    ActualAgent = Agent
    ActualToolRegistry = ToolRegistry

    # Update status (assuming the store is accessible, e.g., DB or shared memory)
    # In a pure InMemoryStore scenario across processes, this update won't be seen by the main app.
    try:
        await metadata_store.update_task_status(task_id, TaskStatus.RUNNING)
        logger.info(f"[Actor] Task {task_id} status updated to RUNNING (in worker context).")
    except TaskNotFoundError:
        logger.error(f"[Actor] Task {task_id} not found in metadata store. Cannot update status.")
        # Decide how to handle this - maybe the task was deleted? Exit actor?
        return # Exit if task doesn't exist
    except Exception as store_err:
        logger.error(f"[Actor] Error updating task {task_id} status: {store_err}", exc_info=True)
        # Proceed with execution attempt? Or fail here? For now, proceed.

    # Execute Agent
    task_result: Any = None
    task_error: Optional[str] = None
    final_status_name: str = TaskStatus.COMPLETED.name # Default to completed

    # Use "prompt" key as per test input, fallback to "goal" or default
    goal = task_input_data.get("prompt", task_input_data.get("goal", "No goal specified."))
    inject_mcp = task_input_data.get("inject_mcp_proxy", False) # Check if proxy injection is requested
    logger.info(f"[Actor] Executing agent task {task_id} with goal: '{goal}'")

    if ActualAgent is None or ActualToolRegistry is None:
        logger.error(f"[Actor] Cannot execute agent task {task_id}: agentkit components (Agent/ToolRegistry) not available.")
        task_error = "Agent execution failed: agentkit components not available."
        final_status_name = TaskStatus.FAILED.name
    else:
        try:
            # Instantiate agent components using the determined classes
            tool_registry = ActualToolRegistry()
            if inject_mcp and mcp_client:
                # Use the mcp_client obtained from the dependency container
                proxy_tool = MCPProxyTool(mcp_client=mcp_client) # Assuming MCPProxyTool is available
                tool_registry.add_tool(proxy_tool)
                logger.info(f"[Actor] Injected MCP Proxy Tool for task {task_id}")
            elif inject_mcp and not mcp_client:
                 logger.warning(f"[Actor] MCP Proxy Tool injection requested but MCP client not available for task {task_id}")


            # Instantiate agent components using the determined classes
            # TODO: Allow configuration of planner/memory types via input_data
            planner_instance = SimplePlanner() if SimplePlanner else None
            memory_instance = ShortTermMemory() if ShortTermMemory else None

            agent = ActualAgent( # Use the determined class
                planner=planner_instance,
                memory=memory_instance,
                tool_manager=tool_registry
            )
            logger.debug(f"[Actor] Instantiated Agent for task {task_id}")

            # Run the agent task (Needs to be sync or handled differently in actor)
            # agent_result_data = await agent.run_async(goal=goal) # Actors are typically sync
            # For now, let's assume a synchronous run method exists or adapt
            # If run_async is essential, the actor itself might need to manage an event loop
            # Placeholder for synchronous execution concept:
            try:
                # --- Load Test Mocking Logic ---
                mock_delay_ms_str = os.environ.get("OPS_CORE_LOAD_TEST_MOCK_AGENT_DELAY_MS")
                mock_delay_s = None
                if mock_delay_ms_str:
                    try:
                        mock_delay_s = int(mock_delay_ms_str) / 1000.0
                        if mock_delay_s < 0:
                            mock_delay_s = None # Ignore negative values
                    except ValueError:
                        logger.warning(f"[Actor] Invalid OPS_CORE_LOAD_TEST_MOCK_AGENT_DELAY_MS value: {mock_delay_ms_str}. Ignoring.")
                        mock_delay_s = None

                if mock_delay_s is not None:
                    logger.info(f"[Actor] Load test mode: Mocking agent.run with {mock_delay_s:.3f}s delay for task {task_id}.")
                    await asyncio.sleep(mock_delay_s)
                    agent_result_data = {"output": f"Mocked agent result after {mock_delay_s:.3f}s delay."}
                    logger.debug(f"[Actor] Mock agent run completed for task {task_id}.")
                # --- End Load Test Mocking Logic ---
                else:
                    # Attempt synchronous execution if available, otherwise log limitation
                    if hasattr(agent, 'run'):
                         agent_result_data = agent.run(goal=goal) # Hypothetical sync method
                    else:
                         # If only async exists, we need to run it within the actor's context
                         # This requires careful handling, e.g., using asyncio.run() if appropriate
                         # or structuring the worker differently.
                         # For simplicity now, log limitation.
                         logger.warning(f"[Actor] Agent {task_id} only has async run. Synchronous execution placeholder used.")
                         agent_result_data = "Placeholder: Sync execution needed or async handling in actor."
                         # TODO: Implement proper async execution within actor if required.

                # Construct result including memory history if available
                # Extract final output string if agent_result_data is a dict
                if isinstance(agent_result_data, dict):
                    final_output = agent_result_data.get("output", agent_result_data) # Default to the whole dict if 'output' key missing
                else:
                    final_output = agent_result_data # Assume it's already the final output

                memory_history = []
                if hasattr(agent, 'memory') and agent.memory is not None and hasattr(agent.memory, 'get_history'):
                    memory_history = agent.memory.get_history() # Fetch history

                # Corrected task_result structure
                task_result = {"memory_history": memory_history, "final_output": final_output}

                logger.info(f"[Actor] Agent task {task_id} completed. Result: {task_result}")
                final_status_name = TaskStatus.COMPLETED.name

            except Exception as agent_err:
                logger.error(f"[Actor] Agent task {task_id} failed: {agent_err}", exc_info=True)
                task_error = f"{type(agent_err).__name__}: {agent_err}\n{traceback.format_exc()}"
                final_status_name = TaskStatus.FAILED.name

        except Exception as setup_err:
             logger.error(f"[Actor] Error setting up agent for task {task_id}: {setup_err}", exc_info=True)
             # Include exception type and traceback in the error message
             task_error = f"{type(setup_err).__name__}: {setup_err}\n{traceback.format_exc()}"
             final_status_name = TaskStatus.FAILED.name

        # Update status and result/error in the metadata store
        # Update status and result/error in the metadata store
        # Update status and result/error in the metadata store
        # Update status and result/error in the metadata store
        final_status = TaskStatus[final_status_name]
        try:
            # Update output/error first using the public method
            await metadata_store.update_task_output(
                task_id=task_id,
                output_data=task_result if final_status == TaskStatus.COMPLETED else None,
                error_message=task_error if final_status == TaskStatus.FAILED else None
            )
            # Then update the final status using the public method
            await metadata_store.update_task_status(task_id, final_status)
            logger.info(f"[Actor] Task {task_id} finished. Status updated to {final_status.name} (in worker context).")
            if final_status == TaskStatus.FAILED:
                logger.error(f"[Actor] Task {task_id} Error Details: {task_error}") # Log the error directly

        except TaskNotFoundError:
             logger.error(f"[Actor] Task {task_id} not found during final status/output update call.")
        except Exception as final_update_err:
            logger.error(f"[Actor] Error during final status/output update for task {task_id}: {final_update_err}", exc_info=True)


class InMemoryScheduler:
    """
    Manages task submission and basic processing using an in-memory approach.

    Interacts with an InMemoryMetadataStore to track task states. Includes a
    simple background loop to simulate task execution or run agentkit agents.
    """

    def __init__(
        self,
        metadata_store: InMemoryMetadataStore,
        mcp_client: OpsMcpClient, # Correct type hint
        processing_interval: float = 2.0,
    ):
        """
        Initializes the scheduler with a metadata store and MCP client.

        Args:
            metadata_store: An instance of InMemoryMetadataStore.
            mcp_client: An instance of OpsMcpClient for proxy tool injection.
            processing_interval: How often (in seconds) the scheduler checks for pending tasks.
        """
        if Agent is None:
             # Reason: Log a clear warning if agentkit is missing, preventing agent runs.
             logger.error("agentkit not found. Agent execution disabled.")

        self._metadata_store = metadata_store
        self._mcp_client = mcp_client # Store MCPClient instance (still needed for potential future non-actor tasks or proxy injection logic if adapted)
        # Removed state related to internal processing loop:
        # self._processing_interval = processing_interval
        # self._processing_task: Optional[asyncio.Task] = None
        # self._active_agent_tasks: Dict[str, asyncio.Task] = {}
        # self._stop_event = asyncio.Event()
        logger.info("InMemoryScheduler initialized (Dramatiq integration).")

    async def submit_task(
        self, name: str, task_type: str, input_data: Optional[Dict[str, Any]] = None
    ) -> Task:
        """
        Creates a new task, adds it to the metadata store, and returns it.

        Args:
            name: A human-readable name for the task.
            task_type: The type or category of the task (e.g., 'agent_run').
            input_data: Optional dictionary containing input parameters for the task.

        Returns:
            The newly created Task object.
        """
        task_id = f"task_{uuid.uuid4()}" # Add prefix for clarity
        new_task = Task(
            task_id=task_id, # Use correct field name
            name=name,
            task_type=task_type,
            status=TaskStatus.PENDING,
            input_data=input_data or {},
        )
        await self._metadata_store.add_task(new_task)
        logger.info(f"Task submitted: {task_id} (Type: {task_type}, Name: {name})")

        # If it's an agent task and agentkit is available, send it to the Dramatiq queue
        if task_type == "agent_run" and Agent is not None:
            logger.info(f"Sending agent task {task_id} to Dramatiq queue.")
            # Send only task ID and input data
            execute_agent_task_actor.send(task_id, new_task.input_data)
        elif task_type == "agent_run" and Agent is None:
            logger.error(f"Cannot queue agent task {task_id}: agentkit not installed.")
            # Mark as failed immediately if agentkit is missing
            # Fetch task to update error field, then update status
            task_to_fail = self._metadata_store._tasks.get(task_id) # Use self._metadata_store
            if task_to_fail:
                # Use the task's update_status helper
                task_to_fail.update_status(TaskStatus.FAILED, error_msg="Agent execution failed: agentkit not installed.")
                # No need to call store.update_task_status separately now
            else:
                 # If task somehow disappeared between add and here, log it
                 logger.error(f"Task {task_id} not found in store immediately after creation during agentkit check.")


        return new_task


# Define the Dramatiq actor - now a thin wrapper around the core logic
@dramatiq.actor(time_limit=300_000, store_results=True)
async def execute_agent_task_actor(
    task_id: str,
    task_input_data: Dict[str, Any],
) -> None:
    """
    Dramatiq actor wrapper for agent task execution.
    Fetches dependencies and calls the core logic function.
    """
    logger.info(f"[Actor Wrapper] Received agent task: {task_id}")
    # Fetch dependencies using getters
    metadata_store = get_metadata_store()
    mcp_client = get_mcp_client()

    # Call the core logic function
    await _run_agent_task_logic(
        task_id=task_id,
        task_input_data=task_input_data,
        metadata_store=metadata_store,
        mcp_client=mcp_client
    )

    # Removed _process_tasks method - agent tasks handled by Dramatiq workers

    async def start(self) -> None:
        """Placeholder start method. Dramatiq workers are started separately."""
        logger.info("Scheduler start method called (no internal loop to start).")
        # In a real app, this might initialize connections or other resources if needed.
        pass

    async def stop(self) -> None:
        """Placeholder stop method. Dramatiq workers are stopped separately."""
        logger.info("Scheduler stop method called (no internal loop to stop).")
        # In a real app, this might clean up resources or connections.
        pass


    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        Retrieves the status of a specific task.

        Args:
            task_id: The ID of the task.

        Returns:
            The TaskStatus if the task is found, otherwise None.
        """
        task = await self._metadata_store.get_task(task_id)
        return task.status if task else None
