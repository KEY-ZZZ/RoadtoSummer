import os
from pathlib import Path

ROOT = Path(__file__).parent.parent

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

EXERCISE_LIBRARY_PATH = ROOT / "exercise_library.json"
MATCHING_LOGIC_PATH = ROOT / "matching_logic.json"
DB_PATH = ROOT / "data" / "fitness_bot.db"

CLAUDE_MODEL = "claude-haiku-4-5-20251001"
