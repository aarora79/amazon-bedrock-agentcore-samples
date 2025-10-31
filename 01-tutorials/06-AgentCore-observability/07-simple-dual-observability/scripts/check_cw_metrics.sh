#!/bin/bash

# Script to display CloudWatch metrics for the AgentCore agent
# Follows project standards for minimal complexity and clear naming

set -e

# Configuration
NAMESPACE="AWS/Bedrock-AgentCore"
AGENT_ID="dWTPGP46D4"
DEFAULT_TIME_RANGE="3600"  # 1 hour in seconds
DEFAULT_METRIC="Invocations"
DEFAULT_STAT="Sum"

# Available metrics
AVAILABLE_METRICS=("Invocations" "Latency" "SystemErrors" "UserErrors" "Throttles")
AVAILABLE_STATS=("Sum" "Average" "Maximum" "Minimum" "SampleCount")

# Function to display help message
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Display CloudWatch metrics for the AgentCore observability agent.

OPTIONS:
    --last-hour      Show metrics from last hour (default)
    --last-30-min    Show metrics from last 30 minutes
    --last-24h       Show metrics from last 24 hours
    --metric NAME    Specify metric name (default: Invocations)
                     Available: Invocations, Latency, SystemErrors, UserErrors, Throttles
    --stat TYPE      Specify statistic (default: Sum)
                     Available: Sum, Average, Maximum, Minimum, SampleCount
    --help           Show this help message

EXAMPLES:
    # Show invocations from last hour
    $(basename "$0")

    # Show average latency from last 30 minutes
    $(basename "$0") --last-30-min --metric Latency --stat Average

    # Show system errors from last 24 hours
    $(basename "$0") --last-24h --metric SystemErrors

    # Show all available metrics
    $(basename "$0") --metric all

EOF
}


# Function to validate metric name
validate_metric() {
    local metric=$1

    if [ "$metric" = "all" ]; then
        return 0
    fi

    for valid_metric in "${AVAILABLE_METRICS[@]}"; do
        if [ "$metric" = "$valid_metric" ]; then
            return 0
        fi
    done

    echo "Error: Invalid metric name: $metric"
    echo "Available metrics: ${AVAILABLE_METRICS[*]}"
    exit 1
}


# Function to validate statistic
validate_stat() {
    local stat=$1

    for valid_stat in "${AVAILABLE_STATS[@]}"; do
        if [ "$stat" = "$valid_stat" ]; then
            return 0
        fi
    done

    echo "Error: Invalid statistic: $stat"
    echo "Available statistics: ${AVAILABLE_STATS[*]}"
    exit 1
}


# Function to get timestamp in ISO 8601 format
get_timestamp_iso() {
    local seconds_offset=$1
    date -u -d "-${seconds_offset} seconds" '+%Y-%m-%dT%H:%M:%S'
}


# Function to display single metric
display_metric() {
    local metric_name=$1
    local stat_type=$2
    local start_time=$3
    local end_time=$4
    local period=$5

    echo "Fetching metric: $metric_name ($stat_type)"
    echo "Namespace: $NAMESPACE"
    echo "Agent ID: $AGENT_ID"
    echo "Time range: $start_time to $end_time"
    echo "----------------------------------------"

    local result=$(aws cloudwatch get-metric-statistics \
        --namespace "$NAMESPACE" \
        --metric-name "$metric_name" \
        --dimensions Name=AgentId,Value="$AGENT_ID" \
        --start-time "$start_time" \
        --end-time "$end_time" \
        --period "$period" \
        --statistics "$stat_type" \
        --output json)

    local datapoints=$(echo "$result" | jq -r '.Datapoints | length')

    if [ "$datapoints" -eq 0 ]; then
        echo "No data points found for this metric in the specified time range."
        echo ""
        return
    fi

    echo "$result" | jq -r '.Datapoints | sort_by(.Timestamp) | .[] |
        "\(.Timestamp) | \(if .Sum then .Sum elif .Average then .Average elif .Maximum then .Maximum elif .Minimum then .Minimum else .SampleCount end) | \(.Unit)"' | \
        while IFS='|' read -r timestamp value unit; do
            local formatted_time=$(date -d "$timestamp" '+%Y-%m-%d %H:%M:%S')
            printf "[%s] %s: %.2f %s\n" "$formatted_time" "$stat_type" "$value" "$unit"
        done

    # Display summary
    echo ""
    echo "Summary:"
    local total=$(echo "$result" | jq -r "[.Datapoints[].${stat_type}] | add")
    local count=$(echo "$result" | jq -r ".Datapoints | length")
    local avg=$(echo "$result" | jq -r "[.Datapoints[].${stat_type}] | add / length")

    if [ "$total" != "null" ]; then
        printf "Total: %.2f\n" "$total"
        printf "Average: %.2f\n" "$avg"
        printf "Data points: %d\n" "$count"
    fi

    echo ""
}


# Function to display all metrics
display_all_metrics() {
    local stat_type=$1
    local start_time=$2
    local end_time=$3
    local period=$4

    echo "Fetching ALL metrics"
    echo "Namespace: $NAMESPACE"
    echo "Agent ID: $AGENT_ID"
    echo "Time range: $start_time to $end_time"
    echo "========================================"
    echo ""

    for metric in "${AVAILABLE_METRICS[@]}"; do
        display_metric "$metric" "$stat_type" "$start_time" "$end_time" "$period"
    done
}


# Parse command line arguments
TIME_RANGE="$DEFAULT_TIME_RANGE"
METRIC_NAME="$DEFAULT_METRIC"
STAT_TYPE="$DEFAULT_STAT"

while [[ $# -gt 0 ]]; do
    case $1 in
        --last-hour)
            TIME_RANGE="3600"  # 1 hour
            shift
            ;;
        --last-30-min)
            TIME_RANGE="1800"  # 30 minutes
            shift
            ;;
        --last-24h)
            TIME_RANGE="86400"  # 24 hours
            shift
            ;;
        --metric)
            METRIC_NAME="$2"
            shift 2
            ;;
        --stat)
            STAT_TYPE="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate inputs
if [ "$METRIC_NAME" != "all" ]; then
    validate_metric "$METRIC_NAME"
fi
validate_stat "$STAT_TYPE"

# Calculate time range
START_TIME=$(get_timestamp_iso "$TIME_RANGE")
END_TIME=$(date -u '+%Y-%m-%dT%H:%M:%S')

# Calculate appropriate period based on time range
if [ "$TIME_RANGE" -le 3600 ]; then
    PERIOD=300  # 5 minutes for 1 hour or less
elif [ "$TIME_RANGE" -le 86400 ]; then
    PERIOD=3600  # 1 hour for 24 hours
else
    PERIOD=86400  # 1 day for longer ranges
fi

# Execute based on metric selection
if [ "$METRIC_NAME" = "all" ]; then
    display_all_metrics "$STAT_TYPE" "$START_TIME" "$END_TIME" "$PERIOD"
else
    display_metric "$METRIC_NAME" "$STAT_TYPE" "$START_TIME" "$END_TIME" "$PERIOD"
fi
