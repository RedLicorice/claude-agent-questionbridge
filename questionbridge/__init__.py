"""QuestionBridge — Telegram bot + REST API bridge for Claude to ask the owner questions."""

__version__ = "0.1.0"


def start() -> None:
    """Entry point for `questionbridge start` / `poetry run start`."""
    from .main import run
    run()


def init() -> None:
    """Entry point for `questionbridge init` — copies settings.example.yaml to CWD."""
    import importlib.resources
    import shutil
    from pathlib import Path

    dest = Path("settings.local.yaml")
    if dest.exists():
        print(f"{dest} already exists — not overwriting.")
        return

    source = importlib.resources.files("questionbridge").joinpath("settings.example.yaml")
    with importlib.resources.as_file(source) as src:
        shutil.copy(src, dest)

    print(f"Created {dest} — fill in your BOT_TOKEN and OWNER_CHAT_ID, then run `questionbridge start`.")
