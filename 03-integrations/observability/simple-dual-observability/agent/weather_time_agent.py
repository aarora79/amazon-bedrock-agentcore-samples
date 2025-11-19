"""
Strands-based agent for weather, time, and calculator queries.

This agent supports two modes controlled by the USE_GATEWAY environment variable:
1. Local Tools Mode (USE_GATEWAY=false): Tools execute within the agent container
2. Gateway Mode (USE_GATEWAY=true): Tools are invoked via AgentCore Gateway with Lambda functions

The agent is designed to be deployed to Amazon Bedrock AgentCore Runtime
where it will receive OpenTelemetry instrumentation.

Uses Strands framework with Amazon Bedrock models.

When Braintrust observability is enabled (via BRAINTRUST_API_KEY env var),
the agent initializes Strands telemetry to export traces to Braintrust.
"""

import logging
import os
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# Initialize AgentCore Runtime App
app = BedrockAgentCoreApp()


# ============================================================================
# Gateway Mode Functions
# ============================================================================


def _get_gateway_endpoint(gateway_arn: str) -> str:
    """
    Get Gateway endpoint URL from ARN.

    Args:
        gateway_arn: Gateway ARN in format arn:aws:bedrock-agentcore:REGION:ACCOUNT:gateway/GATEWAY_ID

    Returns:
        Gateway endpoint URL
    """
    # ARN format: arn:aws:bedrock-agentcore:REGION:ACCOUNT:gateway/GATEWAY_ID
    parts = gateway_arn.split(":")
    region = parts[3]
    gateway_id = parts[5].split("/")[1]

    endpoint = f"https://{gateway_id}.gateway.bedrock-agentcore.{region}.amazonaws.com"
    logger.info(f"Gateway endpoint: {endpoint}")
    return endpoint


