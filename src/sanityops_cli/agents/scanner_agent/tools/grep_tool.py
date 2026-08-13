"""
GrepTool - A powerful search tool built on ripgrep.

Adapted for the deeplogic-cli agent framework.
"""

import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from sanityops_agent.tools.base import Tool, ToolResult


class OutputMode(Enum):
    """Output mode for grep results."""
    CONTENT = "content"
    FILES_WITH_MATCHES = "files_with_matches"
    COUNT = "count"


# Version control system directories to exclude from searches
VCS_DIRECTORIES_TO_EXCLUDE = [
    '.git',
    '.svn',
    '.hg',
    '.bzr',
    '.jj',
    '.sl',
]

# Default cap on grep results when head_limit is unspecified
DEFAULT_HEAD_LIMIT = 250


@dataclass
class GrepOutput:
    """Output schema for GrepTool."""
    mode: OutputMode
    num_files: int
    filenames: list[str] = field(default_factory=list)
    content: str | None = None
    num_lines: int | None = None
    num_matches: int | None = None
    applied_limit: int | None = None
    applied_offset: int | None = None


def get_cwd() -> str:
    """Get current working directory."""
    return os.getcwd()


def expand_path(path: str, base_dir: str | None = None) -> str:
    """
    Expand a path that may contain tilde notation (~) to an absolute path.

    Args:
        path: The path to expand
        base_dir: Base directory for relative paths (defaults to cwd)

    Returns:
        The expanded absolute path
    """
    actual_base_dir = base_dir or get_cwd()

    # Handle empty path
    if not path or not path.strip():
        return os.path.normpath(actual_base_dir)

    # expanduser automatically handles '~' and '~/...'
    expanded = os.path.expanduser(path.strip())

    # Handle absolute paths
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)

    # Handle relative paths
    return str(Path(actual_base_dir) / expanded)


def to_relative_path(absolute_path: str) -> str:
    """
    Convert an absolute path to a relative path from cwd.

    If the path is outside cwd (relative path would start with ..),
    returns the absolute path unchanged.
    """
    try:
        relative_path = os.path.relpath(absolute_path, get_cwd())
        if relative_path.startswith('..'):
            return absolute_path
        return relative_path
    except ValueError:
        # On Windows, different drives can't be relativized
        return absolute_path


def apply_head_limit(
    items: list,
    limit: int | None,
    offset: int = 0
) -> tuple[list, int | None]:
    """
    Apply head_limit and offset to a list of items.

    Args:
        items: List of items to limit
        limit: Maximum number of items (0 = unlimited)
        offset: Number of items to skip from the start

    Returns:
        Tuple of (limited items, applied_limit if truncation occurred)
    """
    if limit == 0:
        return items[offset:], None

    effective_limit = limit or DEFAULT_HEAD_LIMIT
    sliced = items[offset:offset + effective_limit]
    was_truncated = len(items) - offset > effective_limit

    return sliced, effective_limit if was_truncated else None


def format_limit_info(
    applied_limit: int | None,
    applied_offset: int | None
) -> str:
    """Format limit/offset information for display in tool results."""
    parts = []
    if applied_limit is not None:
        parts.append(f"limit: {applied_limit}")
    if applied_offset:
        parts.append(f"offset: {applied_offset}")
    return ", ".join(parts)


def find_ripgrep() -> str:
    """Find the ripgrep executable."""
    # Try to find rg in PATH
    rg_path = shutil.which('rg')
    if rg_path:
        return rg_path

    # Fallback to common locations
    common_paths = [
        '/usr/local/bin/rg',
        '/usr/bin/rg',
        os.path.expanduser('~/.local/bin/rg'),
    ]

    for path in common_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path

    raise FileNotFoundError(
        "ripgrep (rg) not found. Please install ripgrep: "
        "https://github.com/BurntSushi/ripgrep#installation"
    )


