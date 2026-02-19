#!/usr/bin/env python3
"""
Deep Research Script using Google Gemini Interactions API (Streaming)

This script performs comprehensive deep research on a topic using Google's
Deep Research agent. It streams progress updates including thinking summaries
for real-time visibility into the research process.

Usage:
    python3 deep-research.py "your research topic" --api-key YOUR_KEY
    python3 deep-research.py "topic" --output report.md --timeout 600

API Key:
    Either pass --api-key KEY or set GEMINI_API_KEY environment variable.

Streaming Output:
    The script streams structured JSON events to stdout for log capture:
    - {"event": "start", "interaction_id": "...", "topic": "..."}
    - {"event": "thinking", "summary": "..."}
    - {"event": "progress", "message": "..."}
    - {"event": "content", "text": "..."}
    - {"event": "complete", "report_file": "...", "sources_count": N}
    - {"event": "error", "message": "..."}
"""

import argparse
import json
import os
import sys
import time
import requests
from typing import Optional, Generator
from datetime import datetime
from pathlib import Path


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
                        # Only set if not already in environment
                        if key not in os.environ:
                            os.environ[key] = value


# Load .env file before accessing environment variables
load_env_file()

API_BASE = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEEP_RESEARCH_AGENT = "deep-research-pro-preview-12-2025"
DEFAULT_TIMEOUT = 540  # 9 minutes - leaves 1 minute buffer for shell timeout (10 min max)
DEFAULT_OUTPUT_DIR = "/workspace/deep_research"
MAX_RESUME_ATTEMPTS = 5  # Multiple resume attempts before falling back to GET polling
MIN_REPORT_LENGTH_FOR_COMPLETION = 1000  # If we have this much content, consider research complete

# Status file for real-time streaming (executor monitors this file)
STATUS_FILE = "/workspace/.deep-research-status.jsonl"

# Track emitted THINKING events to prevent duplicates when stream resumes/reconnects
# The API replays ALL events from the beginning on reconnection, causing duplicate thinking logs
# We ONLY deduplicate thinking events - all other events must pass through
_emitted_thinking_summaries = set()


def emit_event(event_type: str, **kwargs):
    """Emit a structured JSON event to stdout AND status file for real-time streaming.

    Only deduplicates 'thinking' events to prevent duplicate research progress logs
    when the API replays events after stream reconnection. All other events pass through.
    """
    # ONLY deduplicate thinking events - these are the source of duplicate logs on reconnection
    # All other events (content, complete, etc.) must ALWAYS be emitted
    if event_type == "thinking":
        summary = kwargs.get("summary", "")[:100]  # First 100 chars as signature
        if summary in _emitted_thinking_summaries:
            # Skip duplicate thinking summary
            return
        _emitted_thinking_summaries.add(summary)

    event = {"event": event_type, "timestamp": datetime.utcnow().isoformat() + 'Z', **kwargs}
    event_json = json.dumps(event)

    # Write to stdout for Codex CLI capture
    print(event_json, flush=True)

    # Also write to status file for real-time monitoring by executor
    try:
        with open(STATUS_FILE, "a", encoding="utf-8") as f:
            f.write(event_json + "\n")
            f.flush()
    except Exception:
        pass  # Don't fail if we can't write to status file


def clear_status_file():
    """Clear the status file and thinking deduplication at the start of a new research session."""
    global _emitted_thinking_summaries
    _emitted_thinking_summaries = set()  # Reset thinking deduplication for new session

    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write("")  # Truncate the file
    except Exception:
        pass


def create_streaming_research(
    topic: str,
    api_key: str,
    system_instruction: Optional[str] = None,
) -> requests.Response:
    """
    Create a streaming deep research interaction.

    Args:
        topic: The research topic or question
        api_key: Google AI API key
        system_instruction: Optional custom instruction

    Returns:
        requests.Response: Streaming response object
    """
    payload = {
        "agent": DEEP_RESEARCH_AGENT,
        "input": topic,
        "background": True,
        "stream": True,
        "agent_config": {
            "type": "deep-research",
            "thinking_summaries": "auto"
        }
    }

    if system_instruction:
        payload["system_instruction"] = system_instruction

    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "x-goog-api-key": api_key,
    }

    # Use alt=sse for Server-Sent Events streaming
    response = requests.post(
        f"{API_BASE}?alt=sse",
        json=payload,
        headers=headers,
        stream=True,
        timeout=(30, 600)  # (connection timeout, read timeout) - 10 min read timeout for long research
    )
    response.raise_for_status()
    return response


