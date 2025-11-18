#!/usr/bin/env python3
"""
Retrieve CloudWatch logs for Bedrock AgentCore agent.

This script retrieves logs from CloudWatch for the deployed agent,
with options to follow logs in real-time and filter by time range.
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _load_deployment_metadata(script_dir: Path) -> dict:
    """Load deployment metadata from .deployment_metadata.json file."""
    metadata_file = script_dir / ".deployment_metadata.json"
    if metadata_file.exists():
        try:
            return json.loads(metadata_file.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _get_cw_logs(
    agent_id: str,
    region: str,
    time_range: str,
    follow: bool,
    filter_pattern: str = "",
) -> None:
    """
    Retrieve CloudWatch logs for the agent.

    Args:
        agent_id: The agent ID
        region: AWS region
        time_range: Time range for logs (e.g., '15m', '1h', '2h', '1d')
        follow: Whether to follow logs in real-time
        filter_pattern: Optional filter pattern for logs
    """
    log_group = f"/aws/bedrock-agentcore/runtimes/{agent_id}-DEFAULT"

    logger.info("=" * 70)
    logger.info("CLOUDWATCH LOGS FOR AGENT")
    logger.info("=" * 70)
    logger.info(f"Agent ID: {agent_id}")
    logger.info(f"Log Group: {log_group}")
    logger.info(f"Region: {region}")
    logger.info(f"Time Range: {time_range}")
    if filter_pattern:
        logger.info(f"Filter Pattern: {filter_pattern}")
    logger.info("=" * 70)
    logger.info("")

    # Build AWS CLI command
    cmd = [
        "aws",
        "logs",
        "tail",
        log_group,
        "--since",
        time_range,
        "--region",
        region,
    ]

    if filter_pattern:
        cmd.extend(["--filter-pattern", filter_pattern])

    if follow:
        cmd.append("--follow")

    logger.info(f"Running: {' '.join(cmd)}")
    logger.info("")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to retrieve logs: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Log retrieval interrupted by user")
        sys.exit(0)


def main() -> None:
    """Main entry point for getting CloudWatch logs."""
    parser = argparse.ArgumentParser(
        description="Get CloudWatch logs for Bedrock AgentCore agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Get last 15 minutes of logs
    uv run python scripts/get_cw_logs.py

    # Follow logs in real-time
    uv run python scripts/get_cw_logs.py --follow

    # Get last hour of logs
    uv run python scripts/get_cw_logs.py --time 1h

    # Get logs and filter for errors only
    uv run python scripts/get_cw_logs.py --time 1h --filter ERROR

    # Use specific agent ID instead of deployment metadata
    uv run python scripts/get_cw_logs.py --agent-id my-agent-id --region us-west-2

Environment variables:
    AWS_REGION: AWS region (if --region not specified)
""",
    )

    parser.add_argument(
        "--agent-id",
        default=None,
        help="Agent ID (default: reads from .deployment_metadata.json)",
    )

    parser.add_argument(
        "--region",
        default=None,
        help="AWS region (default: reads from .deployment_metadata.json or AWS_REGION env var)",
    )

    parser.add_argument(
        "--time",
        default="15m",
        help="Time range for logs (default: 15m). Examples: 15m, 1h, 2h, 1d",
    )

    parser.add_argument(
        "--follow",
        action="store_true",
        help="Follow logs in real-time",
    )

    parser.add_argument(
        "--filter",
        default="",
        help="Filter pattern for logs (e.g., 'ERROR', 'WARN')",
    )

    args = parser.parse_args()

    # Get script directory
    script_dir = Path(__file__).parent

    # Load deployment metadata if agent ID not provided
    if not args.agent_id:
        metadata = _load_deployment_metadata(script_dir)
        if not metadata:
            logger.error("No deployment metadata found at .deployment_metadata.json")
            logger.error("Specify --agent-id or ensure .deployment_metadata.json exists")
            sys.exit(1)

        agent_id = metadata.get("agent_id")
        if not agent_id:
            logger.error("No agent_id found in deployment metadata")
            sys.exit(1)
    else:
        agent_id = args.agent_id

    # Get region
    if args.region:
        region = args.region
    else:
        metadata = _load_deployment_metadata(script_dir) if not args.agent_id else {}
        region = metadata.get("region") or __import__("os").environ.get("AWS_REGION")

    if not region:
        logger.error("No region specified")
        logger.error(
            "Specify --region, ensure .deployment_metadata.json contains 'region', or set AWS_REGION env var"
        )
        sys.exit(1)

    # Get logs
    try:
        _get_cw_logs(
            agent_id=agent_id,
            region=region,
            time_range=args.time,
            follow=args.follow,
            filter_pattern=args.filter,
        )
    except Exception as e:
        logger.error(f"Failed to get logs: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
