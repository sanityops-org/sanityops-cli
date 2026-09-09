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

"""API exception definitions for sanityops CLI."""

from sanityops_cli.exceptions.base_exceptions import SanityopsError


class APIError(SanityopsError):
    """Base exception for API-related errors."""

    exit_code: int = 5


class AuthenticationError(APIError):
    """Authentication failed (401/403).

    The API key is invalid, expired, or lacks required permissions.
    """

    exit_code: int = 5


class ProjectNotFoundError(APIError):
    """Project not found (404).

    The specified project ID does not exist or user lacks access.
    """

    exit_code: int = 6


class NetworkError(APIError):
    """Network-related error.

    Connection timeout, DNS failure, or other network issues.
    """

    exit_code: int = 7


class APIValidationError(APIError):
    """Validation error (422).

    Request parameters failed validation.
    """

    exit_code: int = 2
