#!/usr/bin/env python3
r"""
Event logger for capturing and persisting hook events to JSONL files.

This diagnostic tool captures and logs all Claude Code hook events to daily JSONL files.
Use it to explore the complete payload structure of each hook event, discover available fields, and
understand the data flow before implementing custom hooks. Essential for hook development and debugging.

Output: ~/.claude/hooks-logs/DD-MM-YYYY.jsonl

Setup the hook in your .claude/settings.json file (you can add any/all events you want to log):
{
  "hooks": {
    "Notification": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "Stop": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "SessionStart": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "UserPromptSubmit": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "PreToolUse": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "PermissionRequest": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "PostToolUse": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "PostToolUseFailure": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "SubagentStart": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "SubagentStop": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "TaskCompleted": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "TeammateIdle": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "PreCompact": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }],
    "SessionEnd": [{ "matcher": "", "hooks": [{ "type": "command", "command": "python /path/to/event-logger.py" }] }]
  }
}

All supported events:
  SessionStart, SessionEnd, UserPromptSubmit, PreToolUse, PostToolUse,
  PostToolUseFailure, PermissionRequest, SubagentStart, SubagentStop,
  Stop, PreCompact, Setup, Notification, TaskCompleted, TeammateIdle

Commands:

Unix/Linux/macOS

View today's logs: cat ~/.claude/hooks-logs/$(date +%d-%m-%Y).jsonl | jq
Monitor logs in real-time: tail -f ~/.claude/hooks-logs/$(date +%d-%m-%Y).jsonl | jq
Filter by event type: cat ~/.claude/hooks-logs/*.jsonl | jq 'select(.hook_event_name=="PreToolUse")'
View all unique event types: cat ~/.claude/hooks-logs/*.jsonl | jq -r '.hook_event_name' | sort -u
Count events by type: cat ~/.claude/hooks-logs/*.jsonl | jq -r '.hook_event_name' | sort | uniq -c
View most recent 10 events: cat ~/.claude/hooks-logs/*.jsonl | jq -s '.[-10:]'
Extract specific fields: cat ~/.claude/hooks-logs/*.jsonl | jq '{event: .hook_event_name, time: .ts, cwd: .cwd}'

Windows (PowerShell)

View today's logs: Get-Content "$env:USERPROFILE\.claude\hooks-logs\$(Get-Date -Format 'dd-MM-yyyy').jsonl" | jq
Monitor logs in real-time: Get-Content "$env:USERPROFILE\.claude\hooks-logs\$(Get-Date -Format 'dd-MM-yyyy').jsonl" -Wait -Tail 10 | jq
Filter by event type: Get-Content "$env:USERPROFILE\.claude\hooks-logs\*.jsonl" | jq 'select(.hook_event_name=="PreToolUse")'
View all unique event types: Get-Content "$env:USERPROFILE\.claude\hooks-logs\*.jsonl" | jq -r '.hook_event_name' | Sort-Object -Unique
Count events by type: Get-Content "$env:USERPROFILE\.claude\hooks-logs\*.jsonl" | jq -r '.hook_event_name' | Group-Object | Select-Object Count, Name
View most recent 10 events: Get-Content "$env:USERPROFILE\.claude\hooks-logs\*.jsonl" | jq -s '.[-10:]'
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union

# Type aliases for clarity
JsonValue = Union[None, bool, int, float, str, List[Any], Dict[str, Any]]


def get_log_file_path() -> Path:
    """
    Get the path to today's log file, creating the directory if needed.
    
    Returns:
        Path object pointing to the daily log file.
    """
    log_dir = Path.home() / ".claude" / "hooks-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{datetime.now():%d-%m-%Y}.jsonl"


def truncate_string(value: str, max_length: int = 2000) -> str:
    """
    Truncate a string if it exceeds max_length.
    
    Args:
        value: String to potentially truncate.
        max_length: Maximum allowed length before truncation.
        
    Returns:
        Original or truncated string with length indicator.
    """
    if len(value) > max_length:
        return f"{value[:max_length]}... ({len(value)} chars)"
    return value


def process_value(
    value: Any,
    max_str_length: int = 2000,
    max_list_items: int = 50
) -> JsonValue:
    """
    Process and sanitize values for JSON serialization with size limits.
    
    Recursively processes nested structures, truncating strings and lists
    that exceed specified limits to prevent excessive log file growth.
    
    Args:
        value: Value to process.
        max_str_length: Maximum string length before truncation.
        max_list_items: Maximum list items before truncation.
        
    Returns:
        Processed value safe for JSON serialization.
    """
    # Handle primitive types that don't need processing
    if value is None or isinstance(value, (bool, int, float)):
        return value
    
    # Truncate long strings
    if isinstance(value, str):
        return truncate_string(value, max_str_length)
    
    # Process and truncate lists
    if isinstance(value, list):
        processed_items = [
            process_value(item, max_str_length, max_list_items)
            for item in value[:max_list_items]
        ]
        if len(value) > max_list_items:
            processed_items.append(f"... +{len(value) - max_list_items} more")
        return processed_items
    
    # Recursively process dictionaries
    if isinstance(value, dict):
        return {
            str(key): process_value(val, max_str_length, max_list_items)
            for key, val in value.items()
        }
    
    # Fallback for unknown types
    return str(value)


def parse_stdin_data(stdin_data: str) -> Dict[str, Any]:
    """
    Parse JSON data from stdin, with fallback for invalid JSON.
    
    Args:
        stdin_data: Raw string data from stdin.
        
    Returns:
        Parsed dictionary or dict with raw data if parsing fails.
    """
    if not stdin_data:
        return {}
    
    try:
        return json.loads(stdin_data)
    except json.JSONDecodeError:
        return {"_raw": stdin_data}


def create_event_entry(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a standardized event log entry.
    
    Args:
        data: Parsed event data.
        
    Returns:
        Dictionary containing timestamp, event name, working directory, and processed data.
    """
    return {
        "ts": datetime.now().isoformat(),
        "hook_event_name": data.get("hook_event_name", "unknown"),
        "cwd": os.getcwd(),
        "data": process_value(data),
    }


def append_to_log(log_file: Path, event: Dict[str, Any]) -> None:
    """
    Append event entry to log file as a JSON line.
    
    Args:
        log_file: Path to the log file.
        event: Event dictionary to write.
    """
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")


def main() -> None:
    """Main entry point for the event logger."""
    stdin_data = sys.stdin.read()
    data = parse_stdin_data(stdin_data)
    event = create_event_entry(data)
    log_file = get_log_file_path()
    append_to_log(log_file, event)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[event-logger] Error: {e}", file=sys.stderr)
        sys.exit(1)