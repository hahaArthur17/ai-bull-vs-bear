from __future__ import annotations

import asyncio

from app.main import build_configured_debate_worker, settings


async def run_worker() -> None:
    if not settings.debate_queue_enabled:
        raise RuntimeError("Set DEBATE_QUEUE_ENABLED=true to run the Debate Worker")
    stop_event = asyncio.Event()
    workers = [
        build_configured_debate_worker()
        for _ in range(settings.debate_worker_concurrency)
    ]
    async with asyncio.TaskGroup() as group:
        for worker in workers:
            group.create_task(
                worker.run_forever(
                    stop_event,
                    poll_seconds=settings.debate_worker_poll_seconds,
                )
            )


def main() -> None:
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