def resume_streaming_research(
    interaction_id: str,
    api_key: str,
    last_event_id: Optional[str] = None,
) -> requests.Response:
    """
    Resume streaming for an existing interaction.

    This is used when the initial stream ends prematurely (network issues,
    server-side timeout, etc.) to continue receiving events.

    Args:
        interaction_id: The interaction ID from interaction.start event
        api_key: Google AI API key
        last_event_id: The last event ID to resume from (optional)

    Returns:
        requests.Response: Streaming response object
    """
    headers = {
        "Accept": "text/event-stream",
        "x-goog-api-key": api_key,
    }

    url = f"{API_BASE}/{interaction_id}?stream=true&alt=sse"
    if last_event_id:
        url += f"&last_event_id={last_event_id}"

    response = requests.get(
        url,
        headers=headers,
        stream=True,
        timeout=(30, 120)  # 30s connect, 120s read - deep research can have long pauses between events
    )
    response.raise_for_status()
    return response


def parse_sse_events(response: requests.Response) -> Generator[dict, None, None]:
    """
    Parse Server-Sent Events from streaming response.

    Args:
        response: Streaming response from API

    Yields:
        dict: Parsed event data
    """
    buffer = ""

    # Force UTF-8 encoding to handle special characters correctly (em-dash, etc.)
    # The API returns UTF-8 but may not specify it in Content-Type header
    response.encoding = 'utf-8'

    for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
        if chunk:
            buffer += chunk

            # Process complete events (separated by double newlines)
            while "\n\n" in buffer:
                event_str, buffer = buffer.split("\n\n", 1)

                # Parse SSE format
                event_type = None
                event_data = None

                for line in event_str.split("\n"):
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data_str = line[5:].strip()
                        if data_str:
                            try:
                                event_data = json.loads(data_str)
                            except json.JSONDecodeError:
                                event_data = {"raw": data_str}

                if event_data is not None:
                    if event_type:
                        event_data["_event_type"] = event_type
                    yield event_data


