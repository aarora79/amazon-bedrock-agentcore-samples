# CloudWatch Metrics Limitation - Important Note

## Current Status

After thorough investigation, we discovered that **Bedrock AgentCore Runtime does NOT emit standard CloudWatch Metrics API metrics** for agent invocations, despite what some documentation might suggest.

## What Actually Happens

The Bedrock AgentCore Runtime provides observability through:

### 1. CloudWatch Logs (Primary)
- Runtime logs are stored in: `/aws/bedrock-agentcore/runtimes/{AGENT_ID}-DEFAULT/`
- Contains detailed execution logs with timestamps
- **Use:** `./scripts/check_cw_logs.sh` to view these logs

### 2. AWS X-Ray Traces
- Distributed traces are automatically sent to X-Ray
- Shows complete execution flow with latency details
- **View:** CloudWatch Console → X-Ray → Traces

### 3. Braintrust (Optional)
- If BRAINTRUST_API_KEY is configured, traces are exported to Braintrust
- Provides AI-focused observability with LLM metrics
- **View:** https://www.braintrust.dev

### 4. Standard CloudWatch Metrics (Limited)
- **Gateway metrics only:** The `AWS/Bedrock-AgentCore` namespace contains metrics for AgentCore Gateway operations (tool calls, MCP protocol operations)
- **Agent metrics NOT included** in standard CloudWatch Metrics

## Why the Dashboard Appears Empty

The CloudWatch dashboard is configured to display agent invocation metrics (Invocations, Latency, Errors, etc.) in the `AWS/Bedrock-AgentCore` namespace. However, these specific metrics are NOT emitted by the runtime for direct agent invocations - only for gateway operations.

## Recommended Observability Approach

1. **For Development/Debugging:**
   - Use `./scripts/check_cw_logs.sh` to view agent logs
   - Review CloudWatch Logs Insights for detailed analysis

2. **For Monitoring:**
   - View X-Ray traces in CloudWatch console
   - Configure Braintrust for AI-specific observability

3. **For Metrics:**
   - Gateway operations ARE tracked in `AWS/Bedrock-AgentCore` namespace
   - For agent-level metrics, emit custom metrics or use Braintrust

## Future Improvements

If Bedrock AgentCore Runtime adds standard CloudWatch Metrics for agent invocations in the future:
1. Metrics will automatically appear in the `AWS/Bedrock-AgentCore` namespace
2. The dashboard will populate with real data
3. The scripts will work as designed

## Useful Commands

```bash
# View agent logs
./scripts/check_cw_logs.sh --last-30-min

# View gateway metrics (currently available)
./scripts/check_cw_metrics.sh --metric Invocations

# View all gateway metrics
./scripts/check_cw_metrics.sh --metric all

# View X-Ray traces
aws xray get-trace-summaries --start-time <timestamp> --end-time <timestamp>
```

## References

- [AWS Bedrock AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)
- [CloudWatch Logs for AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-logs.html)
- [X-Ray Integration](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-view.html)
