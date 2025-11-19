"""Deploy Lambda functions for AgentCore Gateway tool targets."""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import boto3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# Constants
LAMBDA_RUNTIME = "python3.12"
LAMBDA_TIMEOUT = 30
LAMBDA_MEMORY = 256
LAMBDA_ARCHITECTURE = "x86_64"


def _get_aws_account_id() -> str:
    """Get AWS account ID.

    Returns:
        AWS account ID
    """
    sts_client = boto3.client("sts")
    return sts_client.get_caller_identity()["Account"]


def _create_lambda_role(
    iam_client: Any,
    role_name: str,
) -> str:
    """Create IAM role for Lambda functions.

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
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        # Try to get existing role
        response = iam_client.get_role(RoleName=role_name)
        role_arn = response["Role"]["Arn"]
        logger.info(f"Using existing IAM role: {role_arn}")
        return role_arn

    except iam_client.exceptions.NoSuchEntityException:
        # Create new role
        logger.info(f"Creating IAM role: {role_name}")
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for AgentCore Gateway Lambda functions",
        )
        role_arn = response["Role"]["Arn"]

        # Attach basic Lambda execution policy
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )

        logger.info(f"Created IAM role: {role_arn}")
        return role_arn


def _create_deployment_package(
    lambda_dir: Path,
    output_zip: Path,
) -> None:
    """Create Lambda deployment package.

    Args:
        lambda_dir: Directory containing Lambda function code
        output_zip: Path to output ZIP file
    """
    logger.info(f"Creating deployment package for {lambda_dir.name}")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy Lambda function file
        lambda_files = list(lambda_dir.glob("*_lambda.py"))
        if not lambda_files:
            raise ValueError(f"No Lambda function found in {lambda_dir}")

        lambda_file = lambda_files[0]
        shutil.copy(lambda_file, temp_path / lambda_file.name)

        # Copy tools directory
        tools_dir = lambda_dir.parent / "tools"
        if tools_dir.exists():
            shutil.copytree(tools_dir, temp_path / "tools")

        # Install dependencies if requirements.txt exists
        requirements_file = lambda_dir / "requirements.txt"
        if requirements_file.exists():
            logger.info("Installing Lambda dependencies")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    str(requirements_file),
                    "-t",
                    str(temp_path),
                    "--quiet",
                ],
                check=True,
            )

        # Create ZIP file
        logger.info(f"Creating ZIP file: {output_zip}")
        shutil.make_archive(
            str(output_zip.with_suffix("")),
            "zip",
            temp_path,
        )


def _deploy_lambda_function(
    lambda_client: Any,
    function_name: str,
    deployment_package: Path,
    role_arn: str,
    handler: str,
) -> dict[str, Any]:
    """Deploy or update Lambda function.

    Args:
        lambda_client: Boto3 Lambda client
        function_name: Name of the Lambda function
        deployment_package: Path to deployment ZIP file
        role_arn: IAM role ARN
        handler: Lambda handler string

    Returns:
        Lambda function configuration
    """
    logger.info(f"Deploying Lambda function: {function_name}")

    with open(deployment_package, "rb") as f:
        zip_data = f.read()

    try:
        # Try to update existing function
        response = lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=zip_data,
        )
        logger.info(f"Updated existing Lambda function: {function_name}")

        # Update configuration
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Runtime=LAMBDA_RUNTIME,
            Handler=handler,
            Timeout=LAMBDA_TIMEOUT,
            MemorySize=LAMBDA_MEMORY,
        )

        return response

    except lambda_client.exceptions.ResourceNotFoundException:
        # Create new function
        logger.info(f"Creating new Lambda function: {function_name}")
        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime=LAMBDA_RUNTIME,
            Role=role_arn,
            Handler=handler,
            Code={"ZipFile": zip_data},
            Timeout=LAMBDA_TIMEOUT,
            MemorySize=LAMBDA_MEMORY,
            Architectures=[LAMBDA_ARCHITECTURE],
            Description=f"AgentCore Gateway tool: {function_name}",
        )

        # Wait for function to be active
        logger.info("Waiting for Lambda function to be active...")
        waiter = lambda_client.get_waiter("function_active_v2")
        waiter.wait(FunctionName=function_name)

        return response


def _save_deployment_metadata(
    metadata_file: Path,
    lambda_functions: dict[str, dict[str, Any]],
) -> None:
    """Save Lambda deployment metadata.

    Args:
        metadata_file: Path to metadata file
        lambda_functions: Dictionary of Lambda function information
    """
    metadata = {
        "lambda_functions": lambda_functions,
    }

    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    logger.info(f"Saved deployment metadata to {metadata_file}")


def main() -> None:
    """Main deployment function."""
    parser = argparse.ArgumentParser(
        description="Deploy Lambda functions for AgentCore Gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
    # Deploy Lambda functions
    python scripts/deploy_lambdas.py --region us-east-1

    # Deploy with custom role name
    python scripts/deploy_lambdas.py --role-name my-lambda-role
        """,
    )

    parser.add_argument(
        "--region",
        type=str,
        help="AWS region (default: from AWS_REGION env var or us-east-1)",
    )
    parser.add_argument(
        "--role-name",
        type=str,
        default="agentcore-gateway-lambda-role",
        help="IAM role name for Lambda functions (default: agentcore-gateway-lambda-role)",
    )

    args = parser.parse_args()

    # Get AWS region
    region = args.region or os.getenv("AWS_REGION", "us-east-1")
    logger.info(f"Deploying to region: {region}")

    # Initialize AWS clients
    iam_client = boto3.client("iam", region_name=region)
    lambda_client = boto3.client("lambda", region_name=region)

    # Get project paths
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    lambda_dir = project_dir / "lambda_functions"

    # Create IAM role
    role_arn = _create_lambda_role(iam_client, args.role_name)

    # Wait a bit for role to propagate
    import time

    logger.info("Waiting for IAM role to propagate...")
    time.sleep(10)

    # Define Lambda functions to deploy
    lambda_configs = [
        {
            "name": "agentcore-weather-tool",
            "handler": "weather_lambda.lambda_handler",
            "description": "Weather information tool",
        },
        {
            "name": "agentcore-time-tool",
            "handler": "time_lambda.lambda_handler",
            "description": "Time and timezone tool",
        },
        {
            "name": "agentcore-calculator-tool",
            "handler": "calculator_lambda.lambda_handler",
            "description": "Mathematical calculator tool",
        },
    ]

    # Deploy each Lambda function
    lambda_functions = {}

    for config in lambda_configs:
        function_name = config["name"]

        # Create deployment package
        zip_file = script_dir / f"{function_name}.zip"
        _create_deployment_package(lambda_dir, zip_file)

        # Deploy Lambda function
        result = _deploy_lambda_function(
            lambda_client,
            function_name,
            zip_file,
            role_arn,
            config["handler"],
        )

        lambda_functions[function_name] = {
            "function_arn": result["FunctionArn"],
            "function_name": result["FunctionName"],
            "handler": config["handler"],
            "description": config["description"],
        }

        # Clean up ZIP file
        zip_file.unlink()

        logger.info(f"Successfully deployed: {function_name}")
        logger.info(f"  ARN: {result['FunctionArn']}")

    # Save deployment metadata
    metadata_file = script_dir / ".lambda_deployment.json"
    _save_deployment_metadata(metadata_file, lambda_functions)

    logger.info("\nLambda deployment completed successfully!")
    logger.info(f"Deployed {len(lambda_functions)} Lambda functions")
    logger.info(f"Metadata saved to: {metadata_file}")


if __name__ == "__main__":
    main()
