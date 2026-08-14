from rich.console import Console
from rich.text import Text

from sanityops_cli.logging.logger import Logger


class ProgressHook:
    """Hook to report agent progress to console in real-time."""

    def __init__(
        self,
        console: Console,
        verbose: bool = True,
        logger: Logger | None = None,
    ):
        self.console = console
        self.verbose = verbose
        self.logger = logger
        self._iteration = 0
        self._tool_calls = 0
        self._sub_agent_count = 0
        # Will be set after lazy import
        self._events = None

    def _get_events(self):
        """Lazy import of HookEvent."""
        if self._events is None:
            from sanityops_agent.hooks.base import HookEvent
            self._events = HookEvent
        return self._events

    @property
    def name(self) -> str:
        return "progress"

    @property
    def description(self) -> str:
        return "Reports agent progress to console"

    @property
    def priority(self) -> int:
        return 5

    @property
    def events(self) -> list:
        """Return events this hook subscribes to."""
        events = self._get_events()
        return [
            events.BEFORE_LOOP,
            events.BEFORE_LLM_CALL,
            events.AFTER_LLM_CALL,
            events.BEFORE_TOOL_EXEC,
            events.AFTER_TOOL_EXEC,
            events.ON_TERMINATION,
        ]

    def can_handle(self, event) -> bool:
        """Whether this hook handles the given event."""
        return event in self.events

    def _emit(self, message: str) -> None:
        """Print a progress line to console and mirror it to the logger at DEBUG."""
        self.console.print(message)
        if self.logger is not None:
            self.logger.debug(Text.from_markup(message).plain.strip())

    async def handle(self, ctx):
        """Handle hook event and output progress."""
        event = ctx.event
        data = ctx.data

        events = self._get_events()

        if event == events.BEFORE_LOOP:
            self._iteration = data.get("iteration", 0)
            if self._iteration == 0:
                self._emit("[bold cyan]▶ Agent started[/]")

        elif event == events.BEFORE_LLM_CALL:
            iteration = data.get("iteration", self._iteration)
            self._emit(f"  [dim]⟳ LLM call (iteration {iteration + 1})[/]")

        elif event == events.AFTER_LLM_CALL:
            response = data.get("response")
            if response and hasattr(response, 'usage'):
                usage = response.usage
                if usage:
                    tokens = usage.get('total_tokens', 0)
                    self._emit(f"  [dim]↓ received response (tokens: {tokens})[/]")

        elif event == events.BEFORE_TOOL_EXEC:
            tool_name = data.get("tool_name", "unknown")
            tool_input = data.get("tool_input", {})
            self._tool_calls += 1

            if tool_name == "task":
                goal = tool_input.get("goal", "unknown")[:50]
                self._sub_agent_count += 1
                self._emit(f"  [bold yellow]◇ Starting sub Agent #{self._sub_agent_count}[/]: {goal}...")
            else:
                if self.verbose:
                    if tool_name == "bash":
                        cmd = tool_input.get("command", "")[:60]
                        self._emit(f"  [green]⚡ {tool_name}[/]: {cmd}")
                    elif tool_name == "glob":
                        pattern = tool_input.get("pattern", "")
                        self._emit(f"  [green]⚡ {tool_name}[/]: {pattern}")
                    elif tool_name == "grep":
                        pattern = tool_input.get("pattern", "")[:40]
                        path = tool_input.get("path", "")[:30]
                        self._emit(f"  [green]⚡ {tool_name}[/]: '{pattern}' in {path}")
                    elif tool_name == "file_ops":
                        op = tool_input.get("operation", "")
                        path = tool_input.get("path", "")[:50]
                        self._emit(f"  [green]⚡ {tool_name}[/]: {op} {path}")
                    else:
                        self._emit(f"  [green]⚡ {tool_name}[/]")

        elif event == events.AFTER_TOOL_EXEC:
            tool_name = data.get("tool_name", "unknown")
            is_error = ctx.is_error

            if tool_name == "task":
                if is_error:
                    self.console.print("  [red]✗ Sub Agent failed[/]")
                    if self.logger is not None:
                        self.logger.error("Sub Agent failed")
                else:
                    self._emit("  [green]✓ Sub Agent completed[/]")

        elif event == events.ON_TERMINATION:
            reason = data.get("reason", "unknown")
            self._emit(f"[bold]⏹ Agent terminated[/]: {reason}")
            self._emit(f"  [dim]Statistics: {self._tool_calls} tool calls, {self._sub_agent_count} sub Agents[/]")

        return ctx
