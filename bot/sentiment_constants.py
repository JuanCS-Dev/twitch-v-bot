SENTIMENT_WINDOW_SECONDS = 60.0
SENTIMENT_MAX_EVENTS = 500

ANTI_BOREDOM_THRESHOLD = 0.20  # hype < 20% por 5 minutos
ANTI_BOREDOM_WINDOW_SECONDS = 300.0
ANTI_CONFUSION_THRESHOLD = 0.70  # confusao > 70%

# Score: positivo = hype/diversao, negativo = tristeza/confusao
# Valores entre -2 e +2
EMOTE_SCORES: dict[str, float] = {
    # Hype / diversao
    "PogChamp": 2.0,
    "Pog": 2.0,
    "POGGERS": 2.0,
    "PogU": 2.0,
    "KEKW": 1.5,
    "LUL": 1.0,
    "LULW": 1.0,
    "OMEGALUL": 1.5,
    "EZ": 1.0,
    "Clap": 1.0,
    "catJAM": 1.0,
    "PogBones": 1.5,
    "HYPERS": 2.0,
    "peepoHappy": 1.0,
    "widepeepoHappy": 1.5,
    "FeelsGoodMan": 1.0,
    "LETS": 1.5,
    "LETSGO": 1.5,
    "GG": 1.0,
    # Tristeza / frustração
    "BibleThump": -1.0,
    "Sadge": -1.5,
    "PepeHands": -1.5,
    "FeelsBadMan": -1.0,
    "sadCat": -1.0,
    "widepeepoSad": -1.5,
    "NotLikeThis": -1.0,
    "F": -0.5,
    # Confusao
    "???": -1.0,
    "monkaHmm": -1.0,
    "Pepega": -1.0,
    "WHAT": -1.0,
    "HUH": -1.0,
    "Jebaited": -0.5,
    "Clueless": -1.0,
    "Hmm": -0.5,
}

KEYWORD_SCORES: dict[str, float] = {
    "gg": 1.0,
    "ggwp": 1.0,
    "lol": 0.5,
    "haha": 0.5,
    "kkkk": 0.5,
    "rsrs": 0.5,
    "nice": 0.5,
    "incrivel": 1.0,
    "epico": 1.0,
    "top": 0.5,
    "massa": 0.5,
    "ruim": -0.5,
    "chato": -1.0,
    "boring": -1.0,
    "tedioso": -1.0,
    "confuso": -1.0,
    "nao entendi": -1.0,
    "hein": -0.5,
    "wtf": -0.5,
}

VIBE_THRESHOLDS: list[tuple[float, str]] = [
    (1.5, "Hyped"),
    (0.5, "Divertido"),
    (-0.3, "Chill"),
    (-1.0, "Confuso"),
]
VIBE_DEFAULT = "Triste"