def run_ripgrep(
    args: list[str],
    target: str,
    timeout: int = 20
) -> list[str]:
    """
    Run ripgrep with the given arguments.

    Args:
        args: Arguments to pass to ripgrep
        target: Target path to search
        timeout: Timeout in seconds (default 20)

    Returns:
        List of output lines from ripgrep

    Raises:
        FileNotFoundError: If ripgrep is not found
        subprocess.TimeoutExpired: If ripgrep times out
        subprocess.CalledProcessError: If ripgrep fails
    """
    rg_path = find_ripgrep()

    full_args = [rg_path] + args + [target]

    result = subprocess.run(
        full_args,
        capture_output=True,
        text=True,
        timeout=timeout
    )

    # Exit code 0 = matches found, 1 = no matches (both are success)
    # Exit code 2 = errors occurred (e.g., permission denied), but may have partial results
    if result.returncode not in (0, 1):
        # If we have stdout content despite returncode 2, treat as partial success
        # This handles cases where some files had permission errors but results were found
        if result.returncode == 2 and result.stdout.strip():
            pass  # Continue with partial results
        else:
            raise subprocess.CalledProcessError(
                result.returncode,
                full_args,
                result.stdout,
                result.stderr
            )

    # Split output into lines, filtering empty lines
    lines = [
        line.rstrip('\r')
        for line in result.stdout.strip().split('\n')
        if line
    ]

    return lines


def execute_grep(
    pattern: str,
    path: str | None = None,
    glob: str | None = None,
    output_mode: str | OutputMode = OutputMode.FILES_WITH_MATCHES,
    context_before: int | None = None,
    context_after: int | None = None,
    context: int | None = None,
    show_line_numbers: bool = True,
    case_insensitive: bool = False,
    type: str | None = None,
    head_limit: int | None = None,
    offset: int = 0,
    multiline: bool = False,
) -> GrepOutput:
    """
    Execute a grep search using ripgrep.

    Args:
        pattern: The regular expression pattern to search for
        path: File or directory to search in (defaults to cwd)
        glob: Glob pattern to filter files (e.g., "*.js", "*.{ts,tsx}")
        output_mode: Output mode - "content", "files_with_matches", or "count"
        context_before: Number of lines to show before each match (-B)
        context_after: Number of lines to show after each match (-A)
        context: Number of lines to show before and after each match (-C)
        show_line_numbers: Show line numbers in output (-n)
        case_insensitive: Case insensitive search (-i)
        type: File type to search (e.g., "js", "py", "rust")
        head_limit: Limit output to first N lines/entries
        offset: Skip first N lines/entries before applying head_limit
        multiline: Enable multiline mode where . matches newlines

    Returns:
        GrepOutput containing the search results
    """
    # Convert string output_mode to enum
    if isinstance(output_mode, str):
        output_mode = OutputMode(output_mode)

    # Resolve the target path
    absolute_path = expand_path(path) if path else get_cwd()

    # Build ripgrep arguments
    args = ['--hidden', '-H']  # -H: always show filename (fixes single-file search)

    # Exclude VCS directories
    for dir_name in VCS_DIRECTORIES_TO_EXCLUDE:
        args.extend(['--glob', f'!{dir_name}'])

    # Limit line length
    args.extend(['--max-columns', '500'])

    # Multiline mode
    if multiline:
        args.extend(['-U', '--multiline-dotall'])

    # Case insensitive
    if case_insensitive:
        args.append('-i')

    # Output mode
    if output_mode == OutputMode.FILES_WITH_MATCHES:
        args.append('-l')
    elif output_mode == OutputMode.COUNT:
        args.append('-c')

    # Line numbers (only for content mode)
    if show_line_numbers and output_mode == OutputMode.CONTENT:
        args.append('-n')

    # Context flags
    if output_mode == OutputMode.CONTENT:
        if context is not None:
            args.extend(['-C', str(context)])
        elif context_before is not None or context_after is not None:
            if context_before is not None:
                args.extend(['-B', str(context_before)])
            if context_after is not None:
                args.extend(['-A', str(context_after)])

    # Pattern (use -e if pattern starts with dash)
    if pattern.startswith('-'):
        args.extend(['-e', pattern])
    else:
        args.append(pattern)

    # Type filter
    if type:
        args.extend(['--type', type])

    # Glob patterns - pass each space-separated pattern directly to ripgrep
    # ripgrep natively supports comma-separated patterns and brace expansion
    if glob:
        for pattern_item in glob.split():
            if pattern_item:
                args.extend(['--glob', pattern_item])

    # Execute ripgrep
    results = run_ripgrep(args, absolute_path)

    # Process results based on output mode
    if output_mode == OutputMode.CONTENT:
        limited_results, applied_limit = apply_head_limit(
            results,
            head_limit,
            offset
        )

        # Convert absolute paths to relative paths
        # Handle Windows drive letters (e.g., C:\path) where colon appears at index 1
        final_lines = []
        for line in limited_results:
            colon_index = line.find(':')
            # Check for Windows drive letter pattern (e.g., "C:\" or "C:/")
            if colon_index == 1 and len(line) > 2 and line[0].isalpha() and line[2] in ('\\', '/'):
                colon_index = line.find(':', colon_index + 1)

            if colon_index > 0:
                file_path = line[:colon_index]
                rest = line[colon_index:]
                final_lines.append(to_relative_path(file_path) + rest)
            else:
                final_lines.append(line)

        return GrepOutput(
            mode=OutputMode.CONTENT,
            num_files=0,
            content='\n'.join(final_lines),
            num_lines=len(final_lines),
            applied_limit=applied_limit,
            applied_offset=offset if offset > 0 else None
        )

    if output_mode == OutputMode.COUNT:
        limited_results, applied_limit = apply_head_limit(
            results,
            head_limit,
            offset
        )

        # Convert absolute paths to relative paths
        final_count_lines = []
        total_matches = 0
        file_count = 0

        for line in limited_results:
            colon_index = line.rfind(':')
            if colon_index > 0:
                file_path = line[:colon_index]
                count_str = line[colon_index + 1:]
                final_count_lines.append(to_relative_path(file_path) + ':' + count_str)

                count = int(count_str) if count_str.isdigit() else 0
                total_matches += count
                if count > 0:
                    file_count += 1
            else:
                final_count_lines.append(line)

        return GrepOutput(
            mode=OutputMode.COUNT,
            num_files=file_count,
            content='\n'.join(final_count_lines),
            num_matches=total_matches,
            applied_limit=applied_limit,
            applied_offset=offset if offset > 0 else None
        )

    # files_with_matches mode (default)
    # Apply head_limit to sorted file list
    final_matches, applied_limit = apply_head_limit(
        results,
        head_limit,
        offset
    )

    # Convert absolute paths to relative paths
    relative_matches = [to_relative_path(p) for p in final_matches]

    return GrepOutput(
        mode=OutputMode.FILES_WITH_MATCHES,
        filenames=relative_matches,
        num_files=len(relative_matches),
        applied_limit=applied_limit,
        applied_offset=offset if offset > 0 else None
    )


