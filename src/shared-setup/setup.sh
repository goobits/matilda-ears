#!/bin/bash
# Generic Setup Framework for Python Projects
# This script provides a robust, performant setup system with extensive validation

set -e

# Enable performance optimizations
export LC_ALL=C
export LANG=C

# Prevent Python bytecode generation during development
export PYTHONDONTWRITEBYTECODE=1

# Core configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Support being called from wrapper script or directly
if [[ -f "$SCRIPT_DIR/../../setup-config.yaml" ]]; then
    # Called from shared-setup directory
    readonly PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"  # Go up two levels: shared-setup -> ttt -> project root
elif [[ -f "$(pwd)/setup-config.yaml" ]]; then
    # Called from project root via wrapper
    readonly PROJECT_DIR="$(pwd)"
else
    # Fallback to calculated path
    readonly PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
fi

readonly CONFIG_FILE="$PROJECT_DIR/setup-config.yaml"
readonly CACHE_DIR="$HOME/.cache/setup-framework"
readonly CACHE_FILE="$CACHE_DIR/system-info.cache"
readonly CACHE_TTL=3600  # 1 hour in seconds

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Check if terminal supports colors
if [[ -t 1 ]] && [[ "$(tput colors 2>/dev/null)" -ge 8 ]]; then
    USE_COLOR=true
else
    USE_COLOR=false
fi

# Logging functions
log_info() {
    if [[ "$USE_COLOR" == "true" ]]; then
        echo -e "${BLUE}ℹ️  $1${NC}"
    else
        echo "[INFO] $1"
    fi
}

log_success() {
    if [[ "$USE_COLOR" == "true" ]]; then
        echo -e "${GREEN}✅ $1${NC}"
    else
        echo "[SUCCESS] $1"
    fi
}

log_warning() {
    if [[ "$USE_COLOR" == "true" ]]; then
        echo -e "${YELLOW}⚠️  $1${NC}"
    else
        echo "[WARNING] $1"
    fi
}

log_error() {
    if [[ "$USE_COLOR" == "true" ]]; then
        echo -e "${RED}❌ $1${NC}"
    else
        echo "[ERROR] $1"
    fi
}

log_debug() {
    if [[ "${DEBUG:-}" == "1" ]]; then
        echo -e "${NC}🔍 DEBUG: $1${NC}" >&2
    fi
    return 0
}

# Create cache directory if it doesn't exist
mkdir -p "$CACHE_DIR"

# Function to get cached system information
get_cached_value() {
    local key="$1"
    local current_time=$(date +%s)
    
    if [[ -f "$CACHE_FILE" ]]; then
        local cache_time=$(stat -c %Y "$CACHE_FILE" 2>/dev/null || stat -f %m "$CACHE_FILE" 2>/dev/null || echo 0)
        local age=$((current_time - cache_time))
        
        if [[ $age -lt $CACHE_TTL ]]; then
            grep "^$key=" "$CACHE_FILE" 2>/dev/null | cut -d'=' -f2- || true
        fi
    fi
}

# Function to set cached value
set_cached_value() {
    local key="$1"
    local value="$2"
    
    # Remove old value if exists
    if [[ -f "$CACHE_FILE" ]]; then
        grep -v "^$key=" "$CACHE_FILE" > "$CACHE_FILE.tmp" 2>/dev/null || true
        mv "$CACHE_FILE.tmp" "$CACHE_FILE"
    fi
    
    # Add new value
    echo "$key=$value" >> "$CACHE_FILE"
}

# Parse YAML configuration using Python and PyYAML
parse_yaml() {
    local yaml_file="$1"
    
    log_debug "Starting parse_yaml for file: $yaml_file"
    
    # Check if PyYAML is available
    if ! python3 -c "import yaml" 2>/dev/null; then
        log_error "PyYAML not found. Please install it to continue."
        echo
        echo "To install PyYAML, run one of:"
        echo "  pip install PyYAML"
        echo "  pip3 install PyYAML"
        echo "  python3 -m pip install PyYAML"
        echo
        return 1
    fi
    
    # Convert YAML to JSON using Python
    local json_output
    if ! json_output=$(python3 -c 'import yaml, json, sys; print(json.dumps(yaml.safe_load(sys.stdin)))' < "$yaml_file" 2>&1); then
        log_error "Failed to parse YAML file: $yaml_file"
        log_debug "Error output: $json_output"
        return 1
    fi
    
    # Return the JSON output
    echo "$json_output"
    return 0
}

