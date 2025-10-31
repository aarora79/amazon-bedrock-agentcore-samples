# Simple Dual Observability Tutorial - Final Implementation Summary

## Overview

This tutorial demonstrates Amazon Bedrock AgentCore's automatic observability features with Braintrust integration for AI-focused monitoring.

## Key Finding: CloudWatch Metrics Limitation

**Important:** Bedrock AgentCore Runtime does NOT emit standard CloudWatch Metrics for agent invocations. Instead, observability is provided through:

### 1. CloudWatch Logs (Recommended for Debugging)
**Location:** `/aws/bedrock-agentcore/runtimes/{AGENT_ID}-DEFAULT/`

**View logs:**
```bash
./scripts/check_cw_logs.sh --last-30-min
./scripts/check_cw_logs.sh --follow
```

**Features:**
- Detailed execution logs with timestamps
- Agent initialization and error messages
- Real-time log following capability

### 2. AWS X-Ray Traces (Recommended for Monitoring)
**View in CloudWatch console:** CloudWatch → X-Ray → Traces

**Features:**
- Complete distributed tracing
- Latency details for each operation
- Tool call flow visualization
- Error tracking and analysis

### 3. Braintrust (Optional - AI-Focused Observability)
**Setup:** Configure `BRAINTRUST_API_KEY` environment variable

**Features:**
- LLM cost tracking
- Quality metrics
- Custom dashboards
- Comparative analysis

## Included Utilities

### Agent Deployment & Testing

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup_all.sh` | Deploy agent to runtime | `./scripts/setup_all.sh` |
| `deploy_agent.sh` | Direct agent deployment | `./scripts/deploy_agent.sh` |
| `cleanup.sh` | Remove deployed agent | `./scripts/cleanup.sh` |
| `check_logs.sh` | View agent runtime logs | `./scripts/check_logs.sh` |

### Observability & Debugging

| Script | Purpose | Usage |
|--------|---------|-------|
| `check_cw_logs.sh` | CloudWatch logs viewer | `./scripts/check_cw_logs.sh [--last-hour\|--last-30-min\|--last-24h\|--follow]` |
| `check_cw_metrics.sh` | Gateway metrics viewer | `./scripts/check_cw_metrics.sh [--metric NAME] [--stat TYPE] [--last-hour\|--last-30-min\|--last-24h]` |

### Testing

| Script | Purpose | Usage |
|--------|---------|-------|
| `tests/test_agent.py` | Manual agent testing | `uv run python scripts/tests/test_agent.py --test weather` |
| `tests/run_load_test.sh` | Load testing | `./scripts/tests/run_load_test.sh quick` |

## Architecture

```
Your Application
  ↓ (invoke_agent via boto3)
Bedrock AgentCore Runtime
  ├─ Automatic OpenTelemetry Instrumentation
  ├─ Sends traces to CloudWatch Logs + X-Ray
  └─ (Optional) Sends to Braintrust if configured
    ├─ CloudWatch Logs: /aws/bedrock-agentcore/runtimes/{AGENT_ID}
    ├─ X-Ray: Distributed traces
    └─ Braintrust: AI observability
```

## Quick Start

### 1. Deploy Agent
```bash
./scripts/setup_all.sh
```

### 2. Test Agent
```bash
# Single test
uv run python scripts/tests/test_agent.py --test weather

# Load testing
./scripts/tests/run_load_test.sh quick
```

### 3. View Observability Data

**CloudWatch Logs:**
```bash
./scripts/check_cw_logs.sh --last-30-min
```

**X-Ray Traces:**
- Open AWS CloudWatch Console
- Navigate to X-Ray → Traces
- Filter by service name or agent name

**Braintrust (if configured):**
- Visit https://www.braintrust.dev
- View project dashboard with LLM metrics

## Configuration

### Environment Variables

**Required:**
- `AWS_REGION` - AWS region (default: us-east-1)
- `AGENTCORE_AGENT_ID` - Agent ID from deployment

**Optional:**
- `BRAINTRUST_API_KEY` - Enable Braintrust observability
- `BRAINTRUST_PROJECT_ID` - Braintrust project identifier

See `config/.env.example` for all options.

## Troubleshooting

### No logs appearing
```bash
# Check recent logs
./scripts/check_cw_logs.sh --last-30-min

# Check log group exists
aws logs describe-log-groups --region us-east-1 | grep weather_time
```

### Agent not responding
```bash
# Verify deployment
aws bedrock-agent describe-agent --agent-id <AGENT_ID> --region us-east-1

# Check recent errors in logs
./scripts/check_cw_logs.sh | grep -i error
```

### Traces not appearing in X-Ray
- Verify agent was deployed successfully
- Wait 1-2 minutes after deployment for traces to appear
- Check CloudWatch Logs to verify agent is running

## Project Structure

```
07-simple-dual-observability/
├── agent/                    # Agent implementation
│   └── weather_time_agent.py
├── config/                   # Configuration files
│   ├── .env.example         # Template environment variables
│   └── otel_config.yaml     # OpenTelemetry collector config
├── docs/                     # Documentation
├── scripts/                  # Deployment & testing scripts
│   ├── check_cw_logs.sh     # CloudWatch logs viewer
│   ├── check_cw_metrics.sh  # Gateway metrics viewer
│   ├── setup_all.sh         # Full deployment
│   └── tests/               # Test scripts
├── tools/                    # Agent tools
└── README.md                # Main documentation
```

## Notes

- The CloudWatch dashboard (previously included) has been removed as the runtime does not emit standard CloudWatch Metrics for agent invocations
- Gateway operations (tool calls via MCP) ARE tracked in the `AWS/Bedrock-AgentCore` namespace and can be viewed with `check_cw_metrics.sh`
- For comprehensive observability, use X-Ray and CloudWatch Logs
- Braintrust provides the most detailed AI-specific metrics including LLM costs

## References

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/)
- [CloudWatch Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)
- [X-Ray Integration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-view.html)
- [Braintrust Platform](https://www.braintrust.dev)
