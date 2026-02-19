---
name: memory
description: Search through your past conversations and threads to recall previous work, find solutions you've implemented before, or remember context from earlier tasks.
---

# Thread Memory

Search through your past threads and conversations to recall previous work, find solutions, or remember what was done before.

## When to Use

Use this skill when you need to:
- Remember what was done in a previous conversation
- Find a solution or approach you used before
- Look up how you handled a similar task previously
- Recall context from earlier work on a project
- Find threads related to a specific topic

## Usage

Search your thread history with a query:

```bash
python3 /workspace/.claude/skills/memory/scripts/search-threads.py "your search query"
```

### Options

```bash
# Basic search
python3 /workspace/.claude/skills/memory/scripts/search-threads.py "authentication implementation"

# Include message content in search
python3 /workspace/.claude/skills/memory/scripts/search-threads.py "flask api" --include-messages

# Limit results
python3 /workspace/.claude/skills/memory/scripts/search-threads.py "python script" --limit 5

# Filter by status
python3 /workspace/.claude/skills/memory/scripts/search-threads.py "bug fix" --status completed
```

## Examples

```bash
# Find threads about a specific topic
python3 /workspace/.claude/skills/memory/scripts/search-threads.py "react components"

# Find how you solved a problem before
python3 /workspace/.claude/skills/memory/scripts/search-threads.py "database migration error"

# Look up previous work on a project
python3 /workspace/.claude/skills/memory/scripts/search-threads.py "e-commerce checkout"

# Find threads with code examples
python3 /workspace/.claude/skills/memory/scripts/search-threads.py "python web scraping" --include-messages
```

## Output

The script returns:
- Thread titles with relevance scores
- Task descriptions
- Highlighted matching text
- Optionally: matching message content from conversations

## Requirements

- `COMPUTER_AGENTS_API_KEY` environment variable or secret must be set
- Python 3.10+ with `requests` package installed