# Load configuration
load_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "Configuration file not found: $CONFIG_FILE"
        exit 1
    fi
    
    # Check for jq before proceeding
    if ! command -v jq &> /dev/null; then
        check_jq
        exit 1
    fi
    
    log_info "Loading configuration from $CONFIG_FILE"
    log_debug "Config file path: $CONFIG_FILE"
    
    # Parse YAML to JSON
    local config_json
    if ! config_json=$(parse_yaml "$CONFIG_FILE"); then
        log_error "Failed to parse configuration file"
        exit 1
    fi
    
    # Export top-level keys as CONFIG_* variables
    local keys
    keys=$(echo "$config_json" | jq -r 'keys[]' 2>/dev/null) || {
        log_error "Failed to extract keys from configuration"
        exit 1
    }
    
    # Process each key
    while IFS= read -r key; do
        local value
        value=$(echo "$config_json" | jq -r --arg k "$key" '.[$k]' 2>/dev/null)
        
        # Skip null, arrays, and objects (handle them separately)
        if [[ "$value" != "null" && "$value" != "["* && "$value" != "{"* ]]; then
            export "CONFIG_${key}=${value}"
            log_debug "Exported: CONFIG_${key}=${value}"
        fi
        
        # Handle nested objects (one level deep)
        local value_type
        value_type=$(echo "$config_json" | jq -r --arg k "$key" '.[$k] | type' 2>/dev/null)
        
        if [[ "$value_type" == "object" ]]; then
            local nested_keys
            nested_keys=$(echo "$config_json" | jq -r --arg k "$key" '.[$k] | keys[]' 2>/dev/null) || continue
            
            while IFS= read -r nested_key; do
                local nested_value
                nested_value=$(echo "$config_json" | jq -r --arg k "$key" --arg nk "$nested_key" '.[$k][$nk]' 2>/dev/null)
                
                # Only export non-null, non-object, non-array values
                if [[ "$nested_value" != "null" && "$nested_value" != "["* && "$nested_value" != "{"* ]]; then
                    export "CONFIG_${key}_${nested_key}=${nested_value}"
                    log_debug "Exported: CONFIG_${key}_${nested_key}=${nested_value}"
                fi
            done <<< "$nested_keys"
        fi
    done <<< "$keys"
    
    # Debug: Show loaded configuration
    if [[ "${DEBUG:-}" == "1" ]]; then
        log_debug "Loaded configuration variables:"
        # Use grep with || true to prevent exit on no matches
        env | grep "^CONFIG_" 2>/dev/null | while read -r var; do
            log_debug "  $var"
        done || true
    fi
    
    # Validate required configuration
    if [[ -z "${CONFIG_package_name:-}" ]]; then
        log_error "Missing required configuration: package_name"
        exit 1
    fi
}

# System requirement checks
check_python_version() {
    local required_version="${CONFIG_python_minimum_version:-3.8}"
    
    log_info "Checking Python version (required: >= $required_version)"
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        return 1
    fi
    
    local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= tuple(map(int, '$required_version'.split('.'))) else 1)"; then
        log_error "Python $python_version is installed, but >= $required_version is required"
        return 1
    fi
    
    log_success "Python $python_version meets requirements"
    return 0
}

check_pipx() {
    log_info "Checking for pipx installation"
    
    if ! command -v pipx &> /dev/null; then
        log_error "pipx is not installed"
        echo
        echo "pipx is required for clean, isolated installations."
        echo
        echo "To install pipx:"
        echo "  Option 1 (recommended):"
        echo "    python3 -m pip install --user pipx"
        echo "    python3 -m pipx ensurepath"
        echo
        echo "  Option 2 (Ubuntu/Debian):"
        echo "    sudo apt update"
        echo "    sudo apt install pipx"
        echo "    pipx ensurepath"
        echo
        echo "  Option 3 (macOS with Homebrew):"
        echo "    brew install pipx"
        echo "    pipx ensurepath"
        echo
        echo "After installation, restart your terminal or run:"
        echo "    source ~/.bashrc  # or ~/.zshrc"
        return 1
    fi
    
    # Check if pipx is in PATH
    if ! pipx --version &> /dev/null; then
        log_warning "pipx is installed but may not be in PATH"
        echo "Run: pipx ensurepath"
        echo "Then restart your terminal"
        return 1
    fi
    
    log_success "pipx is installed"
    return 0
}

