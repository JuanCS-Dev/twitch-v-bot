import asyncio
from openai import AsyncOpenAI
from bot.bootstrap_runtime import get_secret

NEBIUS_MODEL_DEFAULT = "moonshotai/Kimi-K2.5"

async def test_all_models():
    api_key = get_secret("NEBIUS_API_KEY")
    client = AsyncOpenAI(
        base_url="https://api.studio.nebius.ai/v1/",
        api_key=api_key,
    )
    
    print(f"=== TEST 1: LOGIC / DEFAULT ({NEBIUS_MODEL_DEFAULT}) ===")
    res_logic = await client.chat.completions.create(
        model=NEBIUS_MODEL_DEFAULT,
        messages=[{"role": "user", "content": "Em uma frase, qual a vantagem da arquitetura MoE em LLMs?"}],
        max_tokens=600
    )
    print(getattr(res_logic.choices[0].message, "content", None) or res_logic.choices[0].message)

asyncio.run(test_all_models())
