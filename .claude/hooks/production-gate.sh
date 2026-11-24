#!/bin/bash
# Production deploys require explicit RELEASE_APPROVAL authorization
cmd=$(jq -r '.tool_input.command' < /dev/stdin 2>/dev/null || cat)

if [[ "$cmd" == *"deploy"* && "$cmd" == *"production"* ]]; then
  if [ -z "$RELEASE_APPROVAL" ]; then
    echo "BLOCKED: Production deploys require explicit RELEASE_APPROVAL authorization." >&2
    exit 2 # Exit code 2 blocks the action and delivers the message to the agent
  fi
fi

exit 0
