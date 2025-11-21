"""Lambda function wrapper for calculator tool."""

import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path to import tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.calculator_tool import calculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def lambda_handler(
    event: dict[str, Any],
    context: Any,
) -> dict[str, Any]:
    """Lambda handler for calculator tool.

    Args:
        event: Lambda event containing the request payload
        context: Lambda context object

    Returns:
        API Gateway response with calculation result
    """
    try:
        logger.info(f"Calculator Lambda invoked with event: {json.dumps(event, default=str)}")

        # Parse request body
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

        # Extract parameters
        operation = body.get("operation")
        a = body.get("a")
        b = body.get("b")

        # Validate required parameters
        if not operation:
            logger.error("Missing required parameter: operation")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing required parameter: operation"}),
            }

        if a is None:
            logger.error("Missing required parameter: a")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing required parameter: a"}),
            }

        # Call calculator tool
        logger.info(f"Performing calculation: {operation}({a}, {b})")
        result = calculator(operation, float(a), float(b) if b is not None else None)

        logger.info(f"Calculation result: {result}")

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result),
        }

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }

    except Exception as e:
        logger.exception(f"Unexpected error in calculator lambda: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"}),
        }
