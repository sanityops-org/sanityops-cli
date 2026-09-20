"""Getting Started panel for CLI help output."""

from rich.panel import Panel
from rich.text import Text

GETTING_STARTED_TEXT = """\
  1. Run 'deeplogic-cli init' to create the default configuration
  2. Edit .deeplogic/inspect_config.yaml to configure your project
  3. Run 'deeplogic-cli inspect' to start the inspection
  4. Run 'deeplogic-cli inspect repair' to generate fixes (optional)
  5. Run 'deeplogic-cli inspect cover' to apply fixes (optional)\
"""

ADVANCED_USAGE_TEXT = """\
  CI/CD Integration:
    1. Commit .deeplogic/inspect_config.yaml to the repository
    2. Set LLM API keys via environment variables (never commit sensitive keys)
    3. Run 'deeplogic-cli inspect' in the pipeline

  Config Command (deeplogic-cli config --help):
    View detailed configuration options and usage examples\
"""


def get_getting_started_panel() -> Panel:
    """Create the Getting Started panel for help output.

    Returns:
        A Rich Panel containing the 5-step Getting Started workflow.
    """
    return Panel(
        Text(GETTING_STARTED_TEXT, justify="left"),
        title="Getting Started",
        border_style="blue",
        padding=(0, 1),
    )


def get_advanced_usage_panel() -> Panel:
    """Create the Advanced Usage panel for help output.

    Returns:
        A Rich Panel containing CI/CD integration and config reference.
    """
    return Panel(
        Text(ADVANCED_USAGE_TEXT, justify="left"),
        title="Advanced Usage",
        border_style="cyan",
        padding=(0, 1),
    )
