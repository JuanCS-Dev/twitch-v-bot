import asyncio
import os
import sys

os.environ["SUPABASE_DB_URL"] = "postgresql://postgres:publishable_JRJtYCVcSy3PClI1hYtjcw_szReuxRB@db.utnmldsouwprgstzvszj.supabase.co:5432/postgres"

from bot.bootstrap_runtime import get_secret
from bot.logic_inference import agent_inference

# This script actually hits the Nebius API to validate the model runs
async def test_real_llm():
    # Force client generation from env to bypass mock boundaries if any
    try:
        api_key = get_secret("NEBIUS_API_KEY")
    except RuntimeError:
        print("Missing NEBIUS_API_KEY. I need to ask the user!")
        sys.exit(1)

    print(f"Loaded NEBIUS_API_KEY. Length is: {len(api_key)}")
    print("Sending real prompt to Nebius...")

    from bot.logic import context as real_context
    from bot.runtime_config import client
    
    real_context.game = "Just Chatting"
    real_context.stream_vibe = "Chilling"

    response = await agent_inference(
        user_msg="Me responda com um poeminha curto, 4 linhas sobre piratas de silício!",
        author_name="test_operator",
        client=client,
        context=real_context,
        enable_grounding=False,
    )

    print("--- RESPONSE FROM NEBIUS ---")
    print(response)
    print("----------------------------")

    if not response or len(response) < 10:
        print("FAILED: Did not get a reasonable response")
        sys.exit(1)

    print("✅ LLM Connection Successful!")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(test_real_llm())