def process_stream_events(
    response: requests.Response,
    start_time: float,
    timeout: int,
    verbose: bool,
    interaction_id: Optional[str],
    last_event_id: Optional[str],
    report_text: str,
    sources: list,
    thoughts: list,
    event_count: int,
) -> tuple:
    """
    Process events from a streaming response.

    Returns:
        tuple: (interaction_id, last_event_id, report_text, sources, thoughts,
                event_count, exit_reason, is_complete)
    """
    exit_reason = "stream_ended"
    is_complete = False
    last_event_type = None

    for event in parse_sse_events(response):
        event_count += 1
        elapsed = time.time() - start_time
        if elapsed > timeout:
            exit_reason = "timeout"
            emit_event("timeout",
                      interaction_id=interaction_id,
                      elapsed_seconds=int(elapsed),
                      event_count=event_count,
                      report_length=len(report_text),
                      message="Research timed out - may still be running on server")
            is_complete = True  # Don't resume after timeout
            break

        event_type = event.get("_event_type") or event.get("eventType") or event.get("type")
        last_event_type = event_type

        # Verbose logging for debugging
        if verbose:
            event_preview = {k: str(v)[:100] if isinstance(v, str) else v for k, v in event.items() if k != "_event_type"}
            emit_event("debug_raw_event",
                      sse_event_type=event_type,
                      keys=list(event.keys()),
                      event_preview=event_preview,
                      event_count=event_count,
                      elapsed_seconds=int(elapsed))

        # Handle different event types
        if event_type == "interaction.start" or "interaction" in event:
            interaction_data = event.get("interaction", event)
            new_id = interaction_data.get("id")
            if new_id:
                interaction_id = new_id
                emit_event("interaction_started",
                          interaction_id=interaction_id,
                          elapsed_seconds=int(elapsed))

        if event.get("eventId"):
            last_event_id = event["eventId"]

        if event_type == "content.delta" or "delta" in event:
            delta = event.get("delta", event)
            delta_type = delta.get("type")

            if verbose:
                emit_event("debug_delta",
                          delta_type=delta_type,
                          delta_keys=list(delta.keys()) if isinstance(delta, dict) else None,
                          has_text="text" in delta if isinstance(delta, dict) else False)

            if delta_type == "text":
                text = delta.get("text", "")
                report_text += text
                if text.strip():
                    emit_event("content", text=text[:200] + "..." if len(text) > 200 else text,
                              accumulated_length=len(report_text))

            elif delta_type == "thought_summary":
                content = delta.get("content", {})
                summary = content.get("text", str(content))
                thoughts.append(summary)
                emit_event("thinking", summary=summary)

        elif event_type == "interaction.complete":
            exit_reason = "interaction_complete"
            # DEBUG: Log the full structure of interaction.complete event to understand where content is
            emit_event("debug_interaction_complete",
                      event_keys=list(event.keys()),
                      has_outputs="outputs" in event,
                      has_interaction="interaction" in event,
                      event_preview={k: str(v)[:200] if isinstance(v, (str, list, dict)) else v for k, v in event.items() if k != "_event_type"})
            # CRITICAL: Extract outputs from the interaction.complete event BEFORE marking complete
            # The final report content is delivered in this event's outputs array
            if "outputs" in event:
                emit_event("extracting_outputs",
                          outputs_count=len(event.get("outputs", [])),
                          event_keys=list(event.keys()))
                for output in event.get("outputs", []):
                    output_type = output.get("type")
                    if output_type == "text":
                        text = output.get("text", "")
                        report_text += text
                        emit_event("content_extracted", text_length=len(text), total_length=len(report_text))
                        for ann in output.get("annotations", []):
                            if ann.get("source"):
                                sources.append(ann["source"])
                    elif output_type == "thought":
                        for item in output.get("summary", []):
                            if item.get("type") == "text":
                                thoughts.append(item.get("text", ""))
            # Also check for 'interaction' object which may contain outputs
            if "interaction" in event:
                interaction_obj = event.get("interaction", {})
                if "outputs" in interaction_obj:
                    emit_event("extracting_interaction_outputs",
                              outputs_count=len(interaction_obj.get("outputs", [])))
                    for output in interaction_obj.get("outputs", []):
                        output_type = output.get("type")
                        if output_type == "text":
                            text = output.get("text", "")
                            report_text += text
                            emit_event("content_extracted", text_length=len(text), total_length=len(report_text))
                            for ann in output.get("annotations", []):
                                if ann.get("source"):
                                    sources.append(ann["source"])
            emit_event("research_complete",
                      interaction_id=interaction_id,
                      elapsed_seconds=int(elapsed),
                      event_count=event_count,
                      report_length=len(report_text))
            # ONLY mark as complete if we actually got content!
            # Sometimes interaction.complete arrives before content is ready
            if len(report_text) >= MIN_REPORT_LENGTH_FOR_COMPLETION:
                is_complete = True
                break
            else:
                # No content yet - don't break, let fallback logic handle it
                emit_event("interaction_complete_no_content",
                          message="interaction.complete received but no content yet, will try fallback fetch",
                          report_length=len(report_text))
                break  # Still break from stream loop, but is_complete stays False

        # Handle outputs array (non-streaming format) - for events other than interaction.complete
        if "outputs" in event:
            for output in event.get("outputs", []):
                output_type = output.get("type")
                if output_type == "text":
                    text = output.get("text", "")
                    report_text += text
                    for ann in output.get("annotations", []):
                        if ann.get("source"):
                            sources.append(ann["source"])
                elif output_type == "thought":
                    for item in output.get("summary", []):
                        if item.get("type") == "text":
                            thoughts.append(item.get("text", ""))

        # Handle status updates
        status = event.get("status")
        if status:
            emit_event("status", status=status, elapsed_seconds=int(elapsed), event_count=event_count, report_length=len(report_text))
            if status in ("completed", "failed", "cancelled"):
                exit_reason = f"status_{status}"
                is_complete = True
                break

    return (interaction_id, last_event_id, report_text, sources, thoughts,
            event_count, exit_reason, is_complete)


