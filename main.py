#!/usr/bin/env python3
import os
import subprocess
import json
import requests
from pathlib import Path
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.rule import Rule
from rich.text import Text
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

console = Console()

# === CONFIG ===
API_KEY  = os.getenv("OPENROUTER_API_KEY")
MODEL    = os.getenv("AI_MODEL", "anthropic/claude-3.5-sonnet")
SITE_URL = "https://github.com/local/ai-cli"
SITE_NAME = "ai-cli"

# === BLACKLIST ===
DANGEROUS_COMMANDS = ['rm -rf /', 'mkfs', 'dd if=', ':(){:|:&};:', 'chmod 777 /']

# === TOOLS ===
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Reads the contents of a file at the given path. Use this to inspect code, configs, logs, or any text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file, e.g. /home/user/project/main.py"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Writes or overwrites a file. WARNING: replaces existing content. Always read first if the file may already exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "New file content"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "Lists files and directories at the given path, like `ls`.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the directory"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal_command",
            "description": "Executes a shell command. Requires user confirmation for safety. Use for file operations, git, package managers, scripts, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Bash command to run"}
                },
                "required": ["command"]
            }
        }
    }
]

# === TOOL IMPLEMENTATIONS ===
def tool_read_file(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return {"success": True, "content": f.read()}
    except Exception as e:
        return {"success": False, "error": str(e)}

def tool_write_file(path, content):
    try:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "message": f"File {path} written successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def tool_list_directory(path):
    try:
        files = os.listdir(path)
        return {"success": True, "files": files}
    except Exception as e:
        return {"success": False, "error": str(e)}

def tool_run_command(command):
    for dangerous in DANGEROUS_COMMANDS:
        if dangerous in command:
            return {"success": False, "error": "Blocked: dangerous command"}
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
        return {
            "success": True,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

TOOLS_MAP = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "list_directory": tool_list_directory,
    "run_terminal_command": tool_run_command
}

LANG_MAP = {
    "py": "python", "js": "javascript", "ts": "typescript",
    "sh": "bash", "bash": "bash", "json": "json",
    "yaml": "yaml", "yml": "yaml", "md": "markdown",
    "toml": "toml", "html": "html", "css": "css",
    "rs": "rust", "go": "go", "c": "c", "cpp": "cpp",
    "java": "java", "rb": "ruby", "php": "php", "sql": "sql",
}

def detect_lang(path):
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else "text"
    return LANG_MAP.get(ext, "text")

# === API ===
def ask_ai(history):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_NAME,
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": history,
        "tools": TOOLS,
        "temperature": 0.2
    }
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    return response.json()

def print_token_usage(response):
    usage = response.get("usage", {})
    if usage:
        prompt_t = usage.get("prompt_tokens", "?")
        completion_t = usage.get("completion_tokens", "?")
        total_t = usage.get("total_tokens", "?")
        console.print(
            f"  [dim]tokens: {prompt_t} in / {completion_t} out / {total_t} total[/dim]"
        )

def print_header():
    model_short = MODEL.split("/")[-1]
    console.print()
    console.print(Rule(style="cyan"))
    title = Text()
    title.append("  AI CLI", style="bold cyan")
    title.append(f"  ·  {model_short}", style="dim cyan")
    title.append("  ·  type 'exit' to quit", style="dim")
    console.print(title)
    console.print(Rule(style="cyan"))
    console.print()

