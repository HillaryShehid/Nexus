"""Run the modular LiveKit voice interface for Personal Nexus.

This process is separate from web_server.py. LiveKit provides the realtime
audio/turn-taking layer while NexusCore remains the authoritative brain.
"""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from src.core import NexusCore
from src.voice_livekit import LiveKitVoiceConfig, build_livekit_models

load_dotenv()


def build_agent():
    from livekit import agents
    from livekit.agents import Agent, RunContext, function_tool

    nexus = NexusCore(actor_id="hilal")

    class NexusVoiceAgent(Agent):
        def __init__(self) -> None:
            super().__init__(
                instructions=(
                    "You are the realtime voice interface for Nexus, a unified "
                    "personal AI assistant. Be warm, natural, confident, concise, "
                    "and conversational. Use light humor when it fits. Do not "
                    "invent facts or claim actions happened. For substantive "
                    "requests, call the nexus_core tool and treat its result as "
                    "the authoritative Nexus answer. You are the voice interface, "
                    "not a second independent brain."
                )
            )

        @function_tool()
        async def nexus_core(self, context: RunContext, request: str) -> str:
            """Send the owner's substantive request through the full Nexus brain.

            Args:
                request: The owner's complete request.
            """
            request = str(request or "").strip()
            if not request:
                return "I need a little more detail before I can help."

            result = await asyncio.to_thread(nexus.handle_request, request)
            if isinstance(result, dict):
                result = result.get("response", result)
            return str(result)

    return agents.AgentServer(), NexusVoiceAgent(), nexus


server, voice_agent, nexus = build_agent()


@server.rtc_session(agent_name=os.getenv("NEXUS_LIVEKIT_AGENT_NAME", "nexus"))
async def nexus_voice(ctx):
    from livekit.agents import AgentSession

    config = LiveKitVoiceConfig()
    vad, stt, llm, tts = build_livekit_models(config)

    session = AgentSession(
        stt=stt,
        llm=llm,
        tts=tts,
        vad=vad,
        max_tool_steps=3,
    )

    await session.start(room=ctx.room, agent=voice_agent)
    await session.generate_reply(
        instructions="Greet the owner briefly and say you are ready."
    )


if __name__ == "__main__":
    from livekit import agents

    agents.cli.run_app(server)
