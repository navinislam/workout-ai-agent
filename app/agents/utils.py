"""
Agent Utilities
---------------
Shared utilities for working with Agents SDK in FastAPI context.
"""

import asyncio
from agents import Agent, Runner, RunResult


def run_agent_sync(agent: Agent, input: str) -> RunResult:
    """Run agent synchronously, handling thread pool execution (no event loop).

    This is needed because FastAPI runs sync endpoints in a thread pool where
    there's no event loop, but Runner.run_sync() needs one.

    Args:
        agent: The agent to run
        input: The input prompt/message

    Returns:
        RunResult from the agent execution
    """
    try:
        # Try normal sync execution first
        return Runner.run_sync(agent, input=input)
    except RuntimeError as e:
        if "no current event loop" in str(e).lower():
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return Runner.run_sync(agent, input=input)
            finally:
                loop.close()
                asyncio.set_event_loop(None)
        else:
            raise
