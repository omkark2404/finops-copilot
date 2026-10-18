"""Alembic migration entry point; also used by application bootstrap."""

from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade():
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(config, "head")


if __name__ == "__main__":
    upgrade()