check_git() {
    log_info "Checking for git"
    
    if ! command -v git &> /dev/null; then
        log_error "git is not installed"
        return 1
    fi
    
    log_success "git is installed"
    return 0
}

check_jq() {
    log_info "Checking for jq"
    
    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed"
        echo
        echo "jq is required for JSON processing."
        echo
        echo "To install jq:"
        echo "  Option 1 (Ubuntu/Debian):"
        echo "    sudo apt update"
        echo "    sudo apt install jq"
        echo
        echo "  Option 2 (macOS with Homebrew):"
        echo "    brew install jq"
        echo
        echo "  Option 3 (Download binary):"
        echo "    Visit: https://stedolan.github.io/jq/download/"
        echo
        return 1
    fi
    
    log_success "jq is installed"
    return 0
}

check_disk_space() {
    local required_mb="${CONFIG_validation_minimum_disk_space_mb:-100}"
    
    if [[ "${CONFIG_validation_check_disk_space:-true}" != "true" ]]; then
        return 0
    fi
    
    log_info "Checking disk space (required: ${required_mb}MB)"
    
    # Get available space in KB, handle both GNU and BSD stat
    local available_kb
    if available_kb=$(df . 2>/dev/null | tail -1 | awk '{print $4}'); then
        local available_mb=$((available_kb / 1024))
        
        if [[ $available_mb -lt $required_mb ]]; then
            log_error "Insufficient disk space: ${available_mb}MB available, ${required_mb}MB required"
            return 1
        fi
        
        log_success "Sufficient disk space: ${available_mb}MB available"
    else
        log_warning "Could not check disk space - continuing anyway"
    fi
    
    return 0
}

# Local dependency management functions

# Validates that a given path is a valid, installable Python project
validate_local_repo() {
    local repo_path="$1"
    if [[ ! -d "$repo_path" || (! -f "$repo_path/pyproject.toml" && ! -f "$repo_path/setup.py") ]]; then
        return 1
    fi
    return 0
}

