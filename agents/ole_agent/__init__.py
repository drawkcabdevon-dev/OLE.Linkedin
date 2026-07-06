"""
OLE Content Agent — deployed to Vertex AI Agent Engine.

This module is loaded by the ADK CLI during `adk deploy agent_engine`.
It must export `root_agent` as the root LlmAgent.
"""

from .agent import agent as root_agent

__all__ = ["root_agent"]
