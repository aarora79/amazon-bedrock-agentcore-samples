# Gateway Mode Quick Start Guide

This guide shows you how to quickly deploy and test the Gateway mode.

## Prerequisites

- AWS credentials configured
- Docker installed
- Python 3.11+
- IAM permissions for Lambda, Bedrock, and AgentCore

## Quick Deploy (5 Minutes)

### Option 1: Unified Deployment (Recommended)

Deploy everything with a single command:

```bash
# Deploy Lambda functions, configure Gateway, and deploy agent
./scripts/deploy_with_gateway.sh --use-gateway true --region us-east-1
```

This will:
1. ✅ Deploy 3 Lambda functions (weather, time, calculator)
2. ✅ Setup Cognito OAuth (for Gateway authentication)
3. ✅ Create AgentCore Gateway
4. ✅ Register Lambda targets
5. ✅ Deploy agent with Gateway mode enabled

### Option 2: Step-by-Step Deployment

Deploy each component separately:

```bash
# Step 1: Deploy Lambda functions (2 min)
cd scripts
python deploy_lambdas.py --region us-east-1

# Step 2: Setup Cognito OAuth (1 min)
python setup_cognito.py --region us-east-1

# Step 3: Configure Gateway (1 min)
python configure_gateway.py --region us-east-1

# Step 4: Deploy agent with Gateway mode (2 min)
export USE_GATEWAY=true
export GATEWAY_ARN=$(python -c "import json; print(json.load(open('.gateway_config.json'))['gateway']['gateway_arn'])")
python deploy_agent.py --region us-east-1
```

## Test the Deployment

Run test scenarios:

```bash
# Test successful multi-tool query
python simple_observability.py --scenario success

# Test error handling
python simple_observability.py --scenario error

# Run all scenarios
python simple_observability.py --scenario all
```

## Verify Gateway Mode

Check agent logs to confirm Gateway mode:

```bash
# View logs
./scripts/check_logs.sh

# Look for these messages:
# "Gateway mode enabled: arn:aws:bedrock:..."
# "Invoking gateway tool: get_weather"
```

Check Lambda execution:

```bash
# View Lambda logs
aws logs tail /aws/lambda/agentcore-weather-tool --follow
aws logs tail /aws/lambda/agentcore-time-tool --follow
aws logs tail /aws/lambda/agentcore-calculator-tool --follow
```

## Compare with Local Mode

Switch to local mode and compare:

```bash
# Deploy with local tools
export USE_GATEWAY=false
./scripts/deploy_agent.sh --auto-update-on-conflict

# Run same test
python simple_observability.py --scenario success

# Note: Local mode is faster (no Lambda cold start)
# Gateway mode scales better for production
```

## Environment Variables

Set these in `.env` file:

```bash
# Copy template
cp .env.example .env

# Edit .env
USE_GATEWAY=true
GATEWAY_ARN=arn:aws:bedrock:us-east-1:123456789012:gateway/abc123
AWS_REGION=us-east-1

# Optional: Add Braintrust for dual observability
BRAINTRUST_API_KEY=your-api-key
BRAINTRUST_PROJECT_ID=your-project-id
```

## Troubleshooting

### Issue: Lambda deployment fails

**Solution:**
```bash
# Check IAM permissions
aws iam get-user
aws lambda list-functions

# Verify role exists
aws iam get-role --role-name agentcore-gateway-lambda-role
```

### Issue: Gateway not found

**Solution:**
```bash
# Check Gateway configuration
cat scripts/.gateway_config.json

# List Gateways
aws bedrock-agent list-gateways --region us-east-1
```

### Issue: Agent can't invoke Gateway

**Solution:**
```bash
# Verify GATEWAY_ARN is set
echo $GATEWAY_ARN

# Check agent environment variables in AWS Console
# AgentCore Runtime → Agents → Your Agent → Environment Variables
```

### Issue: High latency

**Cause:** Lambda cold starts (first invocation ~2-3 seconds)

**Solutions:**
1. Use Lambda provisioned concurrency (costs more)
2. Switch to local mode for development
3. Use Gateway mode only for production

## What's Deployed?

After successful Gateway deployment:

**Lambda Functions:**
- `agentcore-weather-tool` → Gets weather data
- `agentcore-time-tool` → Gets time/timezone info
- `agentcore-calculator-tool` → Performs calculations

**AgentCore Gateway:**
- Gateway ID and ARN in `.gateway_config.json`
- 3 registered targets with tool specifications

**Agent Runtime:**
- Agent with Gateway mode enabled
- Environment variables: USE_GATEWAY=true, GATEWAY_ARN=...

## Cleanup

Remove all Gateway resources:

```bash
# Delete agent
python scripts/delete_agent.py

# Delete Lambda functions
aws lambda delete-function --function-name agentcore-weather-tool
aws lambda delete-function --function-name agentcore-time-tool
aws lambda delete-function --function-name agentcore-calculator-tool

# Delete IAM role (after detaching policies)
aws iam detach-role-policy \
  --role-name agentcore-gateway-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam delete-role --role-name agentcore-gateway-lambda-role

# Delete Gateway (via AWS Console)
# Bedrock → AgentCore → Gateways → Delete
```

## Performance Comparison

| Metric | Local Tools | Gateway Tools |
|--------|-------------|---------------|
| **Cold Start** | 0s | 1-3s |
| **Warm Latency** | 50-100ms | 100-200ms |
| **Scaling** | Limited to agent container | Auto-scales per tool |
| **Cost** | Agent runtime only | Agent + Lambda + Gateway |
| **Best For** | Development, low traffic | Production, high traffic |

## Architecture

```
Local Tools:
Client → Agent Container → Tools (in-process)

Gateway Tools:
Client → Agent Container → Gateway → Lambda Functions
```

## Next Steps

1. **Monitor Performance:**
   - CloudWatch dashboards
   - Lambda metrics (invocations, duration, errors)
   - Gateway metrics

2. **Optimize Costs:**
   - Set Lambda reserved concurrency
   - Use Lambda provisioned concurrency for hot tools
   - Monitor Gateway invocation patterns

3. **Scale Up:**
   - Add more tools as Lambda functions
   - Configure Lambda timeout/memory per tool
   - Set up CloudWatch alarms

## Support

- Full documentation: `README.md`
- Test checklist: `.scratchpad/test-checklist.md`
- Implementation details: `.scratchpad/implementation-summary.md`
- Troubleshooting guide: `docs/troubleshooting.md`

## Validation

Run validation script to check setup:

```bash
python scripts/validate_setup.py
```

Expected output:
```
✓ ALL CHECKS PASSED - Implementation is ready!
```

---

**Quick Summary:**
- ⚡ Deploy: `./scripts/deploy_with_gateway.sh --use-gateway true`
- 🧪 Test: `python simple_observability.py --scenario all`
- 📊 Monitor: `./scripts/check_logs.sh`
- 🔄 Switch modes: Change `USE_GATEWAY` and redeploy