# Auto-detects local repositories based on the development_dependencies config
auto_detect_local_repos() {
    log_info "Auto-detecting local repositories..."
    
    local config_json
    if ! config_json=$(parse_yaml "$CONFIG_FILE"); then
        log_error "Failed to parse configuration for local repo detection"
        return 1
    fi
    
    # Check if development_dependencies section exists
    local dev_deps_exist
    dev_deps_exist=$(echo "$config_json" | jq -r 'has("development_dependencies")' 2>/dev/null)
    
    if [[ "$dev_deps_exist" != "true" ]]; then
        log_debug "No development_dependencies section found in config"
        return 0
    fi
    
    # Get list of dependency names
    local dep_names
    dep_names=$(echo "$config_json" | jq -r '.development_dependencies | keys[]' 2>/dev/null) || {
        log_debug "No development dependencies configured"
        return 0
    }
    
    local found_repos=()
    local missing_repos=()
    
    # Process each dependency
    while IFS= read -r dep_name; do
        local local_path
        local_path=$(echo "$config_json" | jq -r --arg dep "$dep_name" '.development_dependencies[$dep].local_path' 2>/dev/null)
        
        if [[ "$local_path" != "null" && -n "$local_path" ]]; then
            # Convert relative path to absolute if needed
            if [[ ! "$local_path" =~ ^/ ]]; then
                local_path="$PROJECT_DIR/$local_path"
            fi
            
            log_debug "Checking for $dep_name at: $local_path"
            
            if validate_local_repo "$local_path"; then
                log_success "Found local repo: $dep_name at $local_path"
                found_repos+=("$dep_name:$local_path")
            else
                log_warning "Missing local repo: $dep_name (expected at $local_path)"
                missing_repos+=("$dep_name")
            fi
        fi
    done <<< "$dep_names"
    
    # Export results for use by other functions
    export FOUND_LOCAL_REPOS="${found_repos[@]}"
    export MISSING_LOCAL_REPOS="${missing_repos[@]}"
    
    if [[ ${#found_repos[@]} -gt 0 ]]; then
        log_info "Found ${#found_repos[@]} local repositories"
    fi
    
    if [[ ${#missing_repos[@]} -gt 0 ]]; then
        log_info "Missing ${#missing_repos[@]} local repositories"
        return 2  # Special return code to indicate missing repos
    fi
    
    return 0
}

# Interactively handles missing local repositories
handle_missing_repos() {
    local missing_repos_list="$1"
    
    if [[ -z "$missing_repos_list" ]]; then
        return 0
    fi
    
    echo
    echo "=== Missing Local Repositories ==="
    echo "The following local repositories were not found:"
    echo
    
    local repos_array=($missing_repos_list)
    for repo in "${repos_array[@]}"; do
        echo "  • $repo"
    done
    
    echo
    echo "What would you like to do?"
    echo "  1) Clone missing repositories automatically"
    echo "  2) Use PyPI versions instead (fallback)"
    echo "  3) Continue without these dependencies"
    echo "  4) Exit and handle manually"
    echo
    
    local choice
    while true; do
        read -p "Please choose (1-4): " choice
        case $choice in
            1)
                log_info "Will clone missing repositories..."
                export CLONE_MISSING_REPOS="${missing_repos_list}"
                return 0
                ;;
            2)
                log_info "Will use PyPI versions for missing repositories"
                return 0
                ;;
            3)
                log_warning "Continuing without missing dependencies"
                return 0
                ;;
            4)
                log_info "Exiting for manual handling"
                exit 0
                ;;
            *)
                echo "Invalid choice. Please select 1-4."
                ;;
        esac
    done
}

# Clones repositories from git URLs defined in the config
clone_missing_repos() {
    local repos_to_clone="$1"
    
    if [[ -z "$repos_to_clone" ]]; then
        return 0
    fi
    
    local config_json
    if ! config_json=$(parse_yaml "$CONFIG_FILE"); then
        log_error "Failed to parse configuration for repo cloning"
        return 1
    fi
    
    local repos_array=($repos_to_clone)
    local cloned_repos=()
    
    for repo in "${repos_array[@]}"; do
        log_info "Cloning $repo..."
        
        local git_url
        git_url=$(echo "$config_json" | jq -r --arg dep "$repo" '.development_dependencies[$dep].git_url' 2>/dev/null)
        
        local local_path
        local_path=$(echo "$config_json" | jq -r --arg dep "$repo" '.development_dependencies[$dep].local_path' 2>/dev/null)
        
        if [[ "$git_url" == "null" || -z "$git_url" ]]; then
            log_error "No git_url configured for $repo"
            continue
        fi
        
        if [[ "$local_path" == "null" || -z "$local_path" ]]; then
            log_error "No local_path configured for $repo"
            continue
        fi
        
        # Convert relative path to absolute if needed
        if [[ ! "$local_path" =~ ^/ ]]; then
            local_path="$PROJECT_DIR/$local_path"
        fi
        
        # Create parent directory if needed
        local parent_dir
        parent_dir=$(dirname "$local_path")
        if [[ ! -d "$parent_dir" ]]; then
            log_info "Creating directory: $parent_dir"
            mkdir -p "$parent_dir" || {
                log_error "Failed to create directory: $parent_dir"
                continue
            }
        fi
        
        # Clone the repository
        if git clone "$git_url" "$local_path"; then
            log_success "Cloned $repo to $local_path"
            cloned_repos+=("$repo:$local_path")
        else
            log_error "Failed to clone $repo from $git_url"
        fi
    done
    
    # Update found repos list with newly cloned repos
    if [[ ${#cloned_repos[@]} -gt 0 ]]; then
        export FOUND_LOCAL_REPOS="${FOUND_LOCAL_REPOS} ${cloned_repos[@]}"
    fi
    
    return 0
}

# Prepares all development dependencies found via auto-detection
prepare_dev_dependencies() {
    local auto_detect="${1:-false}"
    local explicit_deps="${2:-}"
    
    log_debug "Preparing development dependencies (auto_detect=$auto_detect)"
    
    if [[ "$auto_detect" == "true" ]]; then
        auto_detect_local_repos
        local detect_result=$?
        
        if [[ $detect_result -eq 2 ]]; then
            # Missing repos found
            handle_missing_repos "$MISSING_LOCAL_REPOS"
            
            # Clone repos if user chose to
            if [[ -n "${CLONE_MISSING_REPOS:-}" ]]; then
                clone_missing_repos "$CLONE_MISSING_REPOS"
            fi
        fi
    fi
    
    # Process explicit dependencies if provided
    if [[ -n "$explicit_deps" ]]; then
        log_info "Processing explicit local dependencies: $explicit_deps"
        # Parse comma-separated paths
        IFS=',' read -ra DEP_PATHS <<< "$explicit_deps"
        for path in "${DEP_PATHS[@]}"; do
            path=$(echo "$path" | xargs) # trim whitespace
            if validate_local_repo "$path"; then
                log_success "Valid local repo: $path"
                export FOUND_LOCAL_REPOS="${FOUND_LOCAL_REPOS} explicit:$path"
            else
                log_error "Invalid local repo: $path (missing pyproject.toml or setup.py)"
                return 1
            fi
        done
    fi
    
    # Build pip arguments for found repositories
    if [[ -n "${FOUND_LOCAL_REPOS:-}" ]]; then
        local pip_args=""
        local repos_array=($FOUND_LOCAL_REPOS)
        
        for repo_entry in "${repos_array[@]}"; do
            local repo_path="${repo_entry#*:}"  # Extract path after colon
            pip_args+="--editable \"$repo_path\" "
        done
        
        # Remove trailing space
        pip_args="${pip_args% }"
        
        log_info "Prepared pip arguments for local dependencies"
        log_debug "PIPX_CUSTOM_PIP_ARGS: $pip_args"
        export PIPX_CUSTOM_PIP_ARGS="$pip_args"
    fi
    
    return 0
}

# Installation functions
install_with_pipx() {
    local dev_mode="${1:-false}"
    
    log_info "Installing ${CONFIG_package_name} with pipx"
    
    if ! check_pipx; then
        return 1
    fi
    
    # Check if already installed
    if pipx list | grep -q "${CONFIG_package_name}"; then
        echo
        echo "=== Package Already Installed ==="
        log_warning "${CONFIG_package_name} is already installed with pipx"
        echo
        echo "Available options:"
        echo "  • To upgrade:   $0 upgrade"
        echo "  • To reinstall: $0 uninstall && $0 install"
        echo "  • To check status: $0 status"
        echo "================================="
        return 1
    fi
    
    # Install based on mode
    if [[ "$dev_mode" == "true" ]]; then
        log_info "Installing in development mode (editable)"
        # For development mode, check if we need to use parent directory
        local install_dir="$PROJECT_DIR"
        if [[ ! -f "$PROJECT_DIR/pyproject.toml" && ! -f "$PROJECT_DIR/setup.py" ]]; then
            # Check parent directory
            local parent_dir="$(dirname "$PROJECT_DIR")"
            if [[ -f "$parent_dir/pyproject.toml" || -f "$parent_dir/setup.py" ]]; then
                install_dir="$parent_dir"
                log_info "Using parent directory for installation: $install_dir"
            fi
        fi
        
        # Build pipx command with custom pip args if set
        local pipx_cmd_array=("pipx" "install")
        local pip_args_string=""
        
        # Combine default and custom pip args
        if [[ -n "${PIPX_DEFAULT_PIP_ARGS:-}" ]]; then
            pip_args_string+="${PIPX_DEFAULT_PIP_ARGS} "
        fi
        if [[ -n "${PIPX_CUSTOM_PIP_ARGS:-}" ]]; then
            pip_args_string+="${PIPX_CUSTOM_PIP_ARGS}"
        fi
        
        # Add to the command array if the string is not empty
        if [[ -n "$pip_args_string" ]]; then
            # Remove trailing space
            pip_args_string="${pip_args_string% }"
            pipx_cmd_array+=("--pip-args=${pip_args_string}")
        fi
        
        pipx_cmd_array+=("--editable" "$install_dir")
        
        # Execute the command safely using the array
        if ! "${pipx_cmd_array[@]}" 2>&1 | tee /tmp/pipx_install_dev.log; then
            log_error "Failed to install ${CONFIG_package_name} in development mode"
            
            # Check for common development installation errors
            if grep -q "does not appear to be a Python project" /tmp/pipx_install_dev.log; then
                echo
                log_error "Not a valid Python project"
                echo "Make sure the directory contains one of:"
                echo "  - pyproject.toml"
                echo "  - setup.py"
                echo "  - setup.cfg"
                echo
                echo "Current directory: $install_dir"
                if [[ -f "$install_dir/pyproject.toml" ]]; then
                    log_success "Found pyproject.toml"
                else
                    log_warning "No pyproject.toml found"
                fi
            elif grep -q "ModuleNotFoundError\|ImportError" /tmp/pipx_install_dev.log; then
                echo
                log_error "Missing dependencies detected"
                echo "Try installing dependencies first:"
                echo "  cd $install_dir"
                echo "  pip install -e ."
            fi
            
            rm -f /tmp/pipx_install_dev.log
            return 1
        fi
        rm -f /tmp/pipx_install_dev.log
    else
        log_info "Installing from PyPI"
        
        # First check if package exists on PyPI
        log_info "Checking if '${CONFIG_package_name}' is available on PyPI..."
        
        # Use pip index to check if package exists
        if ! pip index versions "${CONFIG_package_name}" &>/dev/null; then
            log_warning "Package '${CONFIG_package_name}' not found on PyPI"
            echo
            echo "This package hasn't been published to PyPI yet."
            echo "For local development, use:"
            echo
            echo "    ./setup.sh install --dev"
            echo
            echo "This will install from your local source code in editable mode."
            return 1
        fi
        
        log_success "Package found on PyPI"
        
        # Run pipx and capture both output and exit code
        pipx_output_file="/tmp/pipx_install_$$.log"
        pipx install "${CONFIG_package_name}" 2>&1 | tee "$pipx_output_file"
        pipx_exit_code=${PIPESTATUS[0]}
        
        if [[ $pipx_exit_code -ne 0 ]]; then
            log_error "Failed to install ${CONFIG_package_name} from PyPI"
            
            # Read the output for error checking
            pipx_output=$(cat "$pipx_output_file")
            
            # Check for common errors and provide helpful suggestions
            if echo "$pipx_output" | grep -q "No matching distribution found\|Could not find a version"; then
                echo
                log_warning "Package '${CONFIG_package_name}' not found on PyPI"
                echo
                echo "This usually means one of the following:"
                echo "  1. The package hasn't been published to PyPI yet"
                echo "  2. The package name is different on PyPI"
                echo "  3. You're developing locally"
                echo
                log_info "💡 For local development, use:"
                echo "     ./setup.sh install --dev"
                echo
                log_info "💡 To check if a package exists on PyPI:"
                echo "     pip index versions ${CONFIG_package_name}"
            elif echo "$pipx_output" | grep -q "pip is configured with locations that require TLS/SSL"; then
                echo
                log_error "SSL/TLS error detected"
                echo "Try updating certificates:"
                echo "  pip install --upgrade certifi"
            elif echo "$pipx_output" | grep -q "Permission denied"; then
                echo
                log_error "Permission error detected"
                echo "Try running pipx ensurepath first:"
                echo "  pipx ensurepath"
            fi
            
            rm -f "$pipx_output_file"
            return 1
        fi
        
        rm -f "$pipx_output_file"
        log_success "${CONFIG_package_name} installed successfully!"
        
        # Clear bash command cache so new command is immediately available
        hash -r 2>/dev/null || true
        
    echo
    echo "=== Installation Complete ==="
    echo "Package: ${CONFIG_package_name}"
    if [[ "$dev_mode" == "true" ]]; then
        echo "Mode: Development (editable)"
        echo "Location: $install_dir"
    else
        echo "Mode: Production (from PyPI)"
    fi
    echo "============================"
    fi
    
    # Setup shell integration if configured
    if [[ "${CONFIG_shell_integration_enabled:-true}" == "true" ]]; then
        setup_shell_integration
    fi
    
    return 0
}

upgrade_with_pipx() {
    log_info "Upgrading ${CONFIG_package_name} with pipx"
    
    if ! check_pipx; then
        return 1
    fi
    
    # Check if installed
    if ! pipx list | grep -q "${CONFIG_package_name}"; then
        log_error "${CONFIG_package_name} is not installed with pipx"
        log_info "Use '$0 install' to install it first"
        return 1
    fi
    
    # Upgrade
    if ! pipx upgrade "${CONFIG_package_name}"; then
        log_error "Failed to upgrade ${CONFIG_package_name}"
        return 1
    fi
    
    log_success "${CONFIG_package_name} upgraded successfully!"
    return 0
}

uninstall_with_pipx() {
    log_info "Uninstalling ${CONFIG_package_name}"
    
    if ! check_pipx; then
        return 1
    fi
    
    # Check for both production and development package names
    local package_to_uninstall=""
    if pipx list | grep -q "${CONFIG_package_name}"; then
        package_to_uninstall="${CONFIG_package_name}"
    elif pipx list | grep -q "${CONFIG_command_name}"; then
        package_to_uninstall="${CONFIG_command_name}"
        log_info "Found development installation: ${CONFIG_command_name}"
    else
        log_warning "Neither ${CONFIG_package_name} nor ${CONFIG_command_name} is installed with pipx"
        return 0
    fi
    
    # Uninstall
    if ! pipx uninstall "${package_to_uninstall}"; then
        log_error "Failed to uninstall ${package_to_uninstall}"
        return 1
    fi
    
    log_success "${package_to_uninstall} uninstalled successfully!"
    echo
    echo "=== Uninstall Complete ==="
    echo "Package '${package_to_uninstall}' has been removed."
    echo "=========================="
    
    # Remove shell integration if configured
    if [[ "${CONFIG_shell_integration_enabled:-true}" == "true" ]]; then
        remove_shell_integration
    fi
    
    return 0
}

# Shell integration functions
get_shell_config_file() {
    local shell_name="${SHELL##*/}"
    
    case "$shell_name" in
        bash)
            if [[ -f "$HOME/.bashrc" ]]; then
                echo "$HOME/.bashrc"
            elif [[ -f "$HOME/.bash_profile" ]]; then
                echo "$HOME/.bash_profile"
            fi
            ;;
        zsh)
            if [[ -f "$HOME/.zshrc" ]]; then
                echo "$HOME/.zshrc"
            fi
            ;;
        fish)
            if [[ -d "$HOME/.config/fish" ]]; then
                echo "$HOME/.config/fish/config.fish"
            fi
            ;;
        *)
            log_warning "Unknown shell: $shell_name"
            ;;
    esac
}

