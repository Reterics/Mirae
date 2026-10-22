from __future__ import annotations

import argparse
import logging
import sys
from typing import cast

from mirae.config import Profile, load_config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mirae", description="Mirae robot runtime")
    parser.add_argument("--profile", choices=["sim", "pi"], default="sim")
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

    import uvicorn

    from mirae.api.app import create_app
    from mirae.robot import Robot

    app = create_app(Robot(config))
    uvicorn.run(
        app,
        host=args.host or config.api.host,
        port=args.port or config.api.port,
        log_level=args.log_level.lower(),
    )
    return 0
