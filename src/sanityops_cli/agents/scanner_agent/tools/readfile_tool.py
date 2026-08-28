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


"""
FileReadTool - A comprehensive file reading tool.

Adapted for the deeplogic-cli agent framework.

This module provides functionality to read various file types including:
- Text files (with line numbers and offset/limit support)
- Image files (PNG, JPG, JPEG, GIF, WEBP) with base64 encoding
- PDF files (with optional page range extraction)
- Jupyter notebooks (.ipynb)
"""

import base64
import json
import os
from pathlib import Path

from sanityops_agent.tools.base import Tool, ToolResult

# =============================================================================
# Constants
# =============================================================================

# Supported image extensions
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Binary file extensions that cannot be read as text
BINARY_EXTENSIONS = {
    'exe', 'dll', 'so', 'dylib', 'bin', 'dat',
    'pyc', 'pyo', 'pyd', 'class', 'jar', 'war',
    'zip', 'tar', 'gz', 'bz2', 'xz', '7z', 'rar',
    'mp3', 'mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv',
    'wav', 'flac', 'aac', 'ogg',
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'sqlite', 'db', 'mdb',
}

# Device files that would hang the process
BLOCKED_DEVICE_PATHS = {
    '/dev/zero',
    '/dev/random',
    '/dev/urandom',
    '/dev/full',
    '/dev/stdin',
    '/dev/tty',
    '/dev/console',
    '/dev/stdout',
    '/dev/stderr',
    '/dev/fd/0',
    '/dev/fd/1',
    '/dev/fd/2',
}

# Default limits
DEFAULT_MAX_SIZE_BYTES = 2 * 1024 * 1024  # 2MB
DEFAULT_MAX_TOKENS = 20000


# =============================================================================
# Helper Functions
# =============================================================================

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

    path = path.strip()

    # Handle home directory notation
    if path == '~':
        return os.path.expanduser('~')
    if path.startswith('~/'):
        return os.path.normpath(os.path.join(os.path.expanduser('~'), path[2:]))

    # Handle absolute paths
    if os.path.isabs(path):
        return os.path.normpath(path)

    # Handle relative paths
    return os.path.normpath(os.path.abspath(os.path.join(actual_base_dir, path)))


def get_file_extension(file_path: str) -> str:
    """Get the file extension without the leading dot."""
    return Path(file_path).suffix.lstrip('.').lower()


def is_image_file(file_path: str) -> bool:
    """Check if file is an image based on extension."""
    ext = get_file_extension(file_path)
    return ext in IMAGE_EXTENSIONS


def is_binary_file(file_path: str) -> bool:
    """Check if file is a binary file based on extension."""
    ext = get_file_extension(file_path)
    return ext in BINARY_EXTENSIONS


def is_blocked_device(file_path: str) -> bool:
    """Check if path is a blocked device file."""
    return file_path in BLOCKED_DEVICE_PATHS


def is_notebook_file(file_path: str) -> bool:
    """Check if file is a Jupyter notebook."""
    return get_file_extension(file_path) == 'ipynb'


def is_pdf_file(file_path: str) -> bool:
    """Check if file is a PDF."""
    return get_file_extension(file_path) == 'pdf'


def add_line_numbers(content: str, start_line: int = 1) -> str:
    """
    Add line numbers to content.

    Args:
        content: The text content
        start_line: Starting line number (1-indexed)

    Returns:
        Content with line numbers prefixed
    """
    lines = content.split('\n')
    max_line_num = start_line + len(lines) - 1
    width = len(str(max_line_num))

    numbered_lines = []
    for i, line in enumerate(lines):
        line_num = start_line + i
        numbered_lines.append(f"{line_num:{width}d}\t{line}")

    return '\n'.join(numbered_lines)


def detect_image_format(data: bytes) -> tuple[str, str]:
    """
    Detect image format from binary data.

    Args:
        data: Binary image data

    Returns:
        Tuple of (format_name, mime_type)

    Raises:
        ValueError: If format cannot be detected
    """
    # PNG
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png', 'image/png'

    # JPEG
    if data[:2] == b'\xff\xd8':
        return 'jpeg', 'image/jpeg'

    # GIF
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return 'gif', 'image/gif'

    # WebP
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp', 'image/webp'

    # Default to PNG
    return 'png', 'image/png'


def parse_pdf_page_range(pages: str) -> tuple[int, int] | None:
    """
    Parse a PDF page range string.

    Args:
        pages: Page range string (e.g., "1-5", "3", "10-20")

    Returns:
        Tuple of (start_page, end_page) or None if invalid
    """
    import re

    # Single page
    if re.match(r'^\d+$', pages):
        page = int(pages)
        if page >= 1:
            return (page, page)

    # Page range
    match = re.match(r'^(\d+)-(\d+)$', pages)
    if match:
        start = int(match.group(1))
        end = int(match.group(2))
        if start >= 1 and end >= start:
            return (start, end)

    return None


