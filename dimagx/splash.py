import time
import sys
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.table import Table
import pyfiglet
from colorama import init

init(autoreset=True)

def show_splash():
    console = Console()
    
    # 1. Clear terminal
    console.clear()
    
    # 2. Huge ASCII text "DIMAGX"
    # 'slant' is a very modern, italicized ASCII font
    fig = pyfiglet.Figlet(font='slant')
    ascii_art = fig.renderText('DIMAGX')
    
    # 3. Colorful gradient styling
    lines = ascii_art.splitlines()
    # Cyberpunk gradient: Cyan -> Purple -> Magenta
    gradient_colors = [
        "bright_cyan", 
        "cyan", 
        "deep_sky_blue1", 
        "dodger_blue1", 
        "medium_purple1", 
        "magenta"
    ]
    
    styled_ascii = Text()
    for i, line in enumerate(lines):
        color = gradient_colors[min(i, len(gradient_colors)-1)]
        styled_ascii.append(line + "\n", style=f"bold {color}")
    
    # 4. Show a subtitle: "⚡ AI Terminal Ready"
    subtitle = Text(" ⚡ AGENTIC MEMORY READY ", style="bold black on bright_cyan")
    
    # 5. Use Rich panels/box UI
    # We'll use a double border for that premium feel
    panel = Panel(
        styled_ascii,
        subtitle=subtitle,
        subtitle_align="center",
        border_style="cyan",
        padding=(1, 8),
        expand=False,
        title="[bold white]v0.1.0[/bold white]",
        title_align="right"
    )
    
    console.print("\n")
    console.print(panel, justify="center")
    console.print("\n")
    
    # 6. Add a loading spinner animation with status updates
    steps = [
        ("Waking up the brain...", "dots12", "cyan"),
        ("Loading memory graph...", "bouncingBar", "blue"),
        ("Orienting agent context...", "aesthetic", "magenta"),
        ("System Online.", "point", "green")
    ]
    
    for msg, spin, color in steps:
        with console.status(f"[bold {color}]{msg}[/bold {color}]", spinner=spin):
            time.sleep(0.6)
            
    console.print("[bold green]✔[/bold green] [bold white]DimagX is active.[/bold white] Type [bold cyan]dimagx --help[/bold cyan] to explore.\n")

if __name__ == "__main__":
    show_splash()
