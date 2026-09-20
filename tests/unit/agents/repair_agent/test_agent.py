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

import pytest

from sanityops_cli.agents.repair_agent.agent import RepairAgent, _is_rate_limit_error


class TestIsRateLimitError:
    """Tests for _is_rate_limit_error helper."""

    def test_detects_429(self):
        """Detects 429 status code."""
        assert _is_rate_limit_error(Exception("Error 429: Too Many Requests")) is True

    def test_detects_rate_limit_text(self):
        """Detects 'rate limit' in message."""
        assert _is_rate_limit_error(Exception("Rate limit exceeded")) is True

    def test_detects_throttling_error(self):
        """Detects throttling_error marker."""
        assert _is_rate_limit_error(Exception("throttling_error: request blocked")) is True

    def test_detects_too_many_requests(self):
        """Detects 'too many requests' phrase."""
        assert _is_rate_limit_error(Exception("Too many requests, slow down")) is True

    def test_returns_false_for_other_errors(self):
        """Returns False for non-rate-limit errors."""
        assert _is_rate_limit_error(Exception("Connection refused")) is False
        assert _is_rate_limit_error(Exception("File not found")) is False
        assert _is_rate_limit_error(Exception("Invalid API key")) is False


class TestRepairAgentInit:
    """Tests for RepairAgent initialization."""

    def test_default_parameters(self):
        """Agent has sensible defaults."""
        agent = RepairAgent(provider=None)
        assert agent.max_loops == 30
        assert agent.timeout == 300
        assert agent.token_budget is None
        assert agent.llm_retries == 3
        assert agent.retry_delay == 65
        assert agent.verbose is False

    def test_custom_parameters(self):
        """Agent accepts custom parameters."""
        agent = RepairAgent(
            provider="mock_provider",
            max_loops=50,
            timeout=600,
            token_budget=500000,
            llm_retries=5,
            retry_delay=120,
            verbose=True,
        )
        assert agent.max_loops == 50
        assert agent.timeout == 600
        assert agent.token_budget == 500000
        assert agent.llm_retries == 5
        assert agent.retry_delay == 120
        assert agent.verbose is True
