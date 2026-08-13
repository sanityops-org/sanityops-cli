from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

# ============================================================================
# Inspect Command Renderer
# ============================================================================

def render_inspect_terminal(catalog: dict[str, Any]) -> None:
    """inspect resulte renderer for terminal"""
    directory = catalog.get("directory", "-")
    skills = catalog.get("skills", [])
    tools = catalog.get("tools", [])
    prompts = catalog.get("prompts", [])
    meta = catalog.get("meta", {})
    elapsed = meta.get("time_elapsed", 0)
    loops = meta.get("loops_used", 0)

    console.print()
    header_text = Text()
    header_text.append("📋 Inspect Report\n\n", style="bold")
    header_text.append(f"Directory: {directory}", style="dim")
    console.print(Panel(header_text, border_style="blue"))
    console.print()

    # Skills
    console.print(f"[bold]🔧 Skills ({len(skills)})[/]")
    if skills:
        for s in skills:
            name = s.get("name", "-")
            path = s.get("path", "-")
            desc = s.get("description", "")
            console.print(f"  ├─ {name:<20} {path:<30} {desc[:40]}")
    else:
        console.print("  [dim]None[/]")
    console.print()

    # Tools
    console.print(f"[bold]⚙️ Tools ({len(tools)})[/]")
    if tools:
        for t in tools:
            name = t.get("name", "-")
            path = t.get("path", "-")
            t_type = t.get("type", "unknown")
            desc = t.get("description", "")
            console.print(f"  ├─ {name:<20} {path} ({t_type})    {desc[:30]}")
    else:
        console.print("  [dim]None[/]")
    console.print()

    # Prompts
    console.print(f"[bold]💬 Prompts ({len(prompts)})[/]")
    if prompts:
        for p in prompts:
            name = p.get("name", "-")
            path = p.get("path", "-")
            p_type = p.get("type", "file")
            desc = p.get("description", "")
            console.print(f"  ├─ {name:<20} {path} ({p_type})    {desc[:30]}")
    else:
        console.print("  [dim]None[/]")
    console.print()

    # Statistics
    console.print(
        f"[dim]Statistics: {len(skills)} skills, {len(tools)} tools, {len(prompts)} prompts"
        f"  |  Time elapsed: {elapsed:.1f}s  |  Loops: {loops}[/]"
    )