def format_result(output: GrepOutput) -> str:
    """
    Format the grep output for display.

    Args:
        output: The grep output to format

    Returns:
        Formatted string representation of the results
    """
    if output.mode == OutputMode.CONTENT:
        content = output.content or 'No matches found'
        limit_info = format_limit_info(output.applied_limit, output.applied_offset)
        if limit_info:
            return f"{content}\n\n[Showing results with pagination = {limit_info}]"
        return content

    if output.mode == OutputMode.COUNT:
        content = output.content or 'No matches found'
        matches = output.num_matches or 0
        files = output.num_files or 0
        limit_info = format_limit_info(output.applied_limit, output.applied_offset)

        matches_str = 'occurrence' if matches == 1 else 'occurrences'
        files_str = 'file' if files == 1 else 'files'

        summary = f"\n\nFound {matches} total {matches_str} across {files} {files_str}."
        if limit_info:
            summary += f" with pagination = {limit_info}"

        return content + summary

    # files_with_matches mode
    if output.num_files == 0:
        return 'No files found'

    files_str = 'file' if output.num_files == 1 else 'files'
    limit_info = format_limit_info(output.applied_limit, output.applied_offset)

    result = f"Found {output.num_files} {files_str}"
    if limit_info:
        result += f" {limit_info}"

    return result + '\n' + '\n'.join(output.filenames)


