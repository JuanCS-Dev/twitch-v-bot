# test_resiliency.py
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

load_dotenv()

# Verificamos que o import do runtime_config nao quebra mais sem chave
def test_startup_resiliency():
    print("--- ByteBot Resiliency Test (Startup) ---")
    # Garantimos que a chave esta limpa
    env_patch = patch.dict(os.environ, {"GOOGLE_API_KEY": ""})
    env_patch.start()
    
    try:
        from bot import runtime_config
        # Re-import ou refresh para garantir que as variaveis globais sejam testadas
        import importlib
        importlib.reload(runtime_config)
        
        print("✅ SUCCESS: runtime_config imported without crashing.")
        
        if not hasattr(runtime_config, "client"):
            print("✅ SUCCESS: Google client is gone.")
            
    except Exception as e:
        print(f"❌ FAILED: Startup crashed: {str(e)}")
        sys.exit(1)
    finally:
        env_patch.stop()

async def test_inference_resiliency():
    print("\n--- ByteBot Resiliency Test (Inference Guard) ---")
    from bot.logic_inference import agent_inference
    
    # Mocking dependencies
    mock_context = MagicMock()
    mock_client = MagicMock()
    # Testamos inferencia com client mockado falhando (simulando instabilidade)
    mock_client.chat.completions.create.side_effect = Exception("401 Unauthorized")
    result = await agent_inference(
        user_msg="ola",
        author_name="user",
        client=mock_client,
        context=mock_context
    )
    
    if "Conexao com o modelo instavel" in str(result) or "Serviço temporariamente instável" in str(result):
        print("✅ SUCCESS: agent_inference handled None client gracefully.")
    else:
        print(f"❌ FAILED: agent_inference returned unexpected result: {result}")
        sys.exit(1)

if __name__ == "__main__":
    test_startup_resiliency()
    import asyncio
    asyncio.run(test_inference_resiliency())
    print("\n✅ ALL RESILIENCY TESTS PASSED.")
    sys.exit(0)
