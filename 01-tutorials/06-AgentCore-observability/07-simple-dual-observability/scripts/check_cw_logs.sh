#!/bin/bash

# Script to display CloudWatch logs for the AgentCore agent
# Follows project standards for minimal complexity and clear naming

set -e

# Configuration
LOG_GROUP_NAME="/aws/bedrock-agentcore/runtimes/weather_time_observability_agent-dWTPGP46D4-DEFAULT"
DEFAULT_TIME_RANGE="3600000"  # 1 hour in milliseconds

# Function to display help message
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Display CloudWatch logs for the AgentCore observability agent.

OPTIONS:
    --last-hour      Show logs from last hour (default)
    --last-30-min    Show logs from last 30 minutes
    --last-24h       Show logs from last 24 hours
    --follow         Follow logs in real-time
    --help           Show this help message

EXAMPLES:
    # Show logs from last hour
    $(basename "$0")

    # Show logs from last 30 minutes
    $(basename "$0") --last-30-min

    # Follow logs in real-time
    $(basename "$0") --follow

EOF
}


# Function to get timestamp in milliseconds
get_timestamp_ms() {
    local time_offset=$1
    local current_time_ms=$(date +%s)000
    echo $((current_time_ms - time_offset))
}


# Function to display logs
display_logs() {
    local start_time=$1
    local end_time=$(date +%s)000

    echo "Fetching logs from log group: $LOG_GROUP_NAME"
    echo "Time range: $(date -d @$((start_time / 1000))) to $(date -d @$((end_time / 1000)))"
    echo "----------------------------------------"

    aws logs filter-log-events \
        --log-group-name "$LOG_GROUP_NAME" \
        --start-time "$start_time" \
        --end-time "$end_time" \
        --query 'events[*].[timestamp,message]' \
        --output text | while IFS=$'\t' read -r timestamp message; do
            local formatted_time=$(date -d @$((timestamp / 1000)) '+%Y-%m-%d %H:%M:%S')
            echo "[$formatted_time] $message"
        done
}


# Function to follow logs in real-time
follow_logs() {
    echo "Following logs from log group: $LOG_GROUP_NAME"
    echo "Press Ctrl+C to stop"
    echo "----------------------------------------"

    local last_timestamp=$(date +%s)000

    while true; do
        local current_time=$(date +%s)000

        aws logs filter-log-events \
            --log-group-name "$LOG_GROUP_NAME" \
            --start-time "$last_timestamp" \
            --end-time "$current_time" \
            --query 'events[*].[timestamp,message]' \
            --output text | while IFS=$'\t' read -r timestamp message; do
                if [ -n "$timestamp" ]; then
                    local formatted_time=$(date -d @$((timestamp / 1000)) '+%Y-%m-%d %H:%M:%S')
                    echo "[$formatted_time] $message"
                fi
            done

        last_timestamp=$current_time
        sleep 2
    done
}


# Parse command line arguments
TIME_RANGE="$DEFAULT_TIME_RANGE"
FOLLOW_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --last-hour)
            TIME_RANGE="3600000"  # 1 hour
            shift
            ;;
        --last-30-min)
            TIME_RANGE="1800000"  # 30 minutes
            shift
            ;;
        --last-24h)
            TIME_RANGE="86400000"  # 24 hours
            shift
            ;;
        --follow)
            FOLLOW_MODE=true
            shift
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

# Execute based on mode
if [ "$FOLLOW_MODE" = true ]; then
    follow_logs
else
    START_TIME=$(get_timestamp_ms "$TIME_RANGE")
    display_logs "$START_TIME"
fi