def rough_token_estimate(content: str) -> int:
    """
    Estimate token count for content.

    Uses a simple heuristic: ~4 characters per token for most text.
    """
    return len(content) // 4


def find_similar_file(file_path: str) -> str | None:
    """
    Find a similar file if the given file doesn't exist.

    Args:
        file_path: Path to check

    Returns:
        Path to similar file or None
    """
    path = Path(file_path)

    if not path.parent.exists():
        return None

    # Get filename without extension
    stem = path.stem.lower()
    suffix = path.suffix.lower()

    # Search for similar files in the same directory
    for f in path.parent.iterdir():
        if f.is_file():
            f_stem = f.stem.lower()
            f_suffix = f.suffix.lower()

            # Check if filename is similar (typo or case difference)
            if f_stem == stem or f_suffix == suffix:
                return str(f)

            # Check for common typo patterns
            if stem in f_stem or f_stem in stem:
                return str(f)

    return None


# =============================================================================
# Read Functions
# =============================================================================

def read_text_file(
    file_path: str,
    offset: int = 1,
    limit: int | None = None,
    max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
    add_line_nums: bool = True
) -> tuple[str, dict]:
    """
    Read a text file with optional offset and limit.

    Args:
        file_path: Path to the file
        offset: Starting line number (1-indexed)
        limit: Maximum number of lines to read
        max_size_bytes: Maximum file size in bytes
        add_line_nums: Whether to add line numbers

    Returns:
        Tuple of (content, metadata)

    Raises:
        FileNotFoundError: If file doesn't exist
        FileTooLargeError: If file exceeds size limit
        BinaryFileError: If file appears to be binary
    """
    path = Path(file_path)

    if not path.exists():
        similar = find_similar_file(file_path)
        if similar:
            raise FileNotFoundError(
                f"File does not exist: {file_path}. Did you mean {similar}?"
            )
        raise FileNotFoundError(f"File does not exist: {file_path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    # Check file size
    file_size = path.stat().st_size
    if file_size > max_size_bytes:
        raise ValueError(
            f"File size ({file_size} bytes) exceeds maximum allowed size "
            f"({max_size_bytes} bytes). Use offset and limit to read specific portions."
        )

    # Try to read as text
    try:
        with open(path, encoding='utf-8') as f:
            all_lines = f.readlines()
    except UnicodeDecodeError:
        # Try other common encodings
        encodings = ['latin-1', 'cp1252', 'iso-8859-1']
        for enc in encodings:
            try:
                with open(path, encoding=enc) as f:
                    all_lines = f.readlines()
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError(
                f"Cannot read file as text. The file appears to be binary: {file_path}"
            )

    total_lines = len(all_lines)

    # Convert 1-indexed offset to 0-indexed
    start_idx = max(0, offset - 1)

    # Apply limit
    if limit is not None:
        end_idx = min(start_idx + limit, total_lines)
    else:
        end_idx = total_lines

    # Extract requested lines
    selected_lines = all_lines[start_idx:end_idx]
    content = ''.join(selected_lines)

    # Add line numbers if requested
    if add_line_nums and content:
        content = add_line_numbers(content.rstrip('\n'), offset)

    metadata = {
        "file_path": file_path,
        "num_lines": len(selected_lines),
        "start_line": offset,
        "total_lines": total_lines,
        "file_size": file_size,
    }

    return content, metadata


def read_image_file(
    file_path: str,
    max_size_bytes: int | None = None
) -> tuple[str, dict]:
    """
    Read an image file and encode as base64.

    Args:
        file_path: Path to the image file
        max_size_bytes: Maximum file size (optional)

    Returns:
        Tuple of (content, metadata)
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Image file does not exist: {file_path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    file_size = path.stat().st_size

    if max_size_bytes and file_size > max_size_bytes:
        raise ValueError(
            f"Image file size ({file_size} bytes) exceeds maximum allowed size "
            f"({max_size_bytes} bytes)."
        )

    # Read and encode image
    with open(path, 'rb') as f:
        data = f.read()

    if len(data) == 0:
        raise ValueError(f"Image file is empty: {file_path}")

    # Detect format
    format_name, mime_type = detect_image_format(data)

    # Try to get dimensions using PIL if available
    width, height = None, None
    try:
        import io

        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
    except ImportError:
        pass  # PIL not available, skip dimensions
    except Exception:
        pass  # Could not read image dimensions

    base64_data = base64.b64encode(data).decode('ascii')

    # For images, return a description string as content
    dims = f" ({width}x{height})" if width and height else ""
    content = f"Image file read: {file_path}{dims} ({file_size} bytes, {mime_type})"

    metadata = {
        "file_path": file_path,
        "base64": base64_data,
        "media_type": mime_type,
        "original_size": file_size,
        "width": width,
        "height": height,
    }

    return content, metadata


def read_notebook_file(file_path: str) -> tuple[str, dict]:
    """
    Read a Jupyter notebook file.

    Args:
        file_path: Path to the notebook file

    Returns:
        Tuple of (content, metadata)
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Notebook file does not exist: {file_path}")

    try:
        with open(path, encoding='utf-8') as f:
            notebook = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid notebook format: {e}") from e

    # Extract cells
    cells = []
    for cell_data in notebook.get('cells', []):
        cell_type = cell_data.get('cell_type', 'code')

        # Handle source which can be string or list
        source = cell_data.get('source', '')
        if isinstance(source, list):
            source = ''.join(source)

        cells.append({
            "cell_type": cell_type,
            "source": source,
            "outputs": cell_data.get('outputs'),
            "execution_count": cell_data.get('execution_count'),
        })

    # Get notebook language
    language = None
    if 'metadata' in notebook:
        kernelspec = notebook['metadata'].get('kernelspec', {})
        language = kernelspec.get('language')

    # Format content as readable text
    content_lines = []
    for i, cell in enumerate(cells, 1):
        cell_type = cell['cell_type']
        source = cell['source']
        content_lines.append(f"### Cell {i} ({cell_type})")
        if source:
            content_lines.append(source)
        content_lines.append("")

    content = '\n'.join(content_lines)

    metadata = {
        "file_path": file_path,
        "cell_count": len(cells),
        "language": language,
    }

    return content, metadata


def read_pdf_file(
    file_path: str,
    pages: str | None = None,
    max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES
) -> tuple[str, dict]:
    """
    Read a PDF file.

    Args:
        file_path: Path to the PDF file
        pages: Optional page range (e.g., "1-5")
        max_size_bytes: Maximum file size in bytes

    Returns:
        Tuple of (content, metadata)
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file does not exist: {file_path}")

    file_size = path.stat().st_size

    if file_size > max_size_bytes:
        raise ValueError(
            f"PDF file size ({file_size} bytes) exceeds maximum allowed size "
            f"({max_size_bytes} bytes)."
        )

    # Read and encode PDF
    with open(path, 'rb') as f:
        data = f.read()

    base64_data = base64.b64encode(data).decode('ascii')

    # Try to get page count
    page_count = None
    try:
        import pypdf
        reader = pypdf.PdfReader(path)
        page_count = len(reader.pages)
    except ImportError:
        pass  # pypdf not available
    except Exception:
        pass

    pages_info = f", {page_count} pages" if page_count else ""
    content = f"PDF file read: {file_path} ({file_size} bytes{pages_info})"

    metadata = {
        "file_path": file_path,
        "base64": base64_data,
        "original_size": file_size,
        "page_count": page_count,
    }

    return content, metadata


# =============================================================================
# Main Tool Class
# =============================================================================

class FileReadTool(Tool):
    """
    A comprehensive file reading tool.

    This tool provides file reading functionality for various file types:
    - Text files (with line numbers, offset, and limit support)
    - Image files (PNG, JPG, JPEG, GIF, WEBP) with base64 encoding
    - PDF files (with optional page range)
    - Jupyter notebooks (.ipynb)
    """

    name = "read"
    description = """Reads a file from the local filesystem.

Usage:
- The file_path must be an absolute path (not a relative path)
- By default, it reads up to 2000 lines starting from line 1
- Use offset and limit to read specific portions of a large file
- For images (PNG, JPG, GIF, WEBP), the image content is encoded as base64
- For PDFs, use the pages parameter to read specific page ranges (e.g., pages: "1-5")
- For Jupyter notebooks (.ipynb), returns the notebook cells with their outputs

This tool is read-only and does not modify the filesystem.
"""
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to read"
            },
            "offset": {
                "type": "integer",
                "description": "The line number to start reading from (1-indexed)",
                "default": 1
            },
            "limit": {
                "type": "integer",
                "description": "The number of lines to read"
            },
            "pages": {
                "type": "string",
                "description": "Page range for PDF files (e.g., '1-5', '3', '10-20')"
            }
        },
        "required": ["file_path"]
    }
    tags = ["scanner", "reader"]

    def __init__(
        self,
        max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
        max_tokens: int = DEFAULT_MAX_TOKENS
    ):
        """
        Initialize the FileReadTool.

        Args:
            max_size_bytes: Maximum file size in bytes
            max_tokens: Maximum estimated tokens for text content
        """
        from sanityops_agent.tools.context import ToolContext
        super().__init__(context=ToolContext())
        self.max_size_bytes = max_size_bytes
        self.max_tokens = max_tokens

    def _validate_input(self, file_path: str) -> None:
        """
        Validate input before reading.

        Args:
            file_path: Path to validate

        Raises:
            ValueError: If path is a blocked device or binary file
        """
        # Check for blocked device paths
        if is_blocked_device(file_path):
            raise ValueError(
                f"Cannot read '{file_path}': this device file would block or produce infinite output."
            )

        # Check for binary files
        ext = get_file_extension(file_path)
        if is_binary_file(file_path) and not is_image_file(file_path) and ext != 'pdf':
            raise ValueError(
                f"This tool cannot read binary files. "
                f"The file appears to be a binary .{ext} file."
            )

    async def execute(
        self,
        file_path: str,
        offset: int | None = 1,
        limit: int | None = None,
        pages: str | None = None,
        **kwargs
    ) -> ToolResult:
        """
        Read a file.

        Args:
            file_path: Absolute path to the file to read
            offset: The line number to start reading from (1-indexed)
            limit: The number of lines to read
            pages: Page range for PDF files (e.g., "1-5", "3", "10-20")

        Returns:
            ToolResult containing the file content
        """
        try:
            # Expand and normalize path
            full_path = expand_path(file_path)

            # Validate input
            self._validate_input(full_path)

            # Determine file type and read accordingly
            if is_notebook_file(full_path):
                content, metadata = read_notebook_file(full_path)
                return ToolResult(
                    content=content,
                    success=True,
                    metadata={"file_type": "notebook", **metadata}
                )

            if is_image_file(full_path):
                content, metadata = read_image_file(full_path, self.max_size_bytes)
                return ToolResult(
                    content=content,
                    success=True,
                    metadata={"file_type": "image", **metadata}
                )

            if is_pdf_file(full_path):
                content, metadata = read_pdf_file(full_path, pages, self.max_size_bytes)
                return ToolResult(
                    content=content,
                    success=True,
                    metadata={"file_type": "pdf", **metadata}
                )

            # Default: read as text file
            content, metadata = read_text_file(full_path, offset or 1, limit, self.max_size_bytes)

            # Check token limit for text content
            if content:
                token_estimate = rough_token_estimate(content)
                if token_estimate > self.max_tokens:
                    return ToolResult(
                        content=f"File content ({token_estimate} estimated tokens) exceeds maximum allowed tokens ({self.max_tokens}). Use offset and limit parameters to read specific portions of the file.",
                        success=False,
                        error="Token limit exceeded"
                    )

            # Handle empty file
            if not content:
                if metadata.get("total_lines", 0) == 0:
                    content = "<system-reminder>Warning: the file exists but the contents are empty.</system-reminder>"
                else:
                    content = f"<system-reminder>Warning: the file exists but is shorter than the provided offset ({metadata.get('start_line')}). The file has {metadata.get('total_lines')} lines.</system-reminder>"

            return ToolResult(
                content=content,
                success=True,
                metadata={"file_type": "text", **metadata}
            )

        except FileNotFoundError as e:
            return ToolResult(
                content=f"Error: {e}",
                success=False,
                error=str(e)
            )
        except ValueError as e:
            return ToolResult(
                content=f"Error: {e}",
                success=False,
                error=str(e)
            )
        except Exception as e:
            return ToolResult(
                content=f"Error reading file: {e}",
                success=False,
                error=str(e)
            )


# =============================================================================
# Convenience Functions
# =============================================================================

def read_file(
    file_path: str,
    offset: int | None = 1,
    limit: int | None = None,
    pages: str | None = None
) -> tuple[str, dict]:
    """
    Quick file read function.

    Args:
        file_path: Absolute path to the file to read
        offset: The line number to start reading from (1-indexed)
        limit: The number of lines to read
        pages: Page range for PDF files

    Returns:
        Tuple of (content, metadata)
    """
    tool = FileReadTool()
    result = tool.read(file_path=file_path, offset=offset, limit=limit, pages=pages)
    return result.content, result.metadata


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'FileReadTool',
    'read_file',
    'expand_path',
    'add_line_numbers',
    'IMAGE_EXTENSIONS',
    'BINARY_EXTENSIONS',
    'DEFAULT_MAX_SIZE_BYTES',
    'DEFAULT_MAX_TOKENS',
]