# === MAIN LOOP ===
def main():
    if not API_KEY:
        console.print(Panel(
            "[red]OPENROUTER_API_KEY not found.[/red]\n"
            "Create a [bold].env[/bold] file with [bold]OPENROUTER_API_KEY=your_key[/bold]",
            title="[red]Error[/red]",
            border_style="red"
        ))
        return

    print_header()

    system_content = """You are a powerful, universal AI assistant running in the terminal.
You have access to tools: read files, write files, list directories, and run shell commands.
Always use tools to take real action rather than describing what to do.
Before writing or modifying a file, read it first to understand its current state.
You help with anything: coding, debugging, writing, research, file management, data analysis, system tasks — whatever the user needs.
Be concise and precise. Prefer clean, working solutions over lengthy explanations."""

    history = [{"role": "system", "content": system_content}]
    first_turn = True

    while True:
        try:
            if not first_turn:
                console.print(Rule(style="dim"))
            first_turn = False

            user_input = Prompt.ask("\n[bold green]You[/bold green]")
            if user_input.strip().lower() in ["exit", "quit"]:
                break
            if not user_input.strip():
                continue

            history.append({"role": "user", "content": user_input})

            with console.status(f"[bold cyan]Thinking...[/bold cyan]", spinner="dots"):
                response = ask_ai(history)

            if 'choices' not in response or not response['choices']:
                err = response.get("error", {})
                console.print(Panel(
                    f"[red]{err.get('message', 'Unknown API error')}[/red]",
                    title="[red]API Error[/red]",
                    border_style="red"
                ))
                history.pop()
                continue

            message = response['choices'][0]['message']
            history.append(message)
            print_token_usage(response)

            # Tool calls
            if 'tool_calls' in message:
                for tool_call in message['tool_calls']:
                    func_name = tool_call['function']['name']
                    func_args = json.loads(tool_call['function']['arguments'])

                    console.print()
                    console.print(Panel(
                        f"[dim]{json.dumps(func_args, indent=2, ensure_ascii=False)}[/dim]",
                        title=f"[bold yellow]Tool: {func_name}[/bold yellow]",
                        border_style="yellow",
                        expand=False
                    ))

                    # Confirm dangerous ops
                    if func_name in ['write_file', 'run_terminal_command']:
                        if func_name == 'run_terminal_command':
                            console.print(Panel(
                                f"[bold]{func_args.get('command', '')}[/bold]",
                                title="[red]Command to execute[/red]",
                                border_style="red",
                                expand=False
                            ))
                        if not Confirm.ask("[bold red]Allow?[/bold red]"):
                            tool_result = {"error": "Cancelled by user"}
                        else:
                            tool_result = TOOLS_MAP[func_name](**func_args)
                    else:
                        tool_result = TOOLS_MAP[func_name](**func_args)

                    history.append({
                        "role": "tool",
                        "tool_call_id": tool_call['id'],
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    })

                    # Display result
                    if tool_result.get('success'):
                        if 'content' in tool_result:
                            lang = detect_lang(func_args.get('path', ''))
                            console.print(Panel(
                                Syntax(tool_result['content'], lang, theme="monokai", line_numbers=True),
                                title=f"[green]{func_args.get('path', 'file')}[/green]",
                                border_style="green"
                            ))
                        elif 'files' in tool_result:
                            files_text = "\n".join(tool_result['files'])
                            console.print(Panel(files_text, title="[green]Directory[/green]", border_style="green"))
                        elif 'stdout' in tool_result:
                            if tool_result['stdout']:
                                console.print(Panel(tool_result['stdout'].rstrip(), title="[green]stdout[/green]", border_style="green"))
                            if tool_result['stderr']:
                                console.print(Panel(tool_result['stderr'].rstrip(), title="[yellow]stderr[/yellow]", border_style="yellow"))
                        elif 'message' in tool_result:
                            console.print(f"  [green]✓ {tool_result['message']}[/green]")
                    else:
                        console.print(f"  [red]✗ {tool_result.get('error')}[/red]")

                # Final AI synthesis after tools
                with console.status("[bold cyan]Analyzing results...[/bold cyan]", spinner="dots"):
                    final = ask_ai(history)

                if 'choices' in final:
                    final_msg = final['choices'][0]['message']
                    history.append(final_msg)
                    print_token_usage(final)
                    content = final_msg.get('content') or ''
                    if content:
                        console.print(Panel(
                            Markdown(content),
                            title="[bold cyan]Assistant[/bold cyan]",
                            border_style="cyan"
                        ))
            else:
                content = message.get('content') or ''
                if content:
                    console.print(Panel(
                        Markdown(content),
                        title="[bold cyan]Assistant[/bold cyan]",
                        border_style="cyan"
                    ))

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")

    console.print()
    console.print(Rule("[dim]Session ended[/dim]", style="dim"))
    console.print()

if __name__ == "__main__":
    main()