class GrepTool(Tool):
    """
    A powerful search tool built on ripgrep.

    This tool provides regex-based file content searching with support for:
    - Full regex syntax
    - Glob pattern filtering
    - Multiple output modes (content, files_with_matches, count)
    - Context lines before/after matches
    - Case-insensitive search
    - Multiline matching
    """

    name = "grep"
    description = """A powerful search tool built on ripgrep

Usage:
- ALWAYS use grep for search tasks. NEVER invoke `grep` or `rg` as a shell command.
- Supports full regex syntax (e.g., "log.*Error", "function\\s+\\w+")
- Filter files with glob parameter (e.g., "*.js", "**/*.tsx") or type parameter (e.g., "js", "py", "rust")
- Output modes: "content" shows matching lines, "files_with_matches" shows file paths (default), "count" shows match counts
- Pattern syntax: Uses ripgrep (not grep) - literal braces need escaping (use `interface\\{\\}` to find `interface{}` in Go code)
- Multiline matching: By default patterns match within single lines only. For cross-line patterns, use multiline: true
"""
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "The regular expression pattern to search for"
            },
            "path": {
                "type": "string",
                "description": "File or directory to search in (defaults to cwd)"
            },
            "glob": {
                "type": "string",
                "description": "Glob pattern to filter files (e.g., '*.js', '*.{ts,tsx}')"
            },
            "output_mode": {
                "type": "string",
                "enum": ["content", "files_with_matches", "count"],
                "default": "files_with_matches",
                "description": "Output mode - 'content' shows matching lines, 'files_with_matches' shows file paths, 'count' shows match counts"
            },
            "context_before": {
                "type": "integer",
                "description": "Number of lines to show before each match (-B)"
            },
            "context_after": {
                "type": "integer",
                "description": "Number of lines to show after each match (-A)"
            },
            "context": {
                "type": "integer",
                "description": "Number of lines to show before and after each match (-C)"
            },
            "show_line_numbers": {
                "type": "boolean",
                "default": True,
                "description": "Show line numbers in output"
            },
            "case_insensitive": {
                "type": "boolean",
                "default": False,
                "description": "Case insensitive search"
            },
            "type": {
                "type": "string",
                "description": "File type to search (e.g., 'js', 'py', 'rust')"
            },
            "head_limit": {
                "type": "integer",
                "description": "Limit output to first N lines/entries"
            },
            "offset": {
                "type": "integer",
                "default": 0,
                "description": "Skip first N lines/entries before applying head_limit"
            },
            "multiline": {
                "type": "boolean",
                "default": False,
                "description": "Enable multiline mode where . matches newlines"
            }
        },
        "required": ["pattern"]
    }
    tags = ["scanner", "search"]

    async def execute(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        output_mode: str = "files_with_matches",
        context_before: int | None = None,
        context_after: int | None = None,
        context: int | None = None,
        show_line_numbers: bool = True,
        case_insensitive: bool = False,
        type: str | None = None,
        head_limit: int | None = None,
        offset: int = 0,
        multiline: bool = False,
        **kwargs
    ) -> ToolResult:
        """
        Search for a pattern in files using ripgrep.

        Args:
            pattern: The regular expression pattern to search for
            path: File or directory to search in (defaults to cwd)
            glob: Glob pattern to filter files (e.g., "*.js", "*.{ts,tsx}")
            output_mode: Output mode - "content", "files_with_matches", or "count"
            context_before: Number of lines to show before each match (-B)
            context_after: Number of lines to show after each match (-A)
            context: Number of lines to show before and after each match (-C)
            show_line_numbers: Show line numbers in output (-n)
            case_insensitive: Case insensitive search (-i)
            type: File type to search (e.g., "js", "py", "rust")
            head_limit: Limit output to first N lines/entries
            offset: Skip first N lines/entries before applying head_limit
            multiline: Enable multiline mode where . matches newlines

        Returns:
            ToolResult containing the search results
        """
        try:
            # Use asyncio.to_thread to avoid blocking the event loop
            # since execute_grep uses subprocess.run which is synchronous
            output = await asyncio.to_thread(
                execute_grep,
                pattern=pattern,
                path=path,
                glob=glob,
                output_mode=output_mode,
                context_before=context_before,
                context_after=context_after,
                context=context,
                show_line_numbers=show_line_numbers,
                case_insensitive=case_insensitive,
                type=type,
                head_limit=head_limit,
                offset=offset,
                multiline=multiline,
            )

            content = format_result(output)

            return ToolResult(
                content=content,
                success=True,
                metadata={
                    "mode": output.mode.value,
                    "num_files": output.num_files,
                    "num_lines": output.num_lines,
                    "num_matches": output.num_matches,
                    "applied_limit": output.applied_limit,
                }
            )

        except FileNotFoundError as e:
            return ToolResult(
                content=f"Error: {e}",
                success=False,
                error=str(e)
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                content="Error: grep search timed out",
                success=False,
                error="Timeout"
            )
        except subprocess.CalledProcessError as e:
            return ToolResult(
                content=f"Error: grep failed with code {e.returncode}",
                success=False,
                error=str(e.stderr) if e.stderr else str(e)
            )
        except Exception as e:
            return ToolResult(
                content=f"Error: {e}",
                success=False,
                error=str(e)
            )


# Export public API
__all__ = [
    'GrepTool',
    'GrepOutput',
    'OutputMode',
    'execute_grep',
    'format_result',
]