setup_shell_integration() {
    log_info "Setting up shell integration"
    
    local shell_config=$(get_shell_config_file)
    
    if [[ -z "$shell_config" ]]; then
        log_warning "Could not determine shell configuration file"
        return 0
    fi
    
    local integration_marker="# ${CONFIG_package_name} shell integration"
    
    # Check if already configured
    if grep -q "$integration_marker" "$shell_config" 2>/dev/null; then
        log_info "Shell integration already configured"
        return 0
    fi
    
    # Add integration based on configuration
    if [[ -n "${CONFIG_shell_integration_alias:-}" ]]; then
        echo "" >> "$shell_config"
        echo "$integration_marker" >> "$shell_config"
        echo "alias ${CONFIG_shell_integration_alias}='${CONFIG_package_name}'" >> "$shell_config"
        echo "$integration_marker end" >> "$shell_config"
        
        log_success "Added shell alias: ${CONFIG_shell_integration_alias}"
        log_info "Run 'source $shell_config' or start a new shell to use the alias"
    fi
}

remove_shell_integration() {
    log_info "Removing shell integration"
    
    local shell_config=$(get_shell_config_file)
    
    if [[ -z "$shell_config" ]] || [[ ! -f "$shell_config" ]]; then
        return 0
    fi
    
    local integration_marker="# ${CONFIG_package_name} shell integration"
    
    # Remove integration block
    if grep -q "$integration_marker" "$shell_config" 2>/dev/null; then
        # Create backup
        cp "$shell_config" "$shell_config.backup"
        
        # Remove the integration block
        awk "
            /$integration_marker\$/ { skip = 1 }
            /$integration_marker end/ { skip = 0; next }
            !skip { print }
        " "$shell_config.backup" > "$shell_config"
        
        log_success "Removed shell integration"
    fi
}

