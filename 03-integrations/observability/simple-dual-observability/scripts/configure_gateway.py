"""Configure AgentCore Gateway with Lambda function targets."""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any

import boto3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _load_lambda_deployment_metadata(
    metadata_file: Path,
) -> dict[str, Any]:
    """Load Lambda deployment metadata.

    Args:
        metadata_file: Path to Lambda deployment metadata file

    Returns:
        Lambda deployment metadata
    """
    if not metadata_file.exists():
        raise FileNotFoundError(
            f"Lambda deployment metadata not found: {metadata_file}. "
            "Please run deploy_lambdas.py first."
        )

    with open(metadata_file) as f:
        return json.load(f)


def _create_gateway_iam_role(
    iam_client: Any,
    role_name: str,
) -> str:
    """Create IAM role for AgentCore Gateway.

    Args:
        iam_client: Boto3 IAM client
        role_name: Name for the IAM role

    Returns:
        Role ARN
    """
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    # Policy to invoke Lambda functions
    lambda_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction"
                ],
                "Resource": "*"
            }
        ]
    }

    try:
        # Try to get existing role
        response = iam_client.get_role(RoleName=role_name)
        role_arn = response["Role"]["Arn"]
        logger.info(f"Using existing IAM role: {role_arn}")

        # Update trust policy
        iam_client.update_assume_role_policy(
            RoleName=role_name,
            PolicyDocument=json.dumps(trust_policy)
        )

        return role_arn

    except iam_client.exceptions.NoSuchEntityException:
        # Create new role
        logger.info(f"Creating IAM role: {role_name}")
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for AgentCore Gateway to invoke Lambda functions",
        )
        role_arn = response["Role"]["Arn"]

        # Attach inline policy for Lambda invocation
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName="GatewayLambdaInvokePolicy",
            PolicyDocument=json.dumps(lambda_policy)
        )

        logger.info(f"Created IAM role: {role_arn}")
        return role_arn


def _load_cognito_config(
    config_file: Path,
) -> dict[str, Any]:
    """Load Cognito configuration from JSON file.

    Args:
        config_file: Path to Cognito configuration file

    Returns:
        Cognito configuration dictionary

    Raises:
        FileNotFoundError: If Cognito config file doesn't exist
    """
    if not config_file.exists():
        raise FileNotFoundError(
            f"Cognito configuration not found: {config_file}. "
            "Please run scripts/setup_cognito.py first."
        )

    with open(config_file) as f:
        return json.load(f)


