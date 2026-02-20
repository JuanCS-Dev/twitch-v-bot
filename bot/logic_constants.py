import os

BOT_BRAND = "Byte"
MAX_REPLY_LINES = 8
MAX_REPLY_LENGTH = 460
MAX_RECENT_CHAT_ENTRIES = 12
MAX_RECENT_CHAT_PREVIEW_CHARS = 140
MAX_RECENT_CHAT_PROMPT_ENTRIES = 5
MAX_GROUNDING_QUERIES = 3
MAX_GROUNDING_URLS = 3

OBSERVABILITY_TYPES = {
    "game": "Jogo",
    "movie": "Filme",
    "series": "Serie",
    "youtube": "Video YouTube",
    "x": "Post X",
    "topic": "Tema",
}

DEFAULT_STYLE_PROFILE = "Tom generalista, claro e natural em PT-BR, sem giria gamer forcada."

SYSTEM_INSTRUCTION_TEMPLATE = (
    "Voce e Byte, chatbot de uma live na Twitch. "
    "Responda de forma objetiva para os assuntos ativos da live, incluindo jogos, filmes, series, videos do YouTube, posts do X e temas gerais. "
    "Regras: 1) no maximo 8 linhas. 2) frases curtas e informativas. "
    "3) sem markdown. 4) nao use linguagem ofensiva nem invente fatos sem sinalizar incerteza. "
    "5) se faltar contexto essencial, faca uma pergunta curta. "
    "6) para assunto atual, priorize informacao recente e verificavel. "
    "7) responda primeiro a pergunta principal, sem rodeio."
)
MODEL_NAME = "gemini-3-flash-preview"
MODEL_MAX_OUTPUT_TOKENS = 320
MODEL_TEMPERATURE = 0.15
MODEL_RATE_LIMIT_MAX_RETRIES = max(0, int(os.environ.get("MODEL_RATE_LIMIT_MAX_RETRIES", "1")))
MODEL_RATE_LIMIT_BACKOFF_SECONDS = max(0.0, float(os.environ.get("MODEL_RATE_LIMIT_BACKOFF_SECONDS", "0.8")))
EMPTY_RESPONSE_FALLBACK = "Nao consegui consolidar a resposta agora. Tente reformular em uma frase."
UNSTABLE_CONNECTION_FALLBACK = "Conexao com o modelo instavel. Tente novamente em instantes."
