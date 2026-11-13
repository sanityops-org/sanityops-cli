"""HTTP client for deeplogic SaaS API."""

from __future__ import annotations

import json
from typing import Any

import httpx

from deeplogic_cli.exceptions.api_exceptions import (
    APIError,
    AuthenticationError,
    NetworkError,
    ProjectNotFoundError,
)
from deeplogic_cli.exceptions.api_exceptions import (
    ValidationError as APIValidationError,
)


class DeeplogicClient:
    """HTTP client for deeplogic SaaS API.

    Handles authentication, request formatting, and error handling for all
    deeplogic API operations.

    Attributes:
        base_url: The base URL for the API (e.g., "https://api.deeplogic.com").
        api_key: The API key for Bearer token authentication.
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        token: str | None = None,
        timeout: float = 30.0,
    ):
        """Initialize the API client.

        Args:
            base_url: Base URL for the API (without trailing slash).
            api_key: API key for authentication (will be prefixed with "Bearer").
            token: JWT access token (optional). When provided, it takes precedence
                over api_key for defect-check / repair calls.
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token = token
        self.timeout = timeout

    def _get_headers(self) -> dict[str, str]:
        """Get common headers for API requests.

        A JWT token takes precedence over the API key; both are sent as Bearer.
        """
        credential = self.token or self.api_key
        return {
            "Authorization": f"Bearer {credential}",
            "Accept": "application/json",
        }

    def _unwrap_response(self, response_data: dict[str, Any]) -> dict[str, Any]:
        """Unwrap the standard API response envelope.

        The server returns responses in format: {code, data, message}
        This method extracts the 'data' field for easier consumption.

        Args:
            response_data: Raw response from the API.

        Returns:
            The 'data' field if present, otherwise the raw response.
        """
        if "data" in response_data and "code" in response_data:
            return response_data["data"] or {}
        return response_data

    def _handle_error(self, response: httpx.Response, operation: str) -> None:
        """Handle HTTP error responses and raise appropriate exceptions.

        Args:
            response: The HTTP response object.
            operation: Description of the operation for error messages.

        Raises:
            AuthenticationError: For 401/403 responses.
            ProjectNotFoundError: For 404 responses.
            APIValidationError: For 422 responses.
            APIError: For other HTTP errors.
        """
        status_code = response.status_code

        try:
            error_data = response.json()
            detail = error_data.get("detail", response.text)
        except json.JSONDecodeError:
            detail = response.text

        if status_code in (401, 403):
            raise AuthenticationError(
                f"Authentication failed during {operation}. "
                "Please check your API key is valid and not expired."
            )
        elif status_code == 404:
            raise ProjectNotFoundError(f"Resource not found during {operation}: {detail}")
        elif status_code == 422:
            raise APIValidationError(f"Validation error during {operation}: {detail}")
        else:
            raise APIError(f"API error during {operation} (HTTP {status_code}): {detail}")

    def _request_json(
        self,
        method: str,
        url: str,
        operation: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute an HTTP request, map transport failures to NetworkError, and unwrap JSON."""
        kwargs.setdefault("headers", self._get_headers())
        kwargs.setdefault("timeout", self.timeout)
        requester = httpx.get if method == "GET" else httpx.post

        try:
            response = requester(url, **kwargs)
        except httpx.ConnectError as e:
            raise NetworkError(f"Failed to connect to {self.base_url}: {e}") from e
        except httpx.TimeoutException as e:
            raise NetworkError(f"Request timed out: {e}") from e
        except httpx.HTTPError as e:
            raise NetworkError(f"HTTP error during {operation}: {e}") from e

        if response.status_code != 200:
            self._handle_error(response, operation)

        return self._unwrap_response(response.json())

    # ---------------------------------------------------------------------
    # Project Operations
    # ---------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a new project.

        Args:
            name: Project name (required, 1-200 chars).
            description: Optional project description.

        Returns:
            API response with project details including 'id'.

        Raises:
            AuthenticationError: If API key is invalid.
            APIValidationError: If request validation fails.
            NetworkError: If connection fails.
        """
        url = f"{self.base_url}/api/v1/projects/"
        payload: dict[str, Any] = {"name": name}
        if description:
            payload["description"] = description

        return self._request_json("POST", url, "project creation", json=payload)

    def get_project(
        self,
        project_id: str,
    ) -> dict[str, Any]:
        """Get a single project's details.

        Args:
            project_id: Project UUID.

        Returns:
            API response with project details including 'name' and 'project_id'.

        Raises:
            AuthenticationError: If API key is invalid.
            ProjectNotFoundError: If project doesn't exist.
            NetworkError: If connection fails.
        """
        url = f"{self.base_url}/api/v1/projects/{project_id}"
        return self._request_json("GET", url, "getting project")

    # ---------------------------------------------------------------------
    # Artifact Upload
    # ---------------------------------------------------------------------

    def upload_artifacts(
        self,
        project_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        prompt_content: str | None = None,
        tools_schema: str | None = None,
        skill_file: tuple[str, bytes] | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Upload artifacts and create/update a project with automatic version management.

        If project_id is NOT provided: creates a new project with the uploaded artifacts.
        If project_id IS provided: checks if artifacts have changed, creates new versions
        for changed artifacts, reuses existing versions for unchanged artifacts.

        Args:
            project_id: Existing project ID (for updates). If None, creates new project.
            name: Project name (required for new project).
            description: Project description.
            prompt_content: Merged prompt text content.
            tools_schema: JSON string of tools schema.
            skill_file: Tuple of (filename, bytes) for ZIP file.
            message: Version commit message.

        Returns:
            API response with project and version details.

        Raises:
            AuthenticationError: If API key is invalid.
            APIValidationError: If request validation fails.
            NetworkError: If connection fails.
        """
        url = f"{self.base_url}/api/v1/projects/upload"

        # Build multipart form data
        data: dict[str, Any] = {}
        if project_id:
            data["project_id"] = project_id
        if name:
            data["name"] = name
        if description:
            data["description"] = description
        if prompt_content:
            data["prompt_content"] = prompt_content
        if tools_schema:
            data["tools_schema"] = tools_schema
        if message:
            data["message"] = message

        files: dict[str, tuple[str, bytes, str]] | None = None
        if skill_file:
            filename, content = skill_file
            files = {"skill_file": (filename, content, "application/zip")}

        return self._request_json(
            "POST",
            url,
            "artifact upload",
            data=data,
            files=files,
        )

    # ---------------------------------------------------------------------
    # Version Operations
    # ---------------------------------------------------------------------

    def list_versions(
        self,
        project_id: str,
        page: int = 1,
        size: int = 10,
    ) -> dict[str, Any]:
        """List versions for a project.

        Args:
            project_id: Project UUID.
            page: Page number (1-indexed).
            size: Page size (1-100).

        Returns:
            API response with version list.

        Raises:
            AuthenticationError: If API key is invalid.
            ProjectNotFoundError: If project doesn't exist.
            NetworkError: If connection fails.
        """
        url = f"{self.base_url}/api/v1/projects/{project_id}/versions"
        params = {"page": page, "size": min(size, 100)}
        return self._request_json("GET", url, "listing versions", params=params)

    def get_version(
        self,
        project_id: str,
        version_id: str,
    ) -> dict[str, Any]:
        """Get a specific project version with its artifacts.

        Args:
            project_id: Project UUID.
            version_id: Version UUID.

        Returns:
            API response with version details including artifacts.

        Raises:
            AuthenticationError: If API key is invalid.
            ProjectNotFoundError: If project or version doesn't exist.
            NetworkError: If connection fails.
        """
        url = f"{self.base_url}/api/v1/projects/{project_id}/versions/{version_id}"
        return self._request_json("GET", url, "getting version")

    def get_project_artifacts(
        self,
        project_id: str,
        version_id: str | None = None,
    ) -> dict[str, Any]:
        """Get project artifacts with full content (prompts, skills, tools).

        This endpoint returns the actual content of each artifact, including
        schema_content for tools, content for prompts, and metadata for skills.

        Args:
            project_id: Project UUID.
            version_id: Optional version UUID. If None, returns latest version's artifacts.

        Returns:
            API response with:
                - prompts: list of prompt objects with 'content' field
                - skills: list of skill objects with metadata
                - tools: list of tools_schema objects with 'schema_content' field

        Raises:
            AuthenticationError: If API key is invalid.
            ProjectNotFoundError: If project doesn't exist.
            NetworkError: If connection fails.
        """
        url = f"{self.base_url}/api/v1/projects/{project_id}/artifacts"
        params = {}
        if version_id:
            params["version_id"] = version_id
        return self._request_json("GET", url, "getting project artifacts", params=params)

    # ---------------------------------------------------------------------
    # Defect Check Operations (require JWT token)
    # ---------------------------------------------------------------------

    def run_defect_check(
        self,
        project_id: str,
        level: str = "L1",
        version_id: str | None = None,
        enable_cross_check: bool = False,
    ) -> dict[str, Any]:
        """Trigger a server-side defect check for a project.

        Args:
            project_id: Project UUID.
            level: Check level L1/L2/L3.
            version_id: Optional project version UUID.
            enable_cross_check: Whether to run CROSS checks.

        Returns:
            API response with task_id / status.

        Raises:
            AuthenticationError: If the JWT token is invalid.
            APIError: For other HTTP errors.
        """
        url = f"{self.base_url}/api/v1/projects/{project_id}/defect-check/run"
        payload: dict[str, Any] = {"level": level}
        if version_id:
            payload["version_id"] = version_id
        if enable_cross_check:
            payload["enable_cross_check"] = True
        return self._request_json("POST", url, "running defect check", json=payload)

    def get_defect_check_records(self, project_id: str) -> dict[str, Any]:
        """List defect check records for a project (newest first)."""
        url = f"{self.base_url}/api/v1/projects/{project_id}/defect-check/records"
        return self._request_json("GET", url, "listing defect check records")

    def get_defect_check_progress(
        self,
        project_id: str,
        result_id: str,
    ) -> dict[str, Any]:
        """Get progress of a running defect check."""
        url = (
            f"{self.base_url}/api/v1/projects/{project_id}"
            f"/defect-check/records/{result_id}/progress"
        )
        return self._request_json("GET", url, "getting defect check progress")

    def get_defect_check_result(
        self,
        project_id: str,
        result_id: str,
    ) -> dict[str, Any]:
        """Get full defect check result detail for one record."""
        url = f"{self.base_url}/api/v1/projects/{project_id}/defect-check/results/{result_id}"
        return self._request_json("GET", url, "getting defect check result")

    def generate_repaired_skill(
        self,
        project_id: str,
        result_id: str,
        skill_id: str,
        language: str = "zh",
        regenerate: bool = False,
    ) -> dict[str, Any]:
        """Generate a complete repaired SKILL.md from all QDS defects."""
        url = (
            f"{self.base_url}/api/v1/projects/{project_id}"
            f"/defect-check/results/{result_id}/skills/{skill_id}/repaired-skill"
        )
        return self._post_repair(url, language, regenerate)

    def generate_repaired_tool(
        self,
        project_id: str,
        result_id: str,
        tool_index: int,
        language: str = "zh",
        regenerate: bool = False,
    ) -> dict[str, Any]:
        """Generate a complete repaired Tool JSON from all QDT defects."""
        url = (
            f"{self.base_url}/api/v1/projects/{project_id}"
            f"/defect-check/results/{result_id}/tools/{tool_index}/repaired-tool"
        )
        return self._post_repair(url, language, regenerate)

    def generate_repaired_prompt(
        self,
        project_id: str,
        result_id: str,
        language: str = "zh",
        regenerate: bool = False,
    ) -> dict[str, Any]:
        """Generate a complete repaired Prompt from all QDP defects."""
        url = (
            f"{self.base_url}/api/v1/projects/{project_id}"
            f"/defect-check/results/{result_id}/prompt/repaired-prompt"
        )
        return self._post_repair(url, language, regenerate)

    def _post_repair(
        self,
        url: str,
        language: str = "zh",
        regenerate: bool = False,
    ) -> dict[str, Any]:
        """Shared POST handler for the /repaired-* endpoints.

        Repair generation invokes the LLM and may exceed the default 30s
        timeout, so we use a longer 360s upstream timeout (the frontend uses
        6 minutes for this same call).
        """
        payload: dict[str, Any] = {"language": language, "regenerate": regenerate}
        return self._request_json(
            "POST",
            url,
            "generating repaired artifact",
            json=payload,
            timeout=360.0,
        )
