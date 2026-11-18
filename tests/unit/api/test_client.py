"""Unit tests for SanityopsClient."""

from unittest.mock import patch

import httpx
import pytest

from sanityops_cli.api.client import SanityopsClient
from sanityops_cli.exceptions.api_exceptions import (
    AuthenticationError,
    NetworkError,
    ProjectNotFoundError,
    ValidationError,
)


class TestSanityopsClient:
    """Tests for SanityopsClient."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = SanityopsClient(
            base_url="https://api.test.com",
            api_key="test_api_key_123",
        )

    def test_init(self):
        """Test client initialization."""
        assert self.client.base_url == "https://api.test.com"
        assert self.client.api_key == "test_api_key_123"
        assert self.client.timeout == 30.0

    def test_init_trailing_slash(self):
        """Test that trailing slash is stripped from base_url."""
        client = SanityopsClient("https://api.test.com/", "key")
        assert client.base_url == "https://api.test.com"

    def test_get_headers(self):
        """Test authorization header format."""
        headers = self.client._get_headers()
        assert headers["Authorization"] == "Bearer test_api_key_123"
        assert headers["Accept"] == "application/json"


class TestCreateProject:
    """Tests for create_project method."""

    def setup_method(self):
        self.client = SanityopsClient("https://api.test.com", "test_key")

    @patch("httpx.post")
    def test_create_project_success(self, mock_post):
        """Test successful project creation."""
        mock_response = httpx.Response(
            200,
            json={"id": "12345678-1234-1234-1234-123456789012", "name": "test-project"},
        )
        mock_post.return_value = mock_response

        result = self.client.create_project("test-project", "Test description")

        assert result["id"] == "12345678-1234-1234-1234-123456789012"
        assert result["name"] == "test-project"
        mock_post.assert_called_once()

        # Verify request payload
        call_args = mock_post.call_args
        assert call_args.kwargs["json"]["name"] == "test-project"
        assert call_args.kwargs["json"]["description"] == "Test description"

    @patch("httpx.post")
    def test_create_project_auth_error(self, mock_post):
        """Test authentication error handling."""
        mock_response = httpx.Response(401, json={"detail": "Invalid API key"})
        mock_post.return_value = mock_response

        with pytest.raises(AuthenticationError):
            self.client.create_project("test-project")

    @patch("httpx.post")
    def test_create_project_validation_error(self, mock_post):
        """Test validation error handling."""
        mock_response = httpx.Response(422, json={"detail": "Name too long"})
        mock_post.return_value = mock_response

        with pytest.raises(ValidationError):
            self.client.create_project("x" * 300)  # Too long name


class TestUploadArtifacts:
    """Tests for upload_artifacts method."""

    def setup_method(self):
        self.client = SanityopsClient("https://api.test.com", "test_key")

    @patch("httpx.post")
    def test_upload_new_project(self, mock_post):
        """Test uploading artifacts for a new project."""
        mock_response = httpx.Response(
            200,
            json={
                "id": "new-project-id",
                "version_id": "version-123",
                "artifacts": {
                    "prompt": {"status": "new"},
                    "tools": {"status": "new"},
                    "skill": {"status": "new"},
                },
            },
        )
        mock_post.return_value = mock_response

        result = self.client.upload_artifacts(
            name="new-project",
            prompt_content="Test prompt",
            tools_schema='[{"name": "test"}]',
            message="Initial upload",
        )

        assert result["id"] == "new-project-id"
        mock_post.assert_called_once()

    @patch("httpx.post")
    def test_upload_existing_project(self, mock_post):
        """Test uploading artifacts for an existing project."""
        mock_response = httpx.Response(
            200,
            json={
                "version_id": "version-456",
                "artifacts": {
                    "prompt": {"status": "reused"},
                },
            },
        )
        mock_post.return_value = mock_response

        result = self.client.upload_artifacts(
            project_id="existing-project-id",
            prompt_content="Updated prompt",
            message="Update",
        )

        assert result["version_id"] == "version-456"

    @patch("httpx.post")
    def test_upload_with_skill_file(self, mock_post):
        """Test uploading with skill ZIP file."""
        mock_response = httpx.Response(200, json={"version_id": "v1"})
        mock_post.return_value = mock_response

        skill_zip = ("skills.zip", b"PK\x03\x04...")  # Minimal ZIP header

        result = self.client.upload_artifacts(
            project_id="proj-123",
            skill_file=skill_zip,
        )

        assert result["version_id"] == "v1"
        mock_post.assert_called_once()


class TestGetProject:
    """Tests for get_project method."""

    def setup_method(self):
        self.client = SanityopsClient("https://api.test.com", "test_key")

    @patch("httpx.get")
    def test_get_project_success(self, mock_get):
        """Test getting project details."""
        mock_response = httpx.Response(
            200,
            json={
                "data": {
                    "project_id": "12345678-1234-1234-1234-123456789012",
                    "name": "defect-management",
                    "description": "A test project",
                },
                "code": 200,
            },
        )
        mock_get.return_value = mock_response

        result = self.client.get_project("12345678-1234-1234-1234-123456789012")

        assert result["project_id"] == "12345678-1234-1234-1234-123456789012"
        assert result["name"] == "defect-management"
        mock_get.assert_called_once()
        # Verify request URL
        call_args = mock_get.call_args
        assert (
            call_args.args[0]
            == "https://api.test.com/api/v1/projects/12345678-1234-1234-1234-123456789012"
        )

    @patch("httpx.get")
    def test_get_project_not_found(self, mock_get):
        """Test project not found error."""
        mock_response = httpx.Response(404, json={"detail": "Project not found"})
        mock_get.return_value = mock_response

        with pytest.raises(ProjectNotFoundError):
            self.client.get_project("nonexistent-proj")

    @patch("httpx.get")
    def test_get_project_auth_error(self, mock_get):
        """Test authentication error handling."""
        mock_response = httpx.Response(401, json={"detail": "Invalid API key"})
        mock_get.return_value = mock_response

        with pytest.raises(AuthenticationError):
            self.client.get_project("proj-123")


class TestListVersions:
    """Tests for list_versions method."""

    def setup_method(self):
        self.client = SanityopsClient("https://api.test.com", "test_key")

    @patch("httpx.get")
    def test_list_versions_success(self, mock_get):
        """Test listing versions."""
        mock_response = httpx.Response(
            200,
            json={
                "items": [
                    {"id": "v1", "created_at": "2026-08-21T10:00:00Z", "message": "First"},
                    {"id": "v2", "created_at": "2026-08-21T11:00:00Z", "message": "Second"},
                ],
                "total": 2,
            },
        )
        mock_get.return_value = mock_response

        result = self.client.list_versions("proj-123", page=1, size=10)

        assert len(result["items"]) == 2
        assert result["total"] == 2

    @patch("httpx.get")
    def test_list_versions_not_found(self, mock_get):
        """Test project not found error."""
        mock_response = httpx.Response(404, json={"detail": "Project not found"})
        mock_get.return_value = mock_response

        with pytest.raises(ProjectNotFoundError):
            self.client.list_versions("nonexistent-proj")


class TestGetVersion:
    """Tests for get_version method."""

    def setup_method(self):
        self.client = SanityopsClient("https://api.test.com", "test_key")

    @patch("httpx.get")
    def test_get_version_success(self, mock_get):
        """Test getting version details."""
        mock_response = httpx.Response(
            200,
            json={
                "id": "version-123",
                "created_at": "2026-08-21T10:00:00Z",
                "message": "Test version",
                "artifacts": {
                    "prompt": {"hash": "abc123", "status": "new"},
                },
            },
        )
        mock_get.return_value = mock_response

        result = self.client.get_version("proj-123", "version-123")

        assert result["id"] == "version-123"
        assert result["message"] == "Test version"


class TestNetworkErrors:
    """Tests for network error handling."""

    def setup_method(self):
        self.client = SanityopsClient("https://api.test.com", "test_key")

    @patch("httpx.post")
    def test_connection_error(self, mock_post):
        """Test connection error handling."""
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(NetworkError):
            self.client.create_project("test")

    @patch("httpx.post")
    def test_timeout_error(self, mock_post):
        """Test timeout error handling."""
        mock_post.side_effect = httpx.TimeoutException("Request timed out")

        with pytest.raises(NetworkError):
            self.client.create_project("test")

    @patch("httpx.post")
    def test_remote_protocol_error(self, mock_post):
        """Test generic httpx.HTTPError (e.g. RemoteProtocolError) mapping."""
        mock_post.side_effect = httpx.RemoteProtocolError("Server disconnected without response")

        with pytest.raises(NetworkError):
            self.client.create_project("test")
