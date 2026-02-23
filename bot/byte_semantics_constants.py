import os
import re

from bot.logic_constants import BOT_BRAND, MAX_REPLY_LINES

BYTE_TRIGGER = os.environ.get("BYTE_TRIGGER", BOT_BRAND).strip().lower() or "byte"
BYTE_HELP_MESSAGE = (
    "Byte entende chat natural. Acione com byte/@byte/!byte + pergunta. "
    "Atalhos: ajuda | se apresente | ficha tecnica <filme> | status. "
    "Dono (IRC): canais | join <canal> | part <canal>."
)
BYTE_TRIGGER_PATTERN = re.compile(rf"^\s*[@!]?(?:{re.escape(BYTE_TRIGGER)})\b[\s,:-]*(.*)$", re.IGNORECASE)
MOVIE_FACT_SHEET_PATTERN = re.compile(r"ficha\s*t[eé]cnica", re.IGNORECASE)
MOVIE_TITLE_QUOTE_PATTERN = re.compile(r"[\"'`](?P<title>[^\"'`]{2,120})[\"'`]")
CURRENT_EVENTS_HINT_TERMS = (
    "situacao atual", "situação atual", "como esta", "como está", "atualizacao", "atualização", "agora", "hoje",
    "nesta semana", "nessa semana", "esta semana", "ultima semana", "última semana", "ultimos dias", "últimos dias",
    "noticias", "notícias", "recente", "recentes", "agora mesmo", "tempo real", "breaking", "update", "updates",
    "anunciou", "anunciaram", "novidade", "ultimo anuncio", "último anúncio", "lancamento", "lançamento",
)
HIGH_RISK_CURRENT_EVENTS_TERMS = (
    "situacao atual", "situação atual", "agora", "hoje", "nesta semana", "nessa semana", "esta semana",
    "ultima semana", "última semana", "ultimos dias", "últimos dias", "noticias", "notícias", "breaking",
    "update", "updates", "anunciou", "anunciaram",
)
GENERIC_RESPONSE_HINT_TERMS = (
    "depende", "pode variar", "em geral", "de forma geral", "geralmente", "na maioria dos casos",
    "vale lembrar", "e importante lembrar", "por outro lado", "cada caso e um caso",
)
OVERCONFIDENT_HINT_TERMS = ("com certeza", "sem duvida", "definitivamente", "garantido", "sempre")
UNCERTAINTY_HINT_TERMS = (
    "nao consegui verificar", "não consegui verificar", "sem confirmacao", "sem confirmação", "sem confirmar", "incerto",
    "nao ha confirmacao", "não há confirmação", "pode estar desatualizado", "baixa confianca", "baixa confiança",
    "conexao com o modelo instavel", "conexão com o modelo instável",
)
TEMPORAL_ANCHOR_TERMS = (
    "hoje", "agora", "atualmente", "ate o momento", "até o momento", "nesta semana", "neste momento",
    "semana", "mes", "mês", "2025", "2026",
)
SOURCE_ANCHOR_TERMS = (
    "segundo ", "de acordo com", "fonte:", "fontes:", "base:", "reportado por", "confirmado por",
    "comunicado de", "anvisa", "ministerio", "ministério", "governo", "reuters", "bbc", "ap news",
)
CONFIDENCE_LABEL_TERMS = ("confianca:", "confiança:")
QUALITY_STOPWORDS = {
    "byte", "qual", "quais", "como", "onde", "quando", "quem", "porque", "por", "que", "isso", "esse", "essa",
    "agora", "hoje", "sobre", "para", "com", "sem", "uma", "um", "uns", "umas", "dos", "das", "de", "do", "da",
    "the", "and", "tem", "existe", "fala", "diz",
}
FOLLOW_UP_HINT_TERMS = (
    "e agora", "e ai", "e aí", "e ele", "e ela", "e isso", "e esse", "e essa", "sobre isso", "sobre ele", "sobre ela",
    "detalha isso", "resume isso", "resuma isso",
)
BRIEF_STYLE_TERMS = ("resuma", "resumo", "curto", "curta", "1 linha", "uma linha", "tl;dr", "tldr")
ANALYTICAL_STYLE_TERMS = ("detalha", "aprofunda", "analisa", "compare", "comparar", "vs", "diferen", "prons", "contras")
PLAYFUL_STYLE_TERMS = ("zoa", "zoeira", "meme", "engracad", "brinca", "tirada")
QUESTION_OPENING_TERMS = (
    "existe", "tem", "ha", "há", "qual", "quais", "como", "porque", "por que", "onde", "quando", "quem", "pode", "vale",
    "compensa", "recomenda", "recomendacao", "recomendação", "indica",
)
EXISTENCE_QUESTION_TERMS = ("existe", "tem", "ha", "há")
RECOMMENDATION_HINT_TERMS = ("recomenda", "recomendacao", "recomendação", "indica", "sugere", "lista", "melhores")
SERIOUS_TECH_TERMS = (
    "laminina", "parapleg", "medicina", "saude", "tratamento", "terapia", "pesquisa", "estudo", "cient", "neurolog",
    "biolog", "genet", "clinico", "evidencia", "paper",
)
COMPLEX_TECH_HINT_TERMS = (
    "como funciona", "mecanismo", "explica tecnicamente", "base cientifica", "protocolo", "metodologia", "efeitos", "riscos", "limites",
)
RELEVANCE_HINT_TERMS = ("relevante", "impacto", "hoje", "agora", "atual", "urgente", "importante", "cura")
MAX_CHAT_MESSAGE_LENGTH = 460
MULTIPART_SEPARATOR = "[BYTE_SPLIT]"
SERIOUS_REPLY_MAX_LINES = MAX_REPLY_LINES
SERIOUS_REPLY_MAX_LENGTH = MAX_CHAT_MESSAGE_LENGTH
QUALITY_SAFE_FALLBACK = "Nao consegui verificar com confianca agora. Me manda 1 link/fonte no chat e eu resumo em ate 3 linhas."
CURRENT_EVENTS_DEFAULT_SOURCE = "Fonte: pesquisa web em tempo real (DuckDuckGo)."
CURRENT_EVENTS_PENDING_SOURCE = "Fonte: aguardando 1 link/fonte do chat para confirmar."
REWRITE_REASON_GUIDANCE = {
    "resposta_generica": "Troque generalidades por fatos especificos ligados ao pedido do usuario.",
    "abertura_generica": "Comece respondendo direto a pergunta principal, sem 'depende' ou introducoes vagas.",
    "resposta_curta_sem_substancia": "Adicione 1 ou 2 detalhes concretos (nome, data, local, obra ou numero).",
    "off_topic": "Retorne ao objeto central da pergunta e remova desvios.",
    "tema_atual_sem_ancora_temporal": "Inclua ancora temporal objetiva baseada no horario do servidor (hoje/nesta semana/mes-ano).",
    "tema_atual_sem_confianca_explicita": "Inclua a linha final 'Confianca: alta|media|baixa'.",
    "tema_atual_sem_base_verificavel": "Inclua a linha final 'Fonte: <origem confiavel>' quando houver afirmacao atual.",
    "incerteza_sem_pedido_de_fonte": "Se houver incerteza, solicite 1 link/fonte para confirmar.",
    "incerteza_fora_fallback_canonico": "Para tema atual de alto risco com incerteza, use apenas fallback canonico sem especulacao extra.",
    "modelo_indisponivel": "Se o modelo estiver instavel/indisponivel, use fallback seguro pedindo 1 fonte do chat.",
    "resposta_existencia_sem_posicao": "Em pergunta de existencia, comece com 'Sim,' ou 'Nao,'.",
    "termina_com_pergunta_aberta": "Finalize com afirmacao objetiva; so faca pergunta se faltar dado essencial.",
    "confianca_absoluta_sem_base": "Evite tom absoluto sem base verificavel; sinalize limite de confianca.",
}
BYTE_INTRO_TEMPLATES = (
    "Sou Byte: IA premium da live. Latencia baixa, cerebro afiado e zoeira calibrada. Digita 'byte ajuda'.",
    "Byte on. Modo high-tech + caos controlado: resposta rapida, precisa e sem textao. Usa 'byte ajuda'.",
    "Copiloto oficial do chat: contexto em tempo real, ficha tecnica na veia e humor fino. Manda 'byte ajuda'.",
    "Byte na pista. Se a pergunta vier torta, eu devolvo reta com classe e zoeira. Comandos em 'byte ajuda'.",
)
