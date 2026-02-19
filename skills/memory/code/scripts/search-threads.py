#!/usr/bin/env python3
"""
Thread Memory Search Script

Search through your past threads and conversations to recall previous work,
find solutions you've implemented before, or remember context from earlier tasks.

Usage:
    python3 search-threads.py "your search query"
    python3 search-threads.py "flask api" --include-messages
    python3 search-threads.py "bug fix" --limit 5 --status completed

Environment Variables:
    COMPUTER_AGENTS_API_KEY - Required. Your Computer Agents API key.
"""

import argparse
import json
import os
import sys
import requests
from pathlib import Path
from typing import Optional


def load_env_file():
    """Load environment variables from .env file in workspace."""
    env_paths = [
        Path('/workspace/.env'),
        Path.cwd() / '.env',
    ]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip().strip('"').strip("'")
                        if key not in os.environ:
                            os.environ[key] = value


def get_api_key() -> Optional[str]:
    """Get the Computer Agents API key from various sources."""
    # Try environment variable first
    api_key = os.environ.get("COMPUTER_AGENTS_API_KEY")
    if api_key:
        return api_key

    # Try secrets file (written by container entrypoint)
    secrets_paths = [
        Path('/workspace/.secrets/computer_agents_api_key'),
        Path('/workspace/.secrets/api_key'),
    ]
    for secrets_path in secrets_paths:
        if secrets_path.exists():
            with open(secrets_path, 'r') as f:
                api_key = f.read().strip()
                if api_key:
                    return api_key

    return None


def search_threads(
    query: str,
    api_key: str,
    limit: int = 10,
    status: Optional[str] = None,
    include_messages: bool = False,
) -> dict:
    """
    Search threads using the Computer Agents API.

    Args:
        query: Search query
        api_key: Computer Agents API key
        limit: Maximum number of results
        status: Filter by thread status (active, completed, failed, all)
        include_messages: Include matching messages in results

    Returns:
        dict: API response with search results
    """
    api_base = os.environ.get("COMPUTER_AGENTS_API_URL", "https://api.computer-agents.com")

    payload = {
        "query": query,
        "limit": limit,
        "includeMessages": include_messages,
    }

    if status and status != "all":
        payload["status"] = status

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        f"{api_base}/threads/search",
        json=payload,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    return response.json()


def strip_html_tags(text: str) -> str:
    """Strip HTML tags from text, replacing <mark> with emphasis markers."""
    if not text:
        return ""
    # Replace <mark> tags with emphasis markers for terminal display
    text = text.replace("<mark>", "**").replace("</mark>", "**")
    return text


def format_results(data: dict, verbose: bool = False) -> str:
    """
    Format search results for display.

    Args:
        data: API response data
        verbose: Show more details

    Returns:
        str: Formatted results
    """
    results = data.get("results", [])
    total = data.get("total", 0)

    if not results:
        return "No matching threads found."

    output = []
    output.append(f"## Found {total} matching thread(s)\n")

    for i, result in enumerate(results, 1):
        thread = result.get("thread", {})
        score = result.get("score", 0)
        highlights = result.get("highlights", {})

        # Thread header
        title = thread.get("title") or thread.get("task") or "Untitled"
        status = thread.get("status", "unknown")
        created = thread.get("createdAt", "")[:10]  # Just the date part

        output.append(f"### {i}. {title}")
        output.append(f"- **Status:** {status}")
        output.append(f"- **Created:** {created}")
        output.append(f"- **Relevance:** {score:.2f}")

        # Show highlighted task if available
        if highlights.get("task"):
            task_highlight = strip_html_tags(highlights["task"])
            output.append(f"- **Task:** {task_highlight}")
        elif thread.get("task"):
            output.append(f"- **Task:** {thread['task'][:200]}")

        # Show thread ID for reference
        output.append(f"- **Thread ID:** {thread.get('id', 'unknown')}")

        # Show matching messages if available
        matching_messages = result.get("matchingMessages", [])
        if matching_messages:
            output.append("\n**Matching Messages:**")
            for msg in matching_messages[:3]:  # Limit to 3 messages
                role = msg.get("role", "unknown")
                highlight = strip_html_tags(msg.get("highlight", ""))
                if highlight:
                    output.append(f"  - [{role}] {highlight[:300]}")

        output.append("")  # Empty line between results

    # Footer with search metadata
    metadata = data.get("searchMetadata", {})
    processing_time = metadata.get("processingTimeMs", 0)
    has_more = data.get("hasMore", False)

    output.append("---")
    output.append(f"Search completed in {processing_time}ms")
    if has_more:
        output.append(f"More results available (showing {len(results)} of {total})")

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Search through your past threads and conversations"
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Search query"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results (default: 10)"
    )
    parser.add_argument(
        "--status",
        choices=["active", "completed", "failed", "all"],
        default="all",
        help="Filter by thread status"
    )
    parser.add_argument(
        "--include-messages",
        action="store_true",
        help="Include matching message content in results"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON response"
    )

    args = parser.parse_args()

    if not args.query:
        parser.print_help()
        sys.exit(1)

    # Load environment
    load_env_file()

    # Get API key
    api_key = get_api_key()
    if not api_key:
        print("Error: COMPUTER_AGENTS_API_KEY not found", file=sys.stderr)
        print("\nSet the API key using one of these methods:", file=sys.stderr)
        print("  1. Environment variable: export COMPUTER_AGENTS_API_KEY=your_key", file=sys.stderr)
        print("  2. .env file: COMPUTER_AGENTS_API_KEY=your_key", file=sys.stderr)
        print("  3. Secrets file: /workspace/.secrets/computer_agents_api_key", file=sys.stderr)
        sys.exit(1)

    try:
        # Perform search
        data = search_threads(
            query=args.query,
            api_key=api_key,
            limit=args.limit,
            status=args.status,
            include_messages=args.include_messages,
        )

        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(format_results(data))

    except requests.exceptions.HTTPError as e:
        print(f"Error: API request failed - {e}", file=sys.stderr)
        if e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"Details: {json.dumps(error_detail, indent=2)}", file=sys.stderr)
            except:
                print(f"Response: {e.response.text[:500]}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("Error: Request timed out", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