def stream_research(
    topic: str,
    api_key: str,
    output_file: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    system_instruction: Optional[str] = None,
    verbose: bool = False,
) -> dict:
    """
    Perform streaming deep research on a topic with resilient reconnection.

    This implements the resilient streaming pattern recommended by Google:
    - Start with POST to create the interaction
    - If stream ends prematurely, resume with GET using last_event_id
    - Continue until interaction.complete or timeout

    Args:
        topic: The research topic or question
        api_key: Google AI API key
        output_file: Optional path to save the report
        timeout: Maximum time to wait for results
        system_instruction: Optional custom instruction

    Returns:
        dict: Research results including report and metadata
    """
    start_time = time.time()
    interaction_id = None
    last_event_id = None
    report_text = ""
    sources = []
    thoughts = []
    event_count = 0
    is_complete = False
    resume_attempts = 0
    exit_reason = "stream_ended"

    # Clear status file for fresh streaming
    clear_status_file()

    emit_event("start", topic=topic, timeout=timeout)

    # Initial POST request to create the interaction
    try:
        response = create_streaming_research(
            topic=topic,
            api_key=api_key,
            system_instruction=system_instruction,
        )

        (interaction_id, last_event_id, report_text, sources, thoughts,
         event_count, exit_reason, is_complete) = process_stream_events(
            response, start_time, timeout, verbose,
            interaction_id, last_event_id, report_text, sources, thoughts, event_count
        )

    except requests.exceptions.Timeout:
        emit_event("connection_timeout",
                  message="Initial connection timed out, will attempt to resume",
                  event_count=event_count)
    except requests.exceptions.RequestException as e:
        emit_event("error", message=str(e), error_type=type(e).__name__, event_count=event_count)
        raise

    # STRATEGY: If stream ended without content but we have thinking, try GET fetch FIRST
    # The Deep Research API often delivers final content via non-streaming GET, not stream resume
    # Resuming the stream often causes the API to replay all events from the beginning!

    if not is_complete and len(report_text) == 0 and interaction_id and len(thoughts) >= 5:
        emit_event("attempting_get_fetch_first",
                  interaction_id=interaction_id,
                  thoughts_count=len(thoughts),
                  message="Stream ended with thinking but no content, trying GET fetch before resume")

        # Wait a bit for the API to finalize the result
        time.sleep(3)

        try:
            final_result = check_interaction(interaction_id, api_key)
            emit_event("get_fetch_result",
                      result_keys=list(final_result.keys()) if isinstance(final_result, dict) else None,
                      has_outputs="outputs" in final_result if isinstance(final_result, dict) else False)

            if isinstance(final_result, dict):
                # Check for outputs at top level
                if "outputs" in final_result:
                    for output in final_result.get("outputs", []):
                        if output.get("type") == "text":
                            text = output.get("text", "")
                            report_text += text
                            emit_event("get_fetch_content_extracted", text_length=len(text))
                            for ann in output.get("annotations", []):
                                if ann.get("source"):
                                    sources.append(ann["source"])

                # Check for outputs in interaction object
                interaction_obj = final_result.get("interaction", {})
                if "outputs" in interaction_obj:
                    for output in interaction_obj.get("outputs", []):
                        if output.get("type") == "text":
                            text = output.get("text", "")
                            report_text += text
                            emit_event("get_fetch_content_extracted", text_length=len(text))
                            for ann in output.get("annotations", []):
                                if ann.get("source"):
                                    sources.append(ann["source"])

                # If we got content, mark as complete
                if len(report_text) >= MIN_REPORT_LENGTH_FOR_COMPLETION:
                    emit_event("get_fetch_success",
                              report_length=len(report_text),
                              message="Successfully fetched content via GET")
                    is_complete = True
        except Exception as e:
            emit_event("get_fetch_error", error=str(e), error_type=type(e).__name__)

    # Try stream resume if GET fetch didn't get content - but only 1 attempt with short timeout
    # Stream resume can sometimes get the completion event that streaming missed
    while not is_complete and interaction_id and resume_attempts < MAX_RESUME_ATTEMPTS and len(report_text) == 0:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            emit_event("timeout",
                      interaction_id=interaction_id,
                      elapsed_seconds=int(elapsed),
                      message="Research timed out during resume attempts")
            break

        # If we have substantial report content from any source, stop
        if len(report_text) >= MIN_REPORT_LENGTH_FOR_COMPLETION:
            emit_event("content_complete",
                      interaction_id=interaction_id,
                      report_length=len(report_text),
                      message="Research has substantial content, treating as complete")
            is_complete = True
            break

        resume_attempts += 1
        emit_event("resuming_stream",
                  interaction_id=interaction_id,
                  last_event_id=last_event_id,
                  attempt=resume_attempts,
                  elapsed_seconds=int(elapsed),
                  report_length=len(report_text),
                  warning="Stream resume may cause API to replay events")

        # Brief delay before resuming
        time.sleep(2)

        try:
            response = resume_streaming_research(
                interaction_id=interaction_id,
                api_key=api_key,
                last_event_id=last_event_id,
            )

            (interaction_id, last_event_id, report_text, sources, thoughts,
             event_count, exit_reason, is_complete) = process_stream_events(
                response, start_time, timeout, verbose,
                interaction_id, last_event_id, report_text, sources, thoughts, event_count
            )

        except requests.exceptions.Timeout:
            emit_event("resume_timeout",
                      interaction_id=interaction_id,
                      attempt=resume_attempts,
                      message="Resume connection timed out, will retry")
        except requests.exceptions.RequestException as e:
            emit_event("resume_error",
                      message=str(e),
                      error_type=type(e).__name__,
                      attempt=resume_attempts)
            if resume_attempts >= MAX_RESUME_ATTEMPTS:
                raise

    # FALLBACK: If we have no report content but have interaction_id, poll GET until content is ready
    # The Deep Research API may still be processing - poll until status is 'completed' with outputs
    # Research can take 3-10 minutes, so we poll aggressively for up to 6 minutes
    MAX_FALLBACK_ATTEMPTS = 36
    FALLBACK_POLL_INTERVAL = 10  # seconds between polls (36 * 10 = 360s = 6 min)

    if len(report_text) == 0 and interaction_id and len(thoughts) >= 3:  # Lower threshold to start polling
        emit_event("fallback_fetch",
                  interaction_id=interaction_id,
                  message="No content received, polling GET endpoint for results")

        for fallback_attempt in range(MAX_FALLBACK_ATTEMPTS):
            elapsed = time.time() - start_time
            if elapsed > timeout:
                emit_event("fallback_timeout",
                          attempt=fallback_attempt + 1,
                          elapsed_seconds=int(elapsed),
                          message="Timeout reached during fallback polling")
                break

            try:
                final_result = check_interaction(interaction_id, api_key)
                status = final_result.get("status", "unknown") if isinstance(final_result, dict) else "unknown"

                emit_event("fallback_fetch_result",
                          attempt=fallback_attempt + 1,
                          status=status,
                          result_keys=list(final_result.keys()) if isinstance(final_result, dict) else None,
                          has_outputs="outputs" in final_result if isinstance(final_result, dict) else False)

                # Try to extract outputs from the GET response
                if isinstance(final_result, dict):
                    # Check for outputs at top level
                    if "outputs" in final_result:
                        for output in final_result.get("outputs", []):
                            if output.get("type") == "text":
                                text = output.get("text", "")
                                report_text += text
                                emit_event("fallback_content_extracted", text_length=len(text))
                                for ann in output.get("annotations", []):
                                    if ann.get("source"):
                                        sources.append(ann["source"])

                    # Check for outputs in interaction object
                    interaction_obj = final_result.get("interaction", final_result)
                    if "outputs" in interaction_obj and interaction_obj is not final_result:
                        for output in interaction_obj.get("outputs", []):
                            if output.get("type") == "text":
                                text = output.get("text", "")
                                report_text += text
                                emit_event("fallback_content_extracted", text_length=len(text))
                                for ann in output.get("annotations", []):
                                    if ann.get("source"):
                                        sources.append(ann["source"])

                # If we got content, we're done!
                if len(report_text) >= MIN_REPORT_LENGTH_FOR_COMPLETION:
                    emit_event("fallback_fetch_success",
                              report_length=len(report_text),
                              attempts=fallback_attempt + 1,
                              message="Successfully fetched content via GET polling")
                    is_complete = True
                    break

                # If status is still in_progress, wait and retry
                if status == "in_progress":
                    emit_event("fallback_fetch_waiting",
                              attempt=fallback_attempt + 1,
                              status=status,
                              message=f"Research still in progress, waiting {FALLBACK_POLL_INTERVAL}s before retry")
                    time.sleep(FALLBACK_POLL_INTERVAL)
                    continue

                # If status is completed but no content, try a few more times (content might be slow to appear)
                if status == "completed":
                    if fallback_attempt < 5:  # Try up to 5 more times after completed
                        emit_event("fallback_fetch_waiting",
                                  attempt=fallback_attempt + 1,
                                  status=status,
                                  message=f"Status completed but no content yet, retrying in {FALLBACK_POLL_INTERVAL}s")
                        time.sleep(FALLBACK_POLL_INTERVAL)
                        continue
                    else:
                        emit_event("fallback_fetch_empty",
                                  attempt=fallback_attempt + 1,
                                  status=status,
                                  message="Status is completed but no outputs found after multiple attempts")
                        break

                # If status is failed or cancelled, stop
                if status in ("failed", "cancelled"):
                    emit_event("fallback_fetch_failed",
                              attempt=fallback_attempt + 1,
                              status=status,
                              message=f"Research {status}")
                    break

                # Unknown status - wait and retry
                emit_event("fallback_fetch_waiting",
                          attempt=fallback_attempt + 1,
                          status=status,
                          message=f"Unknown status '{status}', waiting {FALLBACK_POLL_INTERVAL}s before retry")
                time.sleep(FALLBACK_POLL_INTERVAL)

            except Exception as e:
                emit_event("fallback_fetch_error",
                          error=str(e),
                          error_type=type(e).__name__,
                          attempt=fallback_attempt + 1)
                # Wait before retry on error
                time.sleep(FALLBACK_POLL_INTERVAL)

    # Final status
    emit_event("stream_ended",
              exit_reason=exit_reason,
              event_count=event_count,
              report_length=len(report_text),
              thoughts_count=len(thoughts),
              resume_attempts=resume_attempts,
              is_complete=is_complete,
              elapsed_seconds=int(time.time() - start_time))

    # Deduplicate sources
    sources = list(set(sources))

    # Build result
    result = {
        "report": report_text.strip(),
        "sources": sources,
        "thought_summary": thoughts,
        "interaction_id": interaction_id,
        "elapsed_seconds": int(time.time() - start_time),
    }

    # Always save to output file if we have content
    if report_text.strip():
        if output_file is None:
            # Generate default filename
            safe_topic = "".join(c if c.isalnum() or c in " -_" else "_" for c in topic[:50])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"{DEFAULT_OUTPUT_DIR}/deep_research_{timestamp}_{safe_topic}.md"

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)

        # Write markdown report with explicit UTF-8 encoding
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result["report"])

            if sources:
                f.write("\n\n---\n\n## Sources\n\n")
                for source in sources:
                    f.write(f"- {source}\n")

        result["output_file"] = output_file
        emit_event("complete",
                  report_file=output_file,
                  sources_count=len(sources),
                  sources=sources,  # Include actual source URLs
                  report_length=len(report_text),
                  thoughts_count=len(thoughts))
    else:
        emit_event("complete",
                  report_file=None,
                  message="No report content received",
                  interaction_id=interaction_id,
                  exit_reason=exit_reason,
                  event_count=event_count,
                  thoughts_count=len(thoughts))

    return result


