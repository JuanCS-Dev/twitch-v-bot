import unittest

from bot.tests.scientific.suite_current_events_normalizer import (
    ScientificCurrentEventsNormalizerTestsMixin,
)
from bot.tests.scientific.suite_http import ScientificHttpTestsMixin
from bot.tests.scientific.suite_hud import ScientificHudTestsMixin
from bot.tests.scientific.suite_e2e_macaco import ScientificMacacoModeTestsMixin
from bot.tests.scientific.suite_irc_control import ScientificIrcControlTestsMixin
from bot.tests.scientific.suite_prompt_core import ScientificPromptCoreTestsMixin
from bot.tests.scientific.suite_prompt_runtime_flow import (
    ScientificPromptRuntimeFlowTestsMixin,
)
from bot.tests.scientific.suite_quality_detection import (
    ScientificQualityDetectionTestsMixin,
)
from bot.tests.scientific.suite_recap import ScientificRecapTestsMixin
from bot.tests.scientific.suite_scene_irc import ScientificSceneAndIrcTestsMixin
from bot.tests.scientific.suite_sentiment import ScientificSentimentTestsMixin
from bot.tests.scientific.suite_tokens import ScientificTokenAndBootstrapTestsMixin
from bot.tests.scientific.suite_vision import ScientificVisionTestsMixin
from bot.tests.scientific_shared import ScientificTestCase


class TestBotProduction90Plus(
    ScientificHttpTestsMixin,
    ScientificHudTestsMixin,
    ScientificMacacoModeTestsMixin,
    ScientificPromptCoreTestsMixin,
    ScientificQualityDetectionTestsMixin,
    ScientificCurrentEventsNormalizerTestsMixin,
    ScientificPromptRuntimeFlowTestsMixin,
    ScientificRecapTestsMixin,
    ScientificSceneAndIrcTestsMixin,
    ScientificSentimentTestsMixin,
    ScientificIrcControlTestsMixin,
    ScientificTokenAndBootstrapTestsMixin,
    ScientificVisionTestsMixin,
    ScientificTestCase,
):
    pass


if __name__ == "__main__":
    unittest.main()
