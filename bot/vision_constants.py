
VISION_MAX_FRAME_BYTES = 20 * 1024 * 1024  # 20 MB (limite inline_data)
VISION_MIN_INTERVAL_SECONDS = 5.0
VISION_CLIP_KEYWORDS = frozenset({
    "victory", "vitoria", "win",
    "death", "morte", "morreu",
    "pentakill", "penta",
    "clutch", "ace",
    "explosion", "explosao",
    "goal", "gol",
    "save", "defesa",
    "epic", "epico",
    "highlight", "destaque",
})

VISION_SCENE_PROMPT = (
    "Voce e um assistente de stream ao vivo de jogos na Twitch. "
    "Analise esta captura de tela e descreva em 1-2 frases curtas: "
    "1) O que esta acontecendo na cena (jogo, menu, tela de loading, etc). "
    "2) Se ha algum momento memoravel ou digno de clip (vitoria, morte epica, "
    "pentakill, jogada clutch, explosao, gol). "
    "Se nao houver nada relevante, diga apenas 'CENA_NORMAL'. "
    "Responda em PT-BR, sem markdown."
)
