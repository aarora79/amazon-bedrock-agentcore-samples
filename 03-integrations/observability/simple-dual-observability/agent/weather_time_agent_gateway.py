"""
Strands-based agent with Gateway tool support.

This agent supports two modes based on USE_GATEWAY environment variable:
- USE_GATEWAY=false: Uses local tool implementations (default)
- USE_GATEWAY=true: Uses AgentCore Gateway with Lambda function targets

When deployed to Amazon Bedrock AgentCore Runtime, it receives OpenTelemetry instrumentation.
"""

import json
import logging
import os
from typing import Any

import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


# Initialize AgentCore Runtime App
app = BedrockAgentCoreApp()


# Gateway-based tool implementations
def _invoke_gateway_tool(
    gateway_arn: str,
    tool_name: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Invoke tool via AgentCore Gateway.

    Args:
        gateway_arn: Gateway ARN
        tool_name: Name of the tool to invoke
        parameters: Tool parameters

    Returns:
        Tool execution result
    """
    logger.info(f"Invoking gateway tool: {tool_name}")
    logger.debug(f"Parameters: {json.dumps(parameters, default=str)}")

    bedrock_agent_runtime = boto3.client("bedrock-agent-runtime")

    try:
        response = bedrock_agent_runtime.invoke_gateway_tool(
            gatewayArn=gateway_arn,
            toolName=tool_name,
            input=json.dumps(parameters),
        )

        # Parse response body
        result = json.loads(response["body"].read())
        logger.info(f"Gateway tool {tool_name} executed successfully")
        logger.debug(f"Result: {json.dumps(result, default=str)}")

        return result

    except Exception as e:
        logger.error(f"Error invoking gateway tool {tool_name}: {e}")
        raise


def _create_local_tools() -> list:
    """Create local tool implementations.

    Returns:
        List of Strands tool decorators
    """
    from strands import tool

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
        Get current time for a given timezone.

        Args:
            timezone: Timezone name (e.g., 'America/New_York', 'Europe/London')

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

    return [get_weather, get_time, calculator]


def _create_gateway_tools(
    gateway_arn: str,
) -> list:
    """Create gateway-based tool implementations.

    Args:
        gateway_arn: Gateway ARN

    Returns:
        List of Strands tool decorators
    """
    from strands import tool

    @tool
    def get_weather(city: str) -> dict[str, Any]:
        """
        Get current weather information for a given city.

        Args:
            city: The city name (e.g., 'Seattle', 'New York')

        Returns:
            Weather information including temperature, conditions, and humidity
        """
        return _invoke_gateway_tool(
            gateway_arn,
            "get_weather",
            {"city": city},
        )

    @tool
    def get_time(timezone: str) -> dict[str, Any]:
        """
        Get current time for a given timezone.

        Args:
            timezone: Timezone name (e.g., 'America/New_York', 'Europe/London')

        Returns:
            Current time, date, timezone, and UTC offset information
        """
        return _invoke_gateway_tool(
            gateway_arn,
            "get_time",
            {"timezone": timezone},
        )

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
        params = {"operation": operation, "a": a}
        if b is not None:
            params["b"] = b

        return _invoke_gateway_tool(
            gateway_arn,
            "calculator",
            params,
        )

    return [get_weather, get_time, calculator]


# Initialize Bedrock model
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
model = BedrockModel(model_id=MODEL_ID)

logger.info(f"Initializing Strands agent with model: {MODEL_ID}")


def _initialize_agent() -> Agent:
    """
    Initialize the agent with proper tool and telemetry configuration.

    This function is called lazily to ensure environment variables
    (especially Braintrust and Gateway configuration) are set before initialization.

    Returns:
        Configured Strands Agent instance
    """
    # Check if Gateway mode is enabled
    use_gateway = os.getenv("USE_GATEWAY", "false").lower() == "true"
    gateway_arn = os.getenv("GATEWAY_ARN")

    if use_gateway:
        if not gateway_arn:
            raise ValueError(
                "USE_GATEWAY is enabled but GATEWAY_ARN environment variable is not set. "
                "Please provide the Gateway ARN."
            )

        logger.info(f"Gateway mode enabled: {gateway_arn}")
        tools = _create_gateway_tools(gateway_arn)
        tool_mode = "AgentCore Gateway"
    else:
        logger.info("Local tool mode enabled")
        tools = _create_local_tools()
        tool_mode = "Local tools"

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
    logger.info("Tools available: get_weather, get_time, calculator")

    return agent


@app.entrypoint
def strands_agent_bedrock(payload: dict[str, Any]) -> str:
    """
    Entry point for AgentCore Runtime invocation.

    This function is decorated with @app.entrypoint which makes it the entry point
    for the AgentCore Runtime. When deployed, the agent initializes with either
    local tools or gateway tools based on USE_GATEWAY environment variable.

    Tool Configuration:
    - USE_GATEWAY=false: Tools execute locally within the agent container
    - USE_GATEWAY=true: Tools execute via AgentCore Gateway with Lambda targets

    Telemetry Configuration:
    - When BRAINTRUST_API_KEY env var is set: Strands telemetry exports OTEL traces
      to Braintrust via OTEL_EXPORTER_OTLP_* environment variables
    - When BRAINTRUST_API_KEY is not set: Agent runs with CloudWatch logs only

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
