#!/usr/bin/env python3
"""
Delete AgentCore Runtime agent using bedrock-agentcore-starter-toolkit.

This script deletes a deployed agent from Amazon Bedrock AgentCore Runtime.
"""

import argparse
import logging
import sys
from pathlib import Path

# Configure logging with basicConfig
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _load_deployment_metadata(script_dir: Path) -> dict:
    """Load deployment metadata from .deployment_metadata.json file."""
    import json

    metadata_file = script_dir / ".deployment_metadata.json"
    if metadata_file.exists():
        try:
            return json.loads(metadata_file.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _delete_agent(
    agent_id: str,
    region: str,
) -> None:
    """
    Delete the agent from AgentCore Runtime.

    Note: The bedrock_agentcore_starter_toolkit's destroy() method is available
    in newer versions. This script provides cleanup guidance for the current
    version.

    Args:
        agent_id: The agent ID to delete
        region: AWS region
    """
    import os

    logger.info(f"Deleting agent: {agent_id}")
    logger.info(f"Region: {region}")

    logger.info("=" * 70)
    logger.info("AGENT DELETION GUIDANCE")
    logger.info("=" * 70)
    logger.info("")
    logger.info("STEP 1: DELETE AGENT FROM AGENTCORE UI")
    logger.info("-" * 70)
    logger.info("")
    logger.info("Delete the agent via AWS Bedrock AgentCore console:")
    logger.info(f"  Agent ID: {agent_id}")
    logger.info("")
    logger.info("Or use the destroy() method if available in your toolkit version:")
    logger.info("  from bedrock_agentcore_starter_toolkit import Runtime")
    logger.info("  runtime = Runtime()")
    logger.info("  runtime.destroy(dry_run=False, delete_ecr_repo=True)")
    logger.info("")
    logger.info("This will clean up:")
    logger.info("  - Agent runtime endpoint")
    logger.info("  - Memory resources")
    logger.info("  - Associated CloudFormation stacks")
    logger.info("")
    logger.info("STEP 2: CLEAN UP AWS RESOURCES (Manual cleanup if needed)")
    logger.info("-" * 70)
    logger.info("")
    logger.info("1. DELETE ECR REPOSITORY:")
    logger.info(f"   aws ecr delete-repository \\")
    logger.info(f"     --repository-name bedrock-agentcore-weather_time_observability_agent \\")
    logger.info(f"     --region {region} \\")
    logger.info(f"     --force")
    logger.info("")
    logger.info("2. DELETE CODEBUILD PROJECT:")
    logger.info(f"   aws codebuild delete-project \\")
    logger.info(f"     --name bedrock-agentcore-weather_time_observability_agent \\")
    logger.info(f"     --region {region}")
    logger.info("")
    logger.info("3. CLEAN UP CLOUDWATCH LOGS:")
    logger.info(f"   aws logs delete-log-group \\")
    logger.info(f"     --log-group-name /aws/codebuild/bedrock-agentcore-weather_time_observability_agent \\")
    logger.info(f"     --region {region}")
    logger.info("")
    logger.info("4. DELETE IAM ROLE (if custom role was created):")
    logger.info(f"   aws iam list-roles --query 'Roles[?contains(RoleName, `agentcore`)]'")
    logger.info(f"   aws iam delete-role --role-name <role-name>")
    logger.info("")
    logger.info("STEP 3: CLEAN UP LOCAL METADATA FILES")
    logger.info("-" * 70)
    logger.info("")
    logger.info("Deleting stale deployment metadata to allow fresh deployments...")

    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    metadata_file = script_dir / ".deployment_metadata.json"
    config_file = project_root / ".bedrock_agentcore.yaml"

    files_deleted = []

    if metadata_file.exists():
        os.remove(metadata_file)
        files_deleted.append(str(metadata_file))
        logger.info(f"  Deleted: {metadata_file.name}")

    if config_file.exists():
        os.remove(config_file)
        files_deleted.append(str(config_file))
        logger.info(f"  Deleted: {config_file.name}")

    logger.info("")
    if files_deleted:
        logger.info("Successfully cleaned up metadata files:")
        for file_path in files_deleted:
            logger.info(f"  - {file_path}")
    else:
        logger.info("No metadata files found to delete.")

    logger.info("")
    logger.info("STEP 4: REDEPLOY AGENT")
    logger.info("-" * 70)
    logger.info("")
    logger.info("After deleting the agent from the AgentCore UI, you can redeploy with:")
    logger.info("")
    logger.info("  uv run python scripts/deploy_agent.py \\")
    logger.info("    --braintrust-api-key <your-key> \\")
    logger.info("    --braintrust-project-id <your-project>")
    logger.info("")
    logger.info("The deployment will create a new agent with a fresh agent ID.")
    logger.info("")
    logger.info("=" * 70)


def main() -> None:
    """Main entry point for agent deletion."""
    parser = argparse.ArgumentParser(
        description="Delete AgentCore Runtime agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Delete agent (reads from .deployment_metadata.json automatically)
    uv run python scripts/delete_agent.py

    # Delete with explicit region
    uv run python scripts/delete_agent.py --region us-west-2

    # Delete specific agent ID
    uv run python scripts/delete_agent.py --agent-id my-agent-id --region us-east-1

Environment variables:
    AWS_REGION: AWS region (if --region not specified)
""",
    )

    parser.add_argument(
        "--region",
        default=None,
        help="AWS region (default: reads from .deployment_metadata.json or AWS_REGION env var)",
    )

    parser.add_argument(
        "--agent-id",
        default=None,
        help="Agent ID to delete (default: reads from .deployment_metadata.json)",
    )

    args = parser.parse_args()

    # Get script directory
    script_dir = Path(__file__).parent

    # Load deployment metadata
    metadata = _load_deployment_metadata(script_dir)

    # Get agent ID
    agent_id = args.agent_id or metadata.get("agent_id")
    if not agent_id:
        logger.error("No agent ID provided via --agent-id and .deployment_metadata.json not found")
        logger.error("Specify --agent-id or ensure .deployment_metadata.json exists")
        sys.exit(1)

    # Get region
    region = args.region or metadata.get("region") or __import__("os").environ.get("AWS_REGION")
    if not region:
        logger.error("No region specified")
        logger.error(
            "Specify --region, ensure .deployment_metadata.json contains 'region', or set AWS_REGION env var"
        )
        sys.exit(1)

    # Delete the agent
    try:
        _delete_agent(
            agent_id=agent_id,
            region=region,
        )
    except Exception as e:
        logger.error(f"Failed to delete agent: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
