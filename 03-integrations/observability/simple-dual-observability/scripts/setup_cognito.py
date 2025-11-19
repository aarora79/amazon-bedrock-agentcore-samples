"""Setup Amazon Cognito OAuth for AgentCore Gateway.

This script creates an Amazon Cognito User Pool and App Client for authenticating
requests to the AgentCore Gateway. It uses the bedrock_agentcore_starter_toolkit
to simplify the Cognito setup process.

The script performs the following operations:
1. Creates a Cognito User Pool with OAuth configuration
2. Creates an App Client with appropriate settings
3. Retrieves access token for testing
4. Saves configuration to .cognito_config.json for use by other scripts

Environment Variables Required:
    AWS_REGION: AWS region for Cognito deployment (default: us-west-2)

Environment Variables Created:
    COGNITO_USERPOOL_ID: Amazon Cognito User Pool ID
    COGNITO_CLIENT_ID: OAuth client ID
    COGNITO_CLIENT_SECRET: OAuth client secret
    COGNITO_DOMAIN: Cognito domain prefix
    COGNITO_DISCOVERY_URL: OIDC discovery endpoint
    COGNITO_ACCESS_TOKEN: Access token for testing

Example Usage:
    python scripts/setup_cognito.py --region us-west-2
"""

import argparse
import json
import logging
import os
from pathlib import Path

from bedrock_agentcore_starter_toolkit.operations.gateway import GatewayClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _setup_cognito(
    region: str,
    cognito_name: str,
) -> dict:
    """Setup Cognito OAuth authorizer.

    Args:
        region: AWS region
        cognito_name: Name for the Cognito User Pool

    Returns:
        Dictionary containing Cognito configuration
    """
    logger.info(f"Creating Cognito OAuth authorizer: {cognito_name}")

    # Create GatewayClient
    client = GatewayClient(region_name=region)

    # Create Cognito authorizer (this creates User Pool, App Client, and Domain)
    cognito_result = client.create_oauth_authorizer_with_cognito(cognito_name)

    # Extract configuration
    client_info = cognito_result["client_info"]
    authorizer_config = cognito_result["authorizer_config"]

    logger.info(f"Cognito User Pool ID: {client_info['user_pool_id']}")
    logger.info(f"Cognito Client ID: {client_info['client_id']}")
    logger.info(f"Cognito Domain: {client_info['domain_prefix']}")
    logger.info(f"Discovery URL: {authorizer_config['customJWTAuthorizer']['discoveryUrl']}")

    # Get access token for testing
    logger.info("Retrieving OAuth access token...")
    try:
        token = client.get_access_token_for_cognito(client_info)
        logger.info(f"Access Token: {token[:20]}...")
    except Exception as e:
        logger.warning(f"Could not retrieve access token: {e}")
        token = None

    return {
        "user_pool_id": client_info["user_pool_id"],
        "client_id": client_info["client_id"],
        "client_secret": client_info["client_secret"],
        "domain_prefix": client_info["domain_prefix"],
        "region": client_info.get("region", region),
        "discovery_url": authorizer_config["customJWTAuthorizer"]["discoveryUrl"],
        "allowed_clients": authorizer_config["customJWTAuthorizer"].get("allowedClients", []),
        "access_token": token,
    }


def _save_cognito_config(
    config_file: Path,
    cognito_config: dict,
) -> None:
    """Save Cognito configuration to JSON file.

    Args:
        config_file: Path to configuration file
        cognito_config: Cognito configuration dictionary
    """
    with open(config_file, "w") as f:
        json.dump(cognito_config, f, indent=2, default=str)

    logger.info(f"Saved Cognito configuration to {config_file}")


def main() -> None:
    """Main setup function."""
    parser = argparse.ArgumentParser(
        description="Setup Amazon Cognito OAuth for AgentCore Gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Setup Cognito in us-west-2
    python scripts/setup_cognito.py --region us-west-2

    # Use custom name
    python scripts/setup_cognito.py --cognito-name my-gateway-auth
        """,
    )

    parser.add_argument(
        "--region",
        type=str,
        help="AWS region (default: from AWS_REGION env var or us-west-2)",
    )
    parser.add_argument(
        "--cognito-name",
        type=str,
        default="agentcore-observability-gateway-auth",
        help="Name for Cognito User Pool (default: agentcore-observability-gateway-auth)",
    )

    args = parser.parse_args()

    # Get AWS region
    region = args.region or os.getenv("AWS_REGION", "us-west-2")
    logger.info(f"Setting up Cognito in region: {region}")

    # Get project paths
    script_dir = Path(__file__).parent

    # Setup Cognito
    cognito_config = _setup_cognito(region, args.cognito_name)

    # Save configuration
    config_file = script_dir / ".cognito_config.json"
    _save_cognito_config(config_file, cognito_config)

    logger.info("\nCognito setup completed successfully!")
    logger.info(f"User Pool ID: {cognito_config['user_pool_id']}")
    logger.info(f"Client ID: {cognito_config['client_id']}")
    logger.info(f"Discovery URL: {cognito_config['discovery_url']}")
    logger.info(f"\nConfiguration saved to: {config_file}")

    if cognito_config["access_token"]:
        logger.info(f"\nAccess token is available for testing")
    else:
        logger.warning("\nAccess token could not be retrieved")


if __name__ == "__main__":
    main()
