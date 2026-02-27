from bot.observability_state import ObservabilityState
from bot.persistence_layer import persistence

observability = ObservabilityState(persistence_layer=persistence)

__all__ = ["ObservabilityState", "observability"]
