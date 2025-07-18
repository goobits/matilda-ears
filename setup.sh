#!/bin/bash
# STT Setup Script - Uses the Generic Setup Framework

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define the path to the framework script
FRAMEWORK_SCRIPT="$SCRIPT_DIR/src/shared-setup/setup.sh"

# Check if the framework exists in the project
if [[ ! -f "$FRAMEWORK_SCRIPT" ]]; then
    echo "❌ Setup framework not found in this project's 'src/shared-setup' directory."
    echo "Please ensure the framework has been synced to this project."
    exit 1
fi

# Check if the configuration file exists
if [[ ! -f "$SCRIPT_DIR/setup-config.yaml" ]]; then
    echo "❌ Configuration file setup-config.yaml not found."
    exit 1
fi

# Execute the generic setup framework, passing along all arguments
exec "$FRAMEWORK_SCRIPT" "$@"