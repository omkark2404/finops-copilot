"""One opt-in paid-provider smoke call using fixed non-sensitive aggregate evidence."""

import argparse
import asyncio
import json
import os
from pathlib import Path


async def verify():
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError(
            "GEMINI_API_KEY must be configured through a secret environment variable"
        )
    # These settings are only for this CLI, which never starts a server.
    os.environ.setdefault("JWT_SECRET_KEY", "provider-smoke-only-not-a-server-secret")
    os.environ.setdefault("ADMIN_PASSWORD", "provider-smoke-only-not-a-server-password")
    from app.agents import GeminiProvider
    from app.config import get_settings

    settings = get_settings()
    provider = GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    try:
        output = await provider.explain(
            {"total_cost": 100, "total_rows": 2},
            "Explain the supplied total cost and row count in one short sentence.",
        )
        if provider.degraded or not output.strip() or output.startswith("[Offline"):
            raise RuntimeError(
                "Live provider verification failed; inspect provider availability, model, quotas and grounding"
            )
        return {
            "provider": provider.name,
            "live_response_verified": True,
            "usage": provider.usage,
            "evidence": "Fixed non-sensitive aggregates only; no customer data",
        }
    finally:
        await provider.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(verify())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print("Live Gemini smoke call passed; inspect usage and reconcile provider billing separately")


if __name__ == "__main__":
    main()
