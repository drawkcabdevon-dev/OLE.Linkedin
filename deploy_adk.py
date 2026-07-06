#!/usr/bin/env python3
"""
Build and deploy the OLE ADK agent to Vertex AI Agent Engine.

Requires:
  - gcloud auth login (ADC credentials)
  - google-adk and google-cloud-aiplatform installed

Usage:
  python deploy_adk.py
"""

import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("deploy-adk")

PROJECT = "linkedin-agent-501504"
LOCATION = "us-central1"


def main():
    # Ensure adk_agent.py is importable
    sys.path.insert(0, str(Path(__file__).parent))

    try:
        import vertexai
        from google.adk.agents import LlmAgent
        from google.adk.tools import FunctionTool
        from vertexai.preview.reasoning_engines import AdkApp
    except ImportError as e:
        logger.error(
            f"Missing dependency: {e}\n\n"
            "Install with:\n"
            "  pip install google-adk google-cloud-aiplatform"
        )
        sys.exit(1)

    vertexai.init(project=PROJECT, location=LOCATION)

    from adk_agent import (
        OLE_SYSTEM_PROMPT,
        draft_post,
        rewrite_post,
        generate_batch_ideas,
        generate_carousel_script,
        trending_searches,
        interest_over_time,
        related_queries,
        content_opportunities,
        analyze_topic,
        daily_brief,
        chat_reply,
    )

    agent = LlmAgent(
        name="ole_content_agent",
        model="gemini-2.5-flash",
        instruction=OLE_SYSTEM_PROMPT,
        tools=[
            FunctionTool(draft_post),
            FunctionTool(rewrite_post),
            FunctionTool(generate_batch_ideas),
            FunctionTool(generate_carousel_script),
            FunctionTool(trending_searches),
            FunctionTool(interest_over_time),
            FunctionTool(related_queries),
            FunctionTool(content_opportunities),
            FunctionTool(analyze_topic),
            FunctionTool(daily_brief),
            FunctionTool(chat_reply),
        ],
    )

    app = AdkApp(agent=agent)
    logger.info("Building and deploying ADK agent to Agent Engine...")
    logger.info(f"Project: {PROJECT}")
    logger.info(f"Location: {LOCATION}")
    logger.info("This may take 5-10 minutes...")

    remote = app.deploy()
    resource_name = remote.resource_name
    logger.info(f"Deployed! Resource: {resource_name}")

    # Print env var for bot config
    print(f"\n--- BOT CONFIG ---")
    print(f"Set this env var in your .env or Cloud Run secrets:")
    print(f"AGENT_ENGINE_RESOURCE={resource_name}")
    print(f"---")

    return resource_name


if __name__ == "__main__":
    main()