# Post-installation verification
verify_installation() {
    log_info "Verifying installation..."
    
    # Test command availability using the actual command name
    local command_name="${CONFIG_command_name:-${CONFIG_package_name}}"
    if ! command -v "${command_name}" &> /dev/null; then
        echo
        echo "=== PATH Configuration Required ==="
        log_warning "Installation succeeded, but '${command_name}' command is not yet available"
        echo
        echo "This is because pipx's bin directory is not in your PATH."
        echo
        echo "To fix this, run:"
        echo "  pipx ensurepath"
        echo
        echo "Then either:"
        echo "  • Open a new terminal window, OR"
        echo "  • Run: source ~/.bashrc (or ~/.zshrc for zsh)"
        echo
        echo "For this session only, you can run:"
        echo "  export PATH=\"\$PATH:\$HOME/.local/bin\""
        echo "===================================="
        return 1
    fi
    
    # Test basic functionality if version check is available
    if "${command_name}" --version &> /dev/null; then
        local version=$("${command_name}" --version 2>/dev/null | head -1)
        log_success "Installation verified - version: ${version}"
    elif "${command_name}" --help &> /dev/null; then
        log_success "Installation verified - help command works"
    else
        log_warning "Command found but basic functionality test failed"
        log_info "Installation may still be functional"
    fi
    
    return 0
}

