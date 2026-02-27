import re

from bot.byte_semantics import format_chat_reply
from bot.logic import MAX_REPLY_LENGTH, MAX_REPLY_LINES, agent_inference, context_manager
from bot.observability import observability
from bot.runtime_config import ENABLE_LIVE_CONTEXT_LEARNING, client, logger
from bot.sentiment_engine import sentiment_engine

RECAP_PATTERNS = re.compile(
    r"(?i)"
    r"(?:o que (?:ta|est[aá]) (?:rolando|acontecendo))"
    r"|(?:cheguei agora)"
    r"|(?:resumo|resume)"
    r"|(?:what.?s happening)"
    r"|(?:what did i miss)"
    r"|(?:me conta)"
    r"|(?:poe.?me.?a.?par)"
)

RECAP_PROMPT_TEMPLATE = (
    "Modo recap para novo viewer no chat da Twitch.\n"
    "Contexto ao vivo:\n"
    "{context}\n"
    "Sentimento: {vibe}\n"
    "Historico recente: {recent_chat}\n"
    "Tarefa: Resuma em 2-3 frases curtas o que esta acontecendo na live agora. "
    "Inclua: o que esta sendo jogado/assistido, clima do chat, e qualquer evento "
    "interessante. Nao use markdown. PT-BR natural."
)


def is_recap_prompt(text: str) -> bool:
    return bool(RECAP_PATTERNS.search(text))


async def generate_recap(channel_id: str | None = None) -> str:
    ctx = context_manager.get(channel_id)
    obs_text = ctx.format_observability()
    vibe = sentiment_engine.get_vibe(channel_id or "default")
    recent = ctx.format_recent_chat(limit=8)
    prompt = RECAP_PROMPT_TEMPLATE.format(
        context=obs_text,
        vibe=vibe,
        recent_chat=recent,
    )
    try:
        answer = await agent_inference(
            prompt,
            "recap",
            client,
            ctx,
            enable_live_context=ENABLE_LIVE_CONTEXT_LEARNING,
            max_lines=MAX_REPLY_LINES,
            max_length=MAX_REPLY_LENGTH,
        )
        safe = format_chat_reply(str(answer or ""))
        return safe.strip() or "Sem contexto suficiente pra recap agora."
    except Exception as error:
        logger.error("Recap generation error: %s", error)
        observability.record_error(category="recap", details=str(error), channel_id=channel_id)
        return "Sem contexto suficiente pra recap agora."


__all__ = ["generate_recap", "is_recap_prompt"]