def _get_gateway_access_token() -> str | None:
    """
    Get access token for Gateway authentication using Cognito OAuth.

    Returns:
        Access token string or None if configuration is missing
    """
    cognito_domain = os.getenv("COGNITO_DOMAIN")
    cognito_client_id = os.getenv("COGNITO_CLIENT_ID")
    cognito_client_secret = os.getenv("COGNITO_CLIENT_SECRET")

    if not all([cognito_domain, cognito_client_id, cognito_client_secret]):
        logger.warning(
            "Cognito credentials not configured - Gateway tools may fail authentication"
        )
        return None

    try:
        import requests

        # Cognito OAuth token URL
        token_url = f"{cognito_domain}/oauth2/token"

        # Request access token using client credentials flow
        auth_data = {
            "grant_type": "client_credentials",
            "client_id": cognito_client_id,
            "client_secret": cognito_client_secret,
        }

        response = requests.post(
            token_url,
            data=auth_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()

        access_token = response.json().get("access_token")
        logger.info("Successfully obtained Gateway access token from Cognito")
        return access_token

    except Exception as e:
        logger.error(f"Failed to get Gateway access token: {e}")
        return None


def _create_mcp_client(gateway_arn: str):
    """
    Create MCP client connected to Gateway.

    This function creates an MCP (Model Context Protocol) client that connects to the
    AgentCore Gateway. The Gateway authenticates using Cognito OAuth JWT tokens and
    provides access to Lambda-based tools.

    Args:
        gateway_arn: Gateway ARN

    Returns:
        Configured MCP client or None if connection fails
    """
    try:
        from mcp.client.streamable_http import streamablehttp_client
        from strands.tools.mcp import MCPClient

        gateway_endpoint = _get_gateway_endpoint(gateway_arn)
        access_token = _get_gateway_access_token()

        # Prepare headers with authentication
        headers = {}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        else:
            logger.warning("No access token available - Gateway may reject requests")

        # Create MCP client
        logger.info(f"Creating MCP client for Gateway: {gateway_endpoint}/mcp")
        mcp_client = MCPClient(
            lambda: streamablehttp_client(
                url=f"{gateway_endpoint}/mcp",
                headers=headers,
            )
        )

        # Enter the context manager to initialize the connection
        mcp_client.__enter__()

        # Verify connection by listing tools
        tools = mcp_client.list_tools_sync()
        logger.info(f"MCP client connected successfully - found {len(tools)} tools")

        if tools:
            try:
                # Try to get tool names for logging
                tool_names = [getattr(tool, 'name', str(tool)) for tool in tools]
                logger.info(f"Available Gateway tools: {', '.join(tool_names)}")
            except Exception as te:
                logger.warning(f"Could not extract tool names: {te}")

        return mcp_client

    except Exception as e:
        logger.error(f"Failed to create MCP client: {e}")
        logger.error(
            "Ensure Gateway is deployed and Cognito credentials are configured"
        )
        return None


# ============================================================================
# Local Tools Mode - Tool Definitions
# ============================================================================


@tool
def get_weather(city: str) -> dict[str, Any]:
    """
    Get current weather information for a given city.

    Args:
        city: The city name (e.g., 'Seattle', 'New York')

    Returns:
        Weather information including temperature, conditions, and humidity
    """
    from tools.weather_tool import get_weather as weather_impl

    logger.info(f"Getting weather for city: {city}")
    result = weather_impl(city)
    logger.debug(f"Weather result: {result}")

    return result


@tool
def get_time(timezone: str) -> dict[str, Any]:
    """
    Get current time for a given city or timezone.

    Args:
        timezone: Timezone name (e.g., 'America/New_York', 'Europe/London') or city name

    Returns:
        Current time, date, timezone, and UTC offset information
    """
    from tools.time_tool import get_time as time_impl

    logger.info(f"Getting time for timezone: {timezone}")
    result = time_impl(timezone)
    logger.debug(f"Time result: {result}")

    return result


@tool
def calculator(operation: str, a: float, b: float = None) -> dict[str, Any]:
    """
    Perform mathematical calculations.

    Args:
        operation: The mathematical operation (add, subtract, multiply, divide, factorial)
        a: First number (or the number for factorial)
        b: Second number (not used for factorial)

    Returns:
        Calculation result with operation details
    """
    from tools.calculator_tool import calculator as calc_impl

    logger.info(f"Performing calculation: {operation}({a}, {b})")
    result = calc_impl(operation, a, b)
    logger.debug(f"Calculator result: {result}")

    return result


# Initialize Bedrock model
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
model = BedrockModel(model_id=MODEL_ID)

logger.info(f"Initializing Strands agent with model: {MODEL_ID}")


def _create_local_tools() -> list:
    """
    Create local tools for the agent.

    Returns:
        List of Strands tool functions
    """
    logger.info("Creating local tools: get_weather, get_time, calculator")
    return [get_weather, get_time, calculator]


def _initialize_agent() -> Agent:
    """
    Initialize the agent with proper telemetry and tool configuration.

    This function checks the USE_GATEWAY environment variable to determine
    whether to use local tools or Gateway-based tools.

    Returns:
        Configured Strands Agent instance
    """
    # Initialize Braintrust telemetry if configured
    braintrust_api_key = os.getenv("BRAINTRUST_API_KEY")
    if braintrust_api_key:
        logger.info("Braintrust observability enabled - initializing telemetry")
        try:
            from strands.telemetry import StrandsTelemetry

            strands_telemetry = StrandsTelemetry()
            strands_telemetry.setup_otlp_exporter()
            logger.info("Strands telemetry initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Strands telemetry: {e}")
            logger.warning("Continuing without Braintrust observability")
    else:
        logger.info("Braintrust observability not configured (CloudWatch only)")

    # Determine tool mode from environment
    use_gateway = os.getenv("USE_GATEWAY", "false").lower() == "true"
    gateway_arn = os.getenv("GATEWAY_ARN")

    if use_gateway:
        logger.info("=" * 70)
        logger.info("GATEWAY MODE ENABLED")
        logger.info("=" * 70)
        logger.info(f"Gateway ARN: {gateway_arn}")

        # Create MCP client to connect to Gateway
        mcp_client = _create_mcp_client(gateway_arn)
        if not mcp_client:
            raise RuntimeError("Failed to create MCP client for Gateway connection")

        # Get tools from MCP client - Strands will automatically use them
        tools = mcp_client.list_tools_sync()
        tool_mode = "AgentCore Gateway"
        logger.info(f"Agent initialized with {len(tools)} Gateway tools")
    else:
        logger.info("=" * 70)
        logger.info("LOCAL TOOLS MODE ENABLED")
        logger.info("=" * 70)
        logger.info("Tools will execute within agent container")

        tools = _create_local_tools()
        tool_mode = "Local tools"
        logger.info(f"Agent initialized with {len(tools)} local tools")

    # Create and return the agent
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt=(
            "You are a helpful assistant with access to weather, time, and calculator tools. "
            "Use these tools to accurately answer user questions. Always provide clear, "
            "concise responses based on the tool outputs. When using tools:\n"
            "- For weather: Use the city name directly\n"
            "- For time: Use timezone format like 'America/New_York' or city names\n"
            "- For calculator: Use operations like 'add', 'subtract', 'multiply', 'divide', or 'factorial'\n"
            "Be friendly and helpful in your responses."
        ),
    )

    logger.info(f"Agent initialized with {tool_mode}")
    logger.info("=" * 70)

    return agent


@app.entrypoint
def strands_agent_bedrock(payload: dict[str, Any]) -> str:
    """
    Entry point for AgentCore Runtime invocation.

    This function is decorated with @app.entrypoint which makes it the entry point
    for the AgentCore Runtime. When deployed, the agent initializes Strands telemetry
    which provides OpenTelemetry instrumentation.

    Telemetry Configuration:
    - When BRAINTRUST_API_KEY env var is set: Strands telemetry is initialized to export
      OTEL traces to Braintrust via OTEL_EXPORTER_OTLP_* environment variables
    - When BRAINTRUST_API_KEY is not set: Agent runs with CloudWatch logs only

    Tool Configuration:
    - When USE_GATEWAY=false: Tools execute within the agent container (default)
    - When USE_GATEWAY=true: Tools are invoked via AgentCore Gateway with Lambda functions

    Args:
        payload: Input payload containing the user prompt

    Returns:
        Agent response text
    """
    user_input = payload.get("prompt", "")

    logger.info(f"Agent invoked with prompt: {user_input}")

    # Initialize agent with proper configuration (lazy initialization)
    agent = _initialize_agent()

    # Invoke the Strands agent
    response = agent(user_input)

    # Extract response text
    response_text = response.message["content"][0]["text"]

    logger.info("Agent invocation completed successfully")
    logger.debug(f"Response: {response_text}")

    return response_text


if __name__ == "__main__":
    # When deployed to AgentCore Runtime, this will start the HTTP server
    # listening on port 8080 with /invocations and /ping endpoints
    app.run()