def _create_gateway(
    bedrock_agent_client: Any,
    gateway_name: str,
    gateway_role_arn: str,
    cognito_config: dict[str, Any],
) -> dict[str, Any]:
    """Create or get AgentCore Gateway.

    Args:
        bedrock_agent_client: Boto3 Bedrock AgentCore Control client
        gateway_name: Name for the gateway
        gateway_role_arn: IAM role ARN for the gateway
        cognito_config: Cognito configuration dictionary

    Returns:
        Gateway information
    """
    logger.info(f"Creating AgentCore Gateway: {gateway_name}")

    # Prepare Cognito JWT authorizer configuration
    auth_config = {
        "customJWTAuthorizer": {
            "discoveryUrl": cognito_config["discovery_url"],
            "allowedClients": [cognito_config["client_id"]],
        }
    }

    logger.info(f"Using Cognito User Pool: {cognito_config['user_pool_id']}")
    logger.info(f"Discovery URL: {cognito_config['discovery_url']}")

    try:
        # Create gateway with Cognito JWT authentication
        response = bedrock_agent_client.create_gateway(
            name=gateway_name,
            roleArn=gateway_role_arn,
            protocolType='MCP',
            authorizerType='CUSTOM_JWT',
            authorizerConfiguration=auth_config,
            description="Gateway for weather, time, and calculator tools",
        )

        gateway_id = response["gatewayId"]
        gateway_arn = response["gatewayArn"]
        gateway_url = response.get("gatewayUrl", "")

        logger.info(f"Created gateway: {gateway_id}")
        logger.info(f"Gateway ARN: {gateway_arn}")
        logger.info(f"Gateway URL: {gateway_url}")

        # Wait for gateway to be ACTIVE before returning
        logger.info("Waiting for gateway to be ACTIVE...")
        import time
        max_attempts = 60  # 5 minutes max wait
        for attempt in range(max_attempts):
            try:
                gateway_details = bedrock_agent_client.get_gateway(gatewayIdentifier=gateway_id)
                status = gateway_details.get("status")
                if status in ["ACTIVE", "READY"]:
                    logger.info(f"Gateway is now {status}")
                    break
                elif status in ["FAILED", "DELETING", "DELETED"]:
                    raise ValueError(f"Gateway creation failed with status: {status}")
                else:
                    logger.info(f"Gateway status: {status}, waiting... (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(5)
            except Exception as e:
                if "ThrottlingException" in str(e):
                    logger.info("Rate limited, waiting...")
                    time.sleep(10)
                else:
                    raise
        else:
            raise TimeoutError(f"Gateway did not become ACTIVE/READY within {max_attempts * 5} seconds")

        return {
            "gateway_id": gateway_id,
            "gateway_arn": gateway_arn,
            "gateway_url": gateway_url,
            "gateway_name": gateway_name,
        }

    except Exception as e:
        if "already exists" in str(e).lower() or "ConflictException" in str(e):
            # Gateway already exists, list and find it
            logger.info(f"Gateway {gateway_name} already exists, retrieving...")

            response = bedrock_agent_client.list_gateways()
            for gateway in response.get("items", []):  # Changed from "gateways" to "items"
                if gateway["name"] == gateway_name:
                    gateway_id = gateway["gatewayId"]

                    # Get full gateway details
                    gateway_details = bedrock_agent_client.get_gateway(gatewayIdentifier=gateway_id)

                    logger.info(f"Found existing gateway: {gateway_id}")
                    logger.info(f"Gateway ARN: {gateway_details['gatewayArn']}")
                    logger.info(f"Gateway URL: {gateway_details.get('gatewayUrl', '')}")

                    return {
                        "gateway_id": gateway_id,
                        "gateway_arn": gateway_details["gatewayArn"],
                        "gateway_url": gateway_details.get("gatewayUrl", ""),
                        "gateway_name": gateway_name,
                    }

            raise ValueError(f"Gateway {gateway_name} not found in list")
        else:
            raise


def _register_lambda_target(
    bedrock_agent_client: Any,
    gateway_id: str,
    target_name: str,
    lambda_arn: str,
    tool_schema: dict[str, Any],
) -> dict[str, Any]:
    """Register Lambda function as gateway target.

    Args:
        bedrock_agent_client: Boto3 Bedrock AgentCore Control client
        gateway_id: Gateway ID
        target_name: Name of the target
        lambda_arn: Lambda function ARN
        tool_schema: Tool schema specification

    Returns:
        Target registration response
    """
    logger.info(f"Registering target: {target_name}")

    # Create target configuration in the format expected by the API
    lambda_target_config = {
        "mcp": {
            "lambda": {
                "lambdaArn": lambda_arn,
                "toolSchema": {"inlinePayload": [tool_schema]}
            }
        }
    }

    credential_config = [{"credentialProviderType": "GATEWAY_IAM_ROLE"}]

    try:
        response = bedrock_agent_client.create_gateway_target(
            gatewayIdentifier=gateway_id,
            name=target_name,
            description=f'Lambda Target for {target_name}',
            targetConfiguration=lambda_target_config,
            credentialProviderConfigurations=credential_config
        )

        logger.info(f"Registered target: {target_name}")
        return response

    except Exception as e:
        if "already exists" in str(e).lower() or "ConflictException" in str(e):
            logger.info(f"Target {target_name} already exists, updating...")

            # Get existing target ID
            targets_response = bedrock_agent_client.list_gateway_targets(gatewayIdentifier=gateway_id)
            target_id = None
            for target in targets_response.get("gatewayTargets", []):
                if target["name"] == target_name:
                    target_id = target["targetId"]
                    break

            if not target_id:
                raise ValueError(f"Target {target_name} not found")

            # Update target
            response = bedrock_agent_client.update_gateway_target(
                gatewayIdentifier=gateway_id,
                targetIdentifier=target_id,
                targetConfiguration=lambda_target_config,
                credentialProviderConfigurations=credential_config
            )

            logger.info(f"Updated target: {target_name}")
            return response
        else:
            raise


def _create_tool_specifications() -> dict[str, dict[str, Any]]:
    """Create tool specifications for gateway targets.

    Returns:
        Dictionary of tool specifications
    """
    return {
        "agentcore-weather-tool": {
            "name": "get_weather",
            "description": "Get current weather information for a given city",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The city name (e.g., 'Seattle', 'New York')",
                    }
                },
                "required": ["city"],
            },
        },
        "agentcore-time-tool": {
            "name": "get_time",
            "description": "Get current time for a given timezone",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone name (e.g., 'America/New_York', 'Europe/London')",
                    }
                },
                "required": ["timezone"],
            },
        },
        "agentcore-calculator-tool": {
            "name": "calculator",
            "description": "Perform mathematical calculations",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "The mathematical operation (add, subtract, multiply, divide, factorial)",
                    },
                    "a": {
                        "type": "number",
                        "description": "First number (or the number for factorial)",
                    },
                    "b": {
                        "type": "number",
                        "description": "Second number (not used for factorial)",
                    },
                },
                "required": ["operation", "a"],
            },
        },
    }


