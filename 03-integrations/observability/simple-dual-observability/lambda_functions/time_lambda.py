"""Lambda function wrapper for time tool."""

import json
import logging
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path to import tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.time_tool import get_time

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
    """Lambda handler for time tool.

    Args:
        event: Lambda event containing the request payload
        context: Lambda context object

    Returns:
        API Gateway response with time data
    """
    try:
        logger.info(f"Time Lambda invoked with event: {json.dumps(event, default=str)}")

        # Parse request body
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

        # Extract timezone parameter
        timezone = body.get("timezone")
        if not timezone:
            logger.error("Missing required parameter: timezone")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing required parameter: timezone"}),
            }

        # Call time tool
        logger.info(f"Fetching time for timezone: {timezone}")
        result = get_time(timezone)

        logger.info(f"Time data retrieved successfully: {result}")

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
        logger.exception(f"Unexpected error in time lambda: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"}),
        }
