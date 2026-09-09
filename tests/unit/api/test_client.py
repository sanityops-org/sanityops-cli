# Copyright 2026 zipsonken
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Tests for sanityops_cli.api.client module."""

from unittest.mock import patch

import httpx
import pytest

from sanityops_cli.api.client import SanityopsClient
from sanityops_cli.exceptions.api_exceptions import (
    APIError,
    APIValidationError,
    AuthenticationError,
    NetworkError,
    ProjectNotFoundError,
)


class TestSanityopsClientInit:
    """Test SanityopsClient initialization."""

    def test_init_strips_trailing_slash_from_base_url(self) -> None:
        client = SanityopsClient("https://api.sanityops.org/", "test-key")
        assert client.base_url == "https://api.sanityops.org"

    def test_init_stores_api_key_and_timeout(self) -> None:
        client = SanityopsClient("https://api.sanityops.org", "test-key", timeout=60.0)
        assert client.api_key == "test-key"
        assert client.timeout == 60.0

    def test_default_timeout_is_30(self) -> None:
        client = SanityopsClient("https://api.sanityops.org", "test-key")
        assert client.timeout == 30.0


class TestSanityopsClientHeaders:
    """Test SanityopsClient header generation."""

    def test_get_headers_includes_bearer_token(self) -> None:
        client = SanityopsClient("https://api.sanityops.org", "my-api-key")
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer my-api-key"
        assert headers["Accept"] == "application/json"


class TestSanityopsClientCreateProject:
    """Test SanityopsClient.create_project method."""

    @patch("httpx.post")
    def test_create_project_success(self, mock_post) -> None:
        mock_response = httpx.Response(
            200,
            json={"code": 0, "data": {"project_id": "uuid-123", "name": "Test Project"}},
            request=httpx.Request("POST", "https://api.sanityops.org/api/v1/projects/"),
        )
        mock_post.return_value = mock_response

        client = SanityopsClient("https://api.sanityops.org", "test-key")
        result = client.create_project("Test Project", "Description")

        assert result["project_id"] == "uuid-123"
        assert result["name"] == "Test Project"

    @patch("httpx.post")
    def test_create_project_authentication_error(self, mock_post) -> None:
        mock_response = httpx.Response(
            401,
            json={"detail": "Invalid API key"},
            request=httpx.Request("POST", "https://api.sanityops.org/api/v1/projects/"),
        )
        mock_post.return_value = mock_response

        client = SanityopsClient("https://api.sanityops.org", "bad-key")

        with pytest.raises(AuthenticationError):
            client.create_project("Test Project")

    @patch("httpx.post")
    def test_create_project_validation_error(self, mock_post) -> None:
        mock_response = httpx.Response(
            422,
            json={"detail": "Name is required"},
            request=httpx.Request("POST", "https://api.sanityops.org/api/v1/projects/"),
        )
        mock_post.return_value = mock_response

        client = SanityopsClient("https://api.sanityops.org", "test-key")

        with pytest.raises(APIValidationError):
            client.create_project("")


class TestSanityopsClientUploadArtifacts:
    """Test SanityopsClient.upload_artifacts method."""

    @patch("httpx.post")
    def test_upload_artifacts_creates_new_project(self, mock_post) -> None:
        mock_response = httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "project_id": "uuid-456",
                    "version_id": "ver-789",
                },
            },
            request=httpx.Request("POST", "https://api.sanityops.org/api/v1/projects/upload"),
        )
        mock_post.return_value = mock_response

        client = SanityopsClient("https://api.sanityops.org", "test-key")
        result = client.upload_artifacts(
            name="New Project",
            prompt_content="Test prompt",
            tools_schema='[{"type": "function", "function": {"name": "test"}}]',
            message="Initial upload",
        )

        assert result["project_id"] == "uuid-456"
        assert result["version_id"] == "ver-789"

    @patch("httpx.post")
    def test_upload_artifacts_updates_existing_project(self, mock_post) -> None:
        mock_response = httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "project_id": "existing-uuid",
                    "version_id": "new-ver",
                },
            },
            request=httpx.Request("POST", "https://api.sanityops.org/api/v1/projects/upload"),
        )
        mock_post.return_value = mock_response

        client = SanityopsClient("https://api.sanityops.org", "test-key")
        result = client.upload_artifacts(
            project_id="existing-uuid",
            prompt_content="Updated prompt",
            message="Update",
        )

        assert result["project_id"] == "existing-uuid"

    @patch("httpx.post")
    def test_upload_artifacts_with_skill_file(self, mock_post) -> None:
        mock_response = httpx.Response(
            200,
            json={"code": 0, "data": {"version_id": "ver-123"}},
            request=httpx.Request("POST", "https://api.sanityops.org/api/v1/projects/upload"),
        )
        mock_post.return_value = mock_response

        client = SanityopsClient("https://api.sanityops.org", "test-key")
        skill_zip = ("skills.zip", b"PK\x03\x04...")

        result = client.upload_artifacts(
            project_id="proj-uuid",
            skill_file=skill_zip,
        )

        assert result["version_id"] == "ver-123"


class TestSanityopsClientErrorHandling:
    """Test SanityopsClient error handling."""

    @patch("httpx.post")
    def test_network_error_on_connection_failure(self, mock_post) -> None:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        client = SanityopsClient("https://api.sanityops.org", "test-key")

        with pytest.raises(NetworkError):
            client.create_project("Test")

    @patch("httpx.get")
    def test_project_not_found_error_404(self, mock_get) -> None:
        mock_response = httpx.Response(
            404,
            json={"detail": "Project not found"},
            request=httpx.Request("GET", "https://api.sanityops.org/api/v1/projects/nonexistent"),
        )
        mock_get.return_value = mock_response

        client = SanityopsClient("https://api.sanityops.org", "test-key")

        with pytest.raises(ProjectNotFoundError):
            client.get_project("nonexistent")

    @patch("httpx.post")
    def test_generic_api_error_for_500(self, mock_post) -> None:
        mock_response = httpx.Response(
            500,
            json={"detail": "Internal server error"},
            request=httpx.Request("POST", "https://api.sanityops.org/api/v1/projects/"),
        )
        mock_post.return_value = mock_response

        client = SanityopsClient("https://api.sanityops.org", "test-key")

        with pytest.raises(APIError) as exc_info:
            client.create_project("Test")

        assert "HTTP 500" in str(exc_info.value)


class TestSanityopsClientResponseUnwrapping:
    """Test SanityopsClient response unwrapping."""

    def test_unwrap_extracts_data_field(self) -> None:
        client = SanityopsClient("https://api.sanityops.org", "test-key")
        result = client._unwrap_response({"code": 0, "data": {"id": "123"}, "message": "OK"})
        assert result == {"id": "123"}

    def test_unwrap_returns_original_if_no_data_field(self) -> None:
        client = SanityopsClient("https://api.sanityops.org", "test-key")
        result = client._unwrap_response({"id": "456", "name": "Project"})
        assert result == {"id": "456", "name": "Project"}

    def test_unwrap_returns_empty_dict_for_null_data(self) -> None:
        client = SanityopsClient("https://api.sanityops.org", "test-key")
        result = client._unwrap_response({"code": 0, "data": None})
        assert result == {}
