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

"""Unit tests for --version output."""

from typer.testing import CliRunner

from sanityops_cli.main import app

runner = CliRunner()


def test_version_outputs_version_line():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "sanityops-cli v" in result.output


def test_version_outputs_copyright_line():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Copyright (C) 2026 zipsonken / Sanity AI Labs" in result.output


def test_version_outputs_license_line():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "License: Apache 2.0" in result.output


def test_version_does_not_output_on_other_commands():
    """Copyright should NOT appear in regular command help output."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Copyright" not in result.output