# Command handlers
cmd_install() {
    local dev_mode=false
    local auto_detect_local=false
    local explicit_local_deps=""
    
    # Parse install options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dev)
                dev_mode=true
                shift
                ;;
            --auto-detect-local)
                auto_detect_local=true
                shift
                ;;
            --local-deps=*)
                explicit_local_deps="${1#*=}"
                shift
                ;;
            --local-deps)
                if [[ $# -gt 1 ]]; then
                    explicit_local_deps="$2"
                    shift 2
                else
                    log_error "--local-deps requires a value"
                    show_usage
                    exit 1
                fi
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Run system checks
    check_python_version || exit 1
    check_git || exit 1
    check_jq || exit 1
    check_disk_space || exit 1
    
    # Prepare development dependencies if in dev mode with local repo flags
    if [[ "$dev_mode" == "true" && ("$auto_detect_local" == "true" || -n "$explicit_local_deps") ]]; then
        log_info "Preparing local development dependencies..."
        if ! prepare_dev_dependencies "$auto_detect_local" "$explicit_local_deps"; then
            log_error "Failed to prepare development dependencies"
            exit 1
        fi
    fi
    
    # Perform installation
    if install_with_pipx "$dev_mode"; then
        # Verify installation worked
        verify_installation
    else
        exit 1
    fi
}

cmd_upgrade() {
    upgrade_with_pipx
}

cmd_uninstall() {
    uninstall_with_pipx
}

cmd_status() {
    log_info "Checking ${CONFIG_package_name} installation status"
    
    # Check pipx installation
    if pipx list 2>/dev/null | grep -q "${CONFIG_package_name}"; then
        log_success "${CONFIG_package_name} is installed via pipx"
        
        # Get version if available
        local command_name="${CONFIG_command_name:-${CONFIG_package_name}}"
        if command -v "${command_name}" &> /dev/null; then
            local version=$("${command_name}" --version 2>/dev/null || echo "unknown")
            log_info "Version: $version"
        fi
    else
        log_info "${CONFIG_package_name} is not installed via pipx"
    fi
    
    # Check command availability using the actual command name
    local command_name="${CONFIG_command_name:-${CONFIG_package_name}}"
    if command -v "${command_name}" &> /dev/null; then
        log_success "Command '${command_name}' is available in PATH"
    else
        log_warning "Command '${command_name}' is not in PATH"
    fi
}

# Show usage information
show_usage() {
    cat << EOF
Usage: ./setup.sh [OPTIONS] [COMMAND] [COMMAND_OPTIONS]

Global Options:
    --debug, --verbose    Enable debug mode with detailed output

Commands:
    install               Install ${CONFIG_package_name:-the package} with pipx
    install --dev         Install in development mode (editable)
    install --dev --auto-detect-local
                          Install in dev mode with auto-detected local repos
    install --dev --local-deps="path1,path2"
                          Install in dev mode with explicit local dependency paths
    upgrade               Upgrade to the latest version
    uninstall             Remove the installation
    status                Check installation status
    help                  Show this help message

Local Development Options (require --dev):
    --auto-detect-local   Automatically detect and use local repositories
                          defined in the development_dependencies config
    --local-deps=PATHS    Comma-separated list of local repository paths
                          to install as editable dependencies

Examples:
    ./setup.sh install              # Install from PyPI
    ./setup.sh install --dev        # Install in development mode
    ./setup.sh install --dev --auto-detect-local
                                    # Install with local repo auto-detection
    ./setup.sh install --dev --local-deps="../stt,../ttt"
                                    # Install with specific local repos
    ./setup.sh --debug install      # Install with debug output
    ./setup.sh upgrade              # Upgrade to latest version
    ./setup.sh uninstall            # Remove installation
    ./setup.sh status               # Check if installed

EOF
}

# Main execution
main() {
    # Parse global options first
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --debug|--verbose)
                export DEBUG=1
                log_debug "Debug mode enabled"
                shift
                ;;
            *)
                break
                ;;
        esac
    done
    
    # Load configuration first
    load_config
    
    log_debug "Configuration loaded successfully"
    
    # Default to showing usage if no command given
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 0
    fi
    
    log_debug "Running command: $1 with args: ${*:2}"
    
    # Parse command
    case "$1" in
        install)
            shift
            cmd_install "$@"
            ;;
        upgrade)
            shift
            cmd_upgrade "$@"
            ;;
        uninstall)
            shift
            cmd_uninstall "$@"
            ;;
        status)
            shift
            cmd_status "$@"
            ;;
        help|--help|-h)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"