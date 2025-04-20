"""
Synchronous and Asynchronous Python clients for interacting with the Ops-Core API.
"""

import httpx
from typing import Optional, Dict, Any, Type, TypeVar, cast
from datetime import datetime, timezone
import json

from .models import StateUpdatePayload, WorkflowTriggerPayload, WorkflowTriggerResponse, AgentStateResponse
from .exceptions import OpsCoreSDKError, OpsCoreApiError, AuthenticationError, NotFoundError, ConnectionError

T = TypeVar('T', bound=Dict[str, Any]) # Type variable for response models

class OpsCoreClientSync:
    """Synchronous client for the Ops-Core API."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0):
        """
        Initializes the synchronous Ops-Core client.

        Args:
            base_url: The base URL of the Ops-Core API (e.g., "http://localhost:8000").
            api_key: The API key for authentication.
            timeout: Request timeout in seconds.
        """
        if not base_url:
            raise ValueError("base_url cannot be empty")
        if not api_key:
            raise ValueError("api_key cannot be empty")

        self._base_url = base_url.rstrip('/')
        self._api_key = api_key
        self._timeout = timeout
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=self._timeout,
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        expected_status: int = 200,
        response_model: Optional[Type[T]] = None
    ) -> Optional[T]:
        """
        Internal helper to make synchronous HTTP requests.

        Args:
            method: HTTP method (e.g., "GET", "POST").
            endpoint: API endpoint path (e.g., "/v1/opscore/agent/123/state").
            payload: Optional request body data.
            expected_status: The expected HTTP status code for success.
            response_model: The TypedDict model to parse the response into.

        Returns:
            Parsed response data as the specified TypedDict model, or None if no model specified.

        Raises:
            ConnectionError: If there's a network issue.
            AuthenticationError: If authentication fails (401/403).
            NotFoundError: If the resource is not found (404).
            OpsCoreApiError: For other API errors (non-2xx status codes).
            OpsCoreSDKError: For unexpected errors during the request or response parsing.
        """
        url = f"{self._base_url}{endpoint}"
        try:
            response = self._client.request(
                method=method,
                url=url, # Use full URL here as base_url is handled by client instance
                json=payload if payload else None,
            )

            if response.status_code == expected_status:
                if not response_model:
                    return None # Success, but no response body expected/parsed
                try:
                    # Handle cases where response might be empty even if model is expected
                    if not response.content:
                         # This might happen for 202 Accepted with no body, treat as success
                         if expected_status == 202:
                             return None
                         else:
                             raise OpsCoreSDKError(f"API returned expected status {expected_status} but with empty body.")

                    # Parse JSON and cast to the expected TypedDict model
                    # Note: TypedDict doesn't validate at runtime, assumes structure matches
                    return cast(T, response.json())
                except json.JSONDecodeError as e:
                    raise OpsCoreSDKError(f"Failed to decode JSON response: {e}")
                except Exception as e: # Catch potential casting or other issues
                    raise OpsCoreSDKError(f"Error processing successful response: {e}")

            # Handle API errors
            detail: str | Dict | None = None
            try:
                # Attempt to parse error detail from response body
                error_data = response.json()
                if isinstance(error_data, dict) and 'detail' in error_data:
                    detail = error_data['detail']
                else:
                    detail = response.text # Fallback to raw text
            except json.JSONDecodeError:
                detail = response.text # Fallback if body is not JSON

            if response.status_code in [401, 403]:
                raise AuthenticationError(response.status_code, detail)
            elif response.status_code == 404:
                raise NotFoundError(response.status_code, detail)
            else:
                raise OpsCoreApiError(response.status_code, detail)

        except httpx.TimeoutException as e:
            raise ConnectionError(f"Request timed out: {e}")
        except httpx.RequestError as e:
            # Includes network errors, connection issues etc.
            raise ConnectionError(f"HTTP request failed: {e}")
        except OpsCoreSDKError: # Re-raise SDK errors from parsing etc.
             raise
        except Exception as e: # Catch any other unexpected errors
            raise OpsCoreSDKError(f"An unexpected error occurred: {e}")

    def update_state(self, agent_id: str, state: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Updates the state of a specific agent.

        Args:
            agent_id: The unique ID of the agent.
            state: The new state string (e.g., "idle", "active").
            details: Optional dictionary with additional state details.

        Raises:
            ConnectionError: If there's a network issue.
            AuthenticationError: If authentication fails.
            NotFoundError: If the agent is not found.
            OpsCoreApiError: For other API errors.
            OpsCoreSDKError: For unexpected errors.
        """
        if not agent_id:
            raise ValueError("agent_id cannot be empty")
        if not state:
            raise ValueError("state cannot be empty")

        endpoint = f"/v1/opscore/agent/{agent_id}/state"
        # API expects timestamp, generate it here
        timestamp = datetime.now(timezone.utc).isoformat()
        payload: StateUpdatePayload = { # Use the TypedDict for structure hint
            "agentId": agent_id, # API payload requires agentId
            "timestamp": timestamp,
            "state": state,
            "details": details
        }
        # API returns 202 Accepted on success with a simple status message,
        # which we don't need to parse here.
        self._request(
            method="POST",
            endpoint=endpoint,
            payload=cast(Dict[str, Any], payload), # Cast for _request arg type
            expected_status=202,
            response_model=None # Don't need to parse the StatusResponse body
        )
        # No return value on success

    def get_state(self, agent_id: str) -> AgentStateResponse:
        """
        Retrieves the current state of a specific agent.

        Args:
            agent_id: The unique ID of the agent.

        Returns:
            An AgentStateResponse dictionary containing the agent's state details.

        Raises:
            ConnectionError: If there's a network issue.
            AuthenticationError: If authentication fails.
            NotFoundError: If the agent is not found.
            OpsCoreApiError: For other API errors.
            OpsCoreSDKError: For unexpected errors.
        """
        if not agent_id:
            raise ValueError("agent_id cannot be empty")

        endpoint = f"/v1/opscore/agent/{agent_id}/state"
        response_data = self._request(
            method="GET",
            endpoint=endpoint,
            expected_status=200,
            response_model=AgentStateResponse # Expect AgentState model back
        )
        if response_data is None:
             # Should not happen if _request works correctly and API returns valid data
             raise OpsCoreSDKError("Received None response when AgentStateResponse was expected.")
        return response_data # Type checked by response_model arg

    def trigger_workflow(
        self,
        agent_id: str,
        workflow_definition_id: str,
        initial_payload: Optional[Dict[str, Any]] = None
    ) -> WorkflowTriggerResponse:
        """
        Triggers a workflow for a specific agent using a predefined workflow definition ID.

        Args:
            agent_id: The unique ID of the agent to associate the workflow with.
            workflow_definition_id: The ID of the pre-registered workflow definition.
            initial_payload: Optional dictionary containing data for the first task.

        Returns:
            A WorkflowTriggerResponse dictionary containing the session ID and workflow ID.

        Raises:
            ConnectionError: If there's a network issue.
            AuthenticationError: If authentication fails.
            NotFoundError: If the agent or workflow definition is not found.
            OpsCoreApiError: For other API errors (e.g., bad request).
            OpsCoreSDKError: For unexpected errors.
        """
        if not agent_id:
            raise ValueError("agent_id cannot be empty")
        if not workflow_definition_id:
            raise ValueError("workflow_definition_id cannot be empty")

        endpoint = f"/v1/opscore/agent/{agent_id}/workflow"
        payload: WorkflowTriggerPayload = {
            "workflowDefinitionId": workflow_definition_id,
            "initialPayload": initial_payload
        }
        response_data = self._request(
            method="POST",
            endpoint=endpoint,
            payload=cast(Dict[str, Any], payload), # Cast for _request arg type
            expected_status=202,
            response_model=WorkflowTriggerResponse # Expect this model back
        )
        if response_data is None:
             # Should not happen if _request works correctly and API returns valid data
             raise OpsCoreSDKError("Received None response when WorkflowTriggerResponse was expected.")
        return response_data # Type checked by response_model arg

    def close(self) -> None:
        """Closes the underlying HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# --- Asynchronous Client ---

class OpsCoreClientAsync:
    """Asynchronous client for the Ops-Core API."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0):
        """
        Initializes the asynchronous Ops-Core client.

        Args:
            base_url: The base URL of the Ops-Core API (e.g., "http://localhost:8000").
            api_key: The API key for authentication.
            timeout: Request timeout in seconds.
        """
        if not base_url:
            raise ValueError("base_url cannot be empty")
        if not api_key:
            raise ValueError("api_key cannot be empty")

        self._base_url = base_url.rstrip('/')
        self._api_key = api_key
        self._timeout = timeout
        # Use AsyncClient for async operations
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=self._timeout,
        )

    async def _request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        expected_status: int = 200,
        response_model: Optional[Type[T]] = None
    ) -> Optional[T]:
        """
        Internal helper to make asynchronous HTTP requests.

        Args:
            method: HTTP method (e.g., "GET", "POST").
            endpoint: API endpoint path (e.g., "/v1/opscore/agent/123/state").
            payload: Optional request body data.
            expected_status: The expected HTTP status code for success.
            response_model: The TypedDict model to parse the response into.

        Returns:
            Parsed response data as the specified TypedDict model, or None if no model specified.

        Raises:
            ConnectionError: If there's a network issue.
            AuthenticationError: If authentication fails (401/403).
            NotFoundError: If the resource is not found (404).
            OpsCoreApiError: For other API errors (non-2xx status codes).
            OpsCoreSDKError: For unexpected errors during the request or response parsing.
        """
        url = f"{self._base_url}{endpoint}"
        try:
            # Use await for async request
            response = await self._client.request(
                method=method,
                url=url,
                json=payload if payload else None,
            )

            if response.status_code == expected_status:
                if not response_model:
                    return None # Success, but no response body expected/parsed
                try:
                    # Handle cases where response might be empty even if model is expected
                    if not response.content:
                         # This might happen for 202 Accepted with no body, treat as success
                         if expected_status == 202:
                             return None
                         else:
                             raise OpsCoreSDKError(f"API returned expected status {expected_status} but with empty body.")

                    # Parse JSON and cast to the expected TypedDict model
                    return cast(T, response.json())
                except json.JSONDecodeError as e:
                    raise OpsCoreSDKError(f"Failed to decode JSON response: {e}")
                except Exception as e: # Catch potential casting or other issues
                    raise OpsCoreSDKError(f"Error processing successful response: {e}")

            # Handle API errors (same logic as sync)
            detail: str | Dict | None = None
            try:
                error_data = response.json()
                if isinstance(error_data, dict) and 'detail' in error_data:
                    detail = error_data['detail']
                else:
                    detail = response.text
            except json.JSONDecodeError:
                detail = response.text

            if response.status_code in [401, 403]:
                raise AuthenticationError(response.status_code, detail)
            elif response.status_code == 404:
                raise NotFoundError(response.status_code, detail)
            else:
                raise OpsCoreApiError(response.status_code, detail)

        except httpx.TimeoutException as e:
            raise ConnectionError(f"Request timed out: {e}")
        except httpx.RequestError as e:
            raise ConnectionError(f"HTTP request failed: {e}")
        except OpsCoreSDKError:
             raise
        except Exception as e:
            raise OpsCoreSDKError(f"An unexpected error occurred: {e}")

    async def update_state(self, agent_id: str, state: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Asynchronously updates the state of a specific agent.

        Args:
            agent_id: The unique ID of the agent.
            state: The new state string (e.g., "idle", "active").
            details: Optional dictionary with additional state details.

        Raises:
            ConnectionError, AuthenticationError, NotFoundError, OpsCoreApiError, OpsCoreSDKError.
        """
        if not agent_id:
            raise ValueError("agent_id cannot be empty")
        if not state:
            raise ValueError("state cannot be empty")

        endpoint = f"/v1/opscore/agent/{agent_id}/state"
        timestamp = datetime.now(timezone.utc).isoformat()
        payload: StateUpdatePayload = {
            "agentId": agent_id,
            "timestamp": timestamp,
            "state": state,
            "details": details
        }
        # Use await for the async request
        await self._request(
            method="POST",
            endpoint=endpoint,
            payload=cast(Dict[str, Any], payload),
            expected_status=202,
            response_model=None
        )

    async def get_state(self, agent_id: str) -> AgentStateResponse:
        """
        Asynchronously retrieves the current state of a specific agent.

        Args:
            agent_id: The unique ID of the agent.

        Returns:
            An AgentStateResponse dictionary containing the agent's state details.

        Raises:
            ConnectionError, AuthenticationError, NotFoundError, OpsCoreApiError, OpsCoreSDKError.
        """
        if not agent_id:
            raise ValueError("agent_id cannot be empty")

        endpoint = f"/v1/opscore/agent/{agent_id}/state"
        # Use await for the async request
        response_data = await self._request(
            method="GET",
            endpoint=endpoint,
            expected_status=200,
            response_model=AgentStateResponse
        )
        if response_data is None:
             raise OpsCoreSDKError("Received None response when AgentStateResponse was expected.")
        return response_data

    async def trigger_workflow(
        self,
        agent_id: str,
        workflow_definition_id: str,
        initial_payload: Optional[Dict[str, Any]] = None
    ) -> WorkflowTriggerResponse:
        """
        Asynchronously triggers a workflow for a specific agent using a predefined workflow definition ID.

        Args:
            agent_id: The unique ID of the agent to associate the workflow with.
            workflow_definition_id: The ID of the pre-registered workflow definition.
            initial_payload: Optional dictionary containing data for the first task.

        Returns:
            A WorkflowTriggerResponse dictionary containing the session ID and workflow ID.

        Raises:
            ConnectionError, AuthenticationError, NotFoundError, OpsCoreApiError, OpsCoreSDKError.
        """
        if not agent_id:
            raise ValueError("agent_id cannot be empty")
        if not workflow_definition_id:
            raise ValueError("workflow_definition_id cannot be empty")

        endpoint = f"/v1/opscore/agent/{agent_id}/workflow"
        payload: WorkflowTriggerPayload = {
            "workflowDefinitionId": workflow_definition_id,
            "initialPayload": initial_payload
        }
        # Use await for the async request
        response_data = await self._request(
            method="POST",
            endpoint=endpoint,
            payload=cast(Dict[str, Any], payload),
            expected_status=202,
            response_model=WorkflowTriggerResponse
        )
        if response_data is None:
             raise OpsCoreSDKError("Received None response when WorkflowTriggerResponse was expected.")
        return response_data

    async def close(self) -> None:
        """Closes the underlying async HTTP client."""
        await self._client.aclose() # Use aclose for async client

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()