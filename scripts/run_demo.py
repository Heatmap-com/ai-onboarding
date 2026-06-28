"""Demo: walk through a complete CreativeOS onboarding via the Brief Scout API.

Usage:
    uv run python scripts/run_demo.py

Outputs:
    demo_conversation.md — a Markdown chat transcript of the onboarding,
    including token usage and estimated cost when tracking is enabled.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from httpx import ASGITransport, AsyncClient

# Enable token/cost tracking for the demo run.
os.environ["BRIEF_SCOUT_TRACK_TOKENS"] = "1"

from brief_scout.main import create_app

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_FILE = PROJECT_ROOT / "demo_conversation.md"

# A plausible onboarding dialogue for a well-known brand so the fixture-based
# FakeLLM adapter returns coherent research and synthesis results.
USER_MESSAGES = [
    "Hi! I'm Alex. I want to get my brand set up on CreativeOS. We're Nike, and our website is nike.com.",
    "Our main competitors are Adidas and Puma.",
    "Our primary goal is new customer acquisition.",
    "We want to reach 18-34 year old athletes who care about style and performance.",
    "We want to explore authentic athlete stories and avoid generic celebrity endorsements.",
]


def _event_payload(line: str) -> dict[str, object] | None:
    """Parse an SSE data line into a dict."""
    if line.startswith("data:"):
        payload_text = line.replace("data: ", "")
        if payload_text:
            return json.loads(payload_text)
    return None


async def run_demo() -> None:
    """Run the full onboarding workflow and write the transcript."""
    app = create_app("config", "demo")
    lines: list[str] = []

    lines.append("# CreativeOS Onboarding Demo\n")
    lines.append(
        "This transcript shows a complete onboarding conversation through the "
        "Brief Scout API, configured for a CreativeOS-style workflow.\n"
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create a session
        session_resp = await client.post("/api/v1/chat/sessions")
        session_data = session_resp.json()
        session_id = session_data["session_id"]

        lines.append(f"**Session ID:** `{session_id}`\n")
        lines.append("---\n")

        # 2. Conversational intake loop
        last_user_message = ""
        for user_msg in USER_MESSAGES:
            last_user_message = user_msg
            lines.append(f"**User:** {user_msg}\n")

            response = await client.post(
                f"/api/v1/chat/{session_id}/message",
                json={"message": user_msg},
            )
            response.raise_for_status()
            data = response.json()

            assistant_msg = data["message"]
            status = data["status"]
            lines.append(f"**CreativeOS:** {assistant_msg}\n")
            lines.append(f"_Status: {status}_\n")

            if status == "researching":
                break

        # 3. Stream the full pipeline (research + synthesis)
        lines.append("---\n")
        lines.append("## Pipeline Stream\n")

        async with client.stream(
            "GET",
            f"/api/v1/chat/{session_id}/stream",
            params={"message": last_user_message},
            timeout=60,
        ) as stream:
            async for line in stream.aiter_lines():
                event = _event_payload(line)
                if event is None:
                    continue
                event_type = event.get("type", "unknown")
                if event_type == "intake":
                    lines.append(
                        f"- **Intake:** {event.get('message', '')} "
                        f"(complete={event.get('is_complete', False)})\n"
                    )
                elif event_type == "research":
                    status = event.get("status", "")
                    steps = event.get("steps", [])
                    if status == "started" and steps:
                        lines.append(f"- **Research started:** {', '.join(steps)}\n")
                    elif status == "complete":
                        lines.append("- **Research complete** ✅\n")
                    else:
                        lines.append(f"- **Research:** {status}\n")
                elif event_type == "research_step":
                    lines.append(f"  - _{event.get('name')}: {event.get('status')}_\n")
                elif event_type == "synthesis":
                    lines.append(f"- **Synthesis:** {event.get('status')}\n")
                elif event_type == "brief":
                    lines.append("- **Brief generated** ✅\n")
                    lines.append(f"  - Brand: {event.get('brief', {}).get('brand_name', '')}\n")
                elif event_type == "error":
                    lines.append(f"- **Error:** {event.get('message')}\n")

        # 4. Retrieve the final brief
        brief_resp = await client.get(f"/api/v1/briefs/{session_id}")
        brief_resp.raise_for_status()
        brief_data = brief_resp.json()
        brief = brief_data.get("brief", {})
        markdown = brief_data.get("markdown", "")

        lines.append("\n---\n")
        lines.append("## Final Creative Brief\n")
        lines.append(f"**Brand:** {brief.get('brand_name', '')}\n")
        lines.append(f"**Primary Goal:** {brief.get('primary_goal', '')}\n")
        lines.append(f"**Target Customer:** {brief.get('target_customer', '')}\n")
        lines.append("\n### Markdown Render\n")
        lines.append("```markdown\n")
        lines.append(markdown)
        lines.append("\n```\n")

    # Append token usage / cost estimate if tracking was enabled.
    token_usage = getattr(app.state, "token_usage", None)
    if token_usage is not None:
        lines.append("\n---\n")
        lines.append("## Token Usage & Estimated Cost\n")
        lines.append("```text\n")
        lines.append(token_usage.summary())
        lines.append("\n```\n")

    OUTPUT_FILE.write_text("".join(lines), encoding="utf-8")
    print(f"Demo transcript written to {OUTPUT_FILE}")

    if token_usage is not None:
        print("\nToken usage summary:\n")
        print(token_usage.summary())


if __name__ == "__main__":
    asyncio.run(run_demo())