def _save_gateway_metadata(
    metadata_file: Path,
    gateway_info: dict[str, Any],
    targets: dict[str, Any],
) -> None:
    """Save gateway configuration metadata.

    Args:
        metadata_file: Path to metadata file
        gateway_info: Gateway information
        targets: Dictionary of registered targets
    """
    metadata = {
        "gateway": gateway_info,
        "targets": targets,
    }

    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    logger.info(f"Saved gateway metadata to {metadata_file}")


def main() -> None:
    """Main configuration function."""
    parser = argparse.ArgumentParser(
        description="Configure AgentCore Gateway with Lambda targets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Configure gateway with deployed Lambda functions
    python scripts/configure_gateway.py --region us-east-1

    # Use custom gateway name
    python scripts/configure_gateway.py --gateway-name my-gateway
        """,
    )

    parser.add_argument(
        "--region",
        type=str,
        help="AWS region (default: from AWS_REGION env var or us-east-1)",
    )
    parser.add_argument(
        "--gateway-name",
        type=str,
        default="agentcore-observability-gateway",
        help="Gateway name (default: agentcore-observability-gateway)",
    )

    args = parser.parse_args()

    # Get AWS region
    region = args.region or os.getenv("AWS_REGION", "us-east-1")
    logger.info(f"Configuring gateway in region: {region}")

    # Get project paths
    script_dir = Path(__file__).parent

    # Load Lambda deployment metadata
    lambda_metadata_file = script_dir / ".lambda_deployment.json"
    lambda_metadata = _load_lambda_deployment_metadata(lambda_metadata_file)

    # Load Cognito configuration
    cognito_config_file = script_dir / ".cognito_config.json"
    try:
        cognito_config = _load_cognito_config(cognito_config_file)
        logger.info(f"Loaded Cognito configuration from {cognito_config_file}")
    except FileNotFoundError as e:
        logger.error(str(e))
        logger.error("Run: python scripts/setup_cognito.py --region us-west-2")
        return

    # Initialize AWS clients
    iam_client = boto3.client("iam")
    bedrock_agent_client = boto3.client("bedrock-agentcore-control", region_name=region)

    # Create IAM role for gateway
    gateway_role_name = "agentcore-gateway-role"
    gateway_role_arn = _create_gateway_iam_role(iam_client, gateway_role_name)

    logger.info("Waiting for IAM role to propagate...")
    import time
    time.sleep(10)

    # Create or get gateway
    gateway_info = _create_gateway(
        bedrock_agent_client, args.gateway_name, gateway_role_arn, cognito_config
    )

    # Get tool specifications
    tool_specs = _create_tool_specifications()

    # Register Lambda functions as targets
    targets = {}
    for function_name, function_info in lambda_metadata["lambda_functions"].items():
        if function_name in tool_specs:
            target_name = function_name.replace('_', '-') + '-target'

            response = _register_lambda_target(
                bedrock_agent_client,
                gateway_info["gateway_id"],
                target_name,
                function_info["function_arn"],
                tool_specs[function_name],
            )

            targets[target_name] = {
                "target_id": response["targetId"],
                "target_arn": response.get("targetArn", ""),
                "lambda_arn": function_info["function_arn"],
                "tool_name": tool_specs[function_name]["name"],
            }

            # Add delay to avoid rate limiting
            import time
            time.sleep(5)

    # Save gateway metadata
    gateway_metadata_file = script_dir / ".gateway_config.json"
    _save_gateway_metadata(gateway_metadata_file, gateway_info, targets)

    logger.info("\nGateway configuration completed successfully!")
    logger.info(f"Gateway ID: {gateway_info['gateway_id']}")
    logger.info(f"Gateway ARN: {gateway_info['gateway_arn']}")
    logger.info(f"Registered {len(targets)} targets")
    logger.info(f"Metadata saved to: {gateway_metadata_file}")


if __name__ == "__main__":
    main()
