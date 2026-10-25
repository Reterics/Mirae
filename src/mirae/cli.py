from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import cast

from mirae.config import ApiConfig, MiraeConfig, Profile, load_config
from mirae.pipeline.settings import load_managed_config


async def _serve(config: MiraeConfig, log_level: str) -> None:
    import uvicorn

    from mirae.api.app import create_app
    from mirae.robot import Robot

    config = await asyncio.to_thread(load_managed_config, config)
    robot = Robot(config)
    try:
        server = uvicorn.Server(
            uvicorn.Config(
                create_app(robot),
                host=config.api.host,
                port=config.api.port,
                log_level=log_level,
                timeout_graceful_shutdown=2,
                limit_concurrency=64,
            )
        )

        async def shutdown_on_failure() -> None:
            await robot.wait_failure()
            server.should_exit = True

        monitor = asyncio.create_task(shutdown_on_failure(), name="server-supervisor")
        try:
            await server.serve()
            if robot.fault:
                raise RuntimeError(robot.fault)
        finally:
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
    finally:
        await robot.stop()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mirae", description="Mirae robot runtime")
    parser.add_argument("--profile", choices=["local", "pi"], default="local")
    parser.add_argument("--config", help="TOML file merged over the profile (or $MIRAE_CONFIG)")
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="start the robot and its API")
    run.add_argument("--host", help="override api.host")
    run.add_argument("--port", type=int, help="override api.port")

    sub.add_parser("config", help="print the resolved configuration")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config(cast(Profile, args.profile), args.config)

    if args.command == "config":
        sys.stdout.write(config.model_dump_json(indent=2) + "\n")
        return 0

    api = config.api.model_dump()
    if args.host is not None:
        api["host"] = args.host
    if args.port is not None:
        api["port"] = args.port
    config = config.model_copy(update={"api": ApiConfig.model_validate(api)})
    try:
        asyncio.run(_serve(config, args.log_level.lower()))
    except (ValueError, OSError, RuntimeError):
        logging.getLogger(__name__).exception("Mirae failed")
        return 1
    return 0
