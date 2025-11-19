#!/bin/bash

# Exit on error
set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env file if it exists
if [ -f "$PARENT_DIR/.env" ]; then
    echo "Loading environment variables from .env file..."
    set -a
    source "$PARENT_DIR/.env"
    set +a
fi

# Default values
AWS_REGION="${AWS_REGION:-us-east-1}"
USE_GATEWAY="${USE_GATEWAY:-false}"
AGENT_NAME="${AGENT_NAME:-weather_time_observability_agent}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --region)
            AWS_REGION="$2"
            shift 2
            ;;
        --use-gateway)
            USE_GATEWAY="$2"
            shift 2
            ;;
        --agent-name)
            AGENT_NAME="$2"
            shift 2
            ;;
        --braintrust-api-key)
            BRAINTRUST_API_KEY="$2"
            shift 2
            ;;
        --braintrust-project-id)
            BRAINTRUST_PROJECT_ID="$2"
            shift 2
            ;;
        --gateway-arn)
            GATEWAY_ARN="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --region REGION                    AWS region (default: us-east-1)"
            echo "  --use-gateway true|false           Enable Gateway mode (default: false)"
            echo "  --agent-name NAME                  Agent name (default: weather_time_observability_agent)"
            echo "  --braintrust-api-key KEY          Braintrust API key (optional)"
            echo "  --braintrust-project-id ID        Braintrust project ID (optional)"
            echo "  --gateway-arn ARN                 Gateway ARN (required if use-gateway=true)"
            echo "  -h, --help                        Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  AWS_REGION                         AWS region"
            echo "  USE_GATEWAY                        Enable Gateway mode"
            echo "  GATEWAY_ARN                        Gateway ARN"
            echo "  BRAINTRUST_API_KEY                Braintrust API key"
            echo "  BRAINTRUST_PROJECT_ID             Braintrust project ID"
            echo ""
            echo "Examples:"
            echo "  # Deploy with local tools"
            echo "  $0 --region us-east-1 --use-gateway false"
            echo ""
            echo "  # Deploy with Gateway tools"
            echo "  $0 --region us-east-1 --use-gateway true --gateway-arn arn:aws:bedrock:..."
            echo ""
            echo "  # Deploy with Braintrust observability"
            echo "  $0 --braintrust-api-key xxx --braintrust-project-id yyy"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "AgentCore Deployment with Gateway Support"
echo "=========================================="
echo "Region: $AWS_REGION"
echo "Agent Name: $AGENT_NAME"
echo "Use Gateway: $USE_GATEWAY"
echo ""

# If Gateway mode is enabled, deploy Lambda functions and configure gateway
if [ "$USE_GATEWAY" = "true" ]; then
    echo "Gateway mode enabled - deploying Lambda functions and configuring gateway..."
    echo ""

    # Deploy Lambda functions
    echo "Step 1: Deploying Lambda functions..."
    python "$SCRIPT_DIR/deploy_lambdas.py" --region "$AWS_REGION"
    echo ""

    # Configure Gateway
    echo "Step 2: Configuring AgentCore Gateway..."
    python "$SCRIPT_DIR/configure_gateway.py" --region "$AWS_REGION"
    echo ""

    # Read gateway ARN from configuration file
    if [ -z "$GATEWAY_ARN" ]; then
        GATEWAY_CONFIG_FILE="$SCRIPT_DIR/.gateway_config.json"
        if [ -f "$GATEWAY_CONFIG_FILE" ]; then
            GATEWAY_ARN=$(python -c "import json; print(json.load(open('$GATEWAY_CONFIG_FILE'))['gateway']['gateway_arn'])")
            echo "Using Gateway ARN from config: $GATEWAY_ARN"
        else
            echo "Error: Gateway ARN not found. Please provide --gateway-arn or ensure gateway configuration exists."
            exit 1
        fi
    fi

    # Use gateway-enabled agent
    ENTRYPOINT="agent/weather_time_agent_gateway.py"
    GATEWAY_ENV_VAR="--env USE_GATEWAY=true --env GATEWAY_ARN=$GATEWAY_ARN"
else
    echo "Local tool mode - using agent with local tools..."
    echo ""

    # Use original agent
    ENTRYPOINT="agent/weather_time_agent.py"
    GATEWAY_ENV_VAR=""
fi

# Deploy agent to AgentCore Runtime
echo "Step 3: Deploying agent to AgentCore Runtime..."
echo ""

# Build deployment command
DEPLOY_CMD="python $SCRIPT_DIR/deploy_agent.py --region $AWS_REGION --agent-name $AGENT_NAME"

# Add Braintrust configuration if provided
if [ -n "$BRAINTRUST_API_KEY" ]; then
    DEPLOY_CMD="$DEPLOY_CMD --braintrust-api-key $BRAINTRUST_API_KEY"
fi

if [ -n "$BRAINTRUST_PROJECT_ID" ]; then
    DEPLOY_CMD="$DEPLOY_CMD --braintrust-project-id $BRAINTRUST_PROJECT_ID"
fi

# Execute deployment
eval "$DEPLOY_CMD"

echo ""
echo "=========================================="
echo "Deployment completed successfully!"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  - Tool Mode: $([ "$USE_GATEWAY" = "true" ] && echo "Gateway (Lambda)" || echo "Local")"
echo "  - Agent Name: $AGENT_NAME"
echo "  - Region: $AWS_REGION"
if [ "$USE_GATEWAY" = "true" ]; then
    echo "  - Gateway ARN: $GATEWAY_ARN"
fi
if [ -n "$BRAINTRUST_API_KEY" ]; then
    echo "  - Braintrust: Enabled"
fi
echo ""
echo "Next steps:"
echo "  1. Test the agent: ./scripts/tests/test_agent.sh"
echo "  2. Run demo scenarios: python simple_observability.py"
echo "  3. View logs: ./scripts/check_logs.sh"
echo ""