def check_interaction(interaction_id: str, api_key: str) -> dict:
    """
    Check the status of an existing interaction.

    Args:
        interaction_id: The interaction ID to check
        api_key: Google AI API key

    Returns:
        dict: Current interaction state
    """
    url = f"{API_BASE}/{interaction_id}"
    headers = {"x-goog-api-key": api_key}

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    return response.json()


def main():
    parser = argparse.ArgumentParser(
        description="Perform deep research using Gemini Deep Research agent (streaming)"
    )
    parser.add_argument("topic", nargs="?", help="Research topic or question")
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Save report to file (default: auto-generated in /workspace/research/)"
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Maximum time to wait in seconds (default: {DEFAULT_TIMEOUT})"
    )
    parser.add_argument(
        "--check",
        metavar="INTERACTION_ID",
        help="Check status of an existing interaction"
    )
    parser.add_argument(
        "--system",
        metavar="INSTRUCTION",
        help="Custom system instruction for the research"
    )
    parser.add_argument(
        "--api-key",
        metavar="KEY",
        help="Gemini API key (alternative to GEMINI_API_KEY env var)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging of raw events"
    )

    args = parser.parse_args()

    # API key lookup order: 1) --api-key arg, 2) env var, 3) secrets file
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Try reading from secrets file (written by container entrypoint)
        secrets_file = "/workspace/.secrets/gemini_api_key"
        if os.path.exists(secrets_file):
            with open(secrets_file, 'r') as f:
                api_key = f.read().strip()
    if not api_key:
        emit_event("error", message="GEMINI_API_KEY not found. Check env var or /workspace/.secrets/gemini_api_key")
        sys.exit(1)

    try:
        if args.check:
            # Check existing interaction
            result = check_interaction(args.check, api_key)
            print(json.dumps(result, indent=2))
        elif args.topic:
            # Start new research
            result = stream_research(
                topic=args.topic,
                api_key=api_key,
                output_file=args.output,
                timeout=args.timeout,
                system_instruction=args.system,
                verbose=args.verbose,
            )

            # Print final summary event
            emit_event("summary",
                      interaction_id=result.get("interaction_id"),
                      output_file=result.get("output_file"),
                      report_length=len(result.get("report", "")),
                      sources_count=len(result.get("sources", [])),
                      thoughts_count=len(result.get("thought_summary", [])))

            # CRITICAL: Print the actual report content so the agent can see and use it
            # The JSON events above are for real-time streaming UI, but the agent needs
            # the actual text content to work with
            report_content = result.get("report", "")
            if report_content:
                output_file = result.get('output_file', 'N/A')
                sources = result.get("sources", [])

                # INSTRUCTIONS FIRST - before any content that might be truncated
                print("\n" + "="*80, flush=True)
                print("✅ DEEP RESEARCH COMPLETE - REPORT SAVED TO FILE", flush=True)
                print("="*80, flush=True)
                print(f"Report file: {output_file}", flush=True)
                print(f"Report length: {len(report_content)} characters", flush=True)
                print(f"Sources: {len(sources)}", flush=True)
                print("="*80, flush=True)
                print("🚨 NEXT STEPS - ENHANCE REPORT WITH IMAGES 🚨", flush=True)
                print("="*80, flush=True)
                print(f"""
🎨 MANDATORY: YOU MUST GENERATE IMAGES FOR THIS REPORT 🎨

STEP 1: Generate a title/header image for the report:
   python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "professional illustration representing [TOPIC], modern infographic style, clean design" --output /workspace/generated_images/title.png --aspect-ratio 16:9

STEP 2: Generate 1-2 visualization images for key concepts:
   python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "diagram showing [KEY CONCEPT FROM REPORT], infographic style, labeled" --output /workspace/generated_images/concept1.png
   python3 /workspace/.claude/skills/image-generation/scripts/generate-image.py "visualization of [ANOTHER KEY CONCEPT], professional illustration" --output /workspace/generated_images/concept2.png

STEP 3: Insert images into the report:
   # Add title image after the first heading (line 2):
   sed -i '2a\\\\n![Title](../generated_images/title.png)\\n' {output_file}

   # Add concept images after relevant section headings:
   sed -i '/## [Section Name]/a\\\\n![Concept](../generated_images/concept1.png)\\n' {output_file}

📁 FILE LOCATIONS:
   - Report: {output_file} (in /workspace/deep_research/)
   - Images: /workspace/generated_images/
   - Relative path from report to images: ../generated_images/filename.png

⚠️  IMPORTANT:
   - You MUST generate at least 2 images (title + 1 concept)
   - Replace [TOPIC], [KEY CONCEPT], [Section Name] with actual content from the report
   - Create the images directory first: mkdir -p /workspace/generated_images

❌ DO NOT: Skip image generation, create new markdown files, rewrite the report
✅ DO: Generate 2+ images, insert them into the existing report with sed
""", flush=True)
                print("="*80, flush=True)
            else:
                print("\n" + "="*80, flush=True)
                print("❌ WARNING: No report content was generated", flush=True)
                print(f"Interaction ID: {result.get('interaction_id', 'N/A')}", flush=True)
                print("The research may have failed or timed out.", flush=True)
                print("\nDO NOT retry the research. Inform the user that research failed.", flush=True)
                print("="*80, flush=True)
        else:
            parser.print_help()
            sys.exit(1)

    except requests.exceptions.HTTPError as e:
        emit_event("error",
                  message=str(e),
                  error_type="HTTPError")
        if e.response is not None:
            try:
                error_detail = e.response.json()
                emit_event("error_detail", detail=error_detail)
            except:
                emit_event("error_response", text=e.response.text[:500])
        sys.exit(1)
    except Exception as e:
        emit_event("error", message=str(e), error_type=type(e).__name__)
        sys.exit(1)


if __name__ == "__main__":
    main()
