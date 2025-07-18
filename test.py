#!/usr/bin/env python3
"""Enhanced test runner for GOOBITS STT System.

Single entry point for all testing functionality: running tests, viewing history,
comparing runs, and detailed analysis.
"""
import sys
import subprocess
import argparse
import os

# Auto-detect and use test environment if available
def check_and_use_test_env():
    """Check if test environment exists and re-exec with it if needed."""
    test_env_python = os.path.join(".test_artifacts", "test-env", "bin", "python")
    
    # If test env exists and we're not already using it
    if os.path.exists(test_env_python) and sys.executable != os.path.abspath(test_env_python):
        print("🔄 Switching to test environment...")
        # Re-execute this script with the test environment Python
        os.execv(test_env_python, [test_env_python] + sys.argv)

# Check for test environment at startup
check_and_use_test_env()

def show_examples():
    """Show comprehensive usage examples."""
    examples = """
🧪 GOOBITS STT TEST RUNNER - Complete Testing Suite

INSTALLATION:
  ./test.py --install                              # Install project with all dependencies
                                                   # (creates venv if needed, checks system deps)

BASIC USAGE:
  ./test.py                                         # Run all tests (auto-parallel + tracking)
  ./test.py tests/text_formatting/                 # Run specific test directory  
  ./test.py tests/text_formatting/test_basic_formatting.py  # Run specific file

EXECUTION MODES:
  ./test.py --sequential                            # Force single-threaded execution
  ./test.py --parallel 4                           # Use 4 parallel workers
  ./test.py --parallel off                         # Same as --sequential

DIFF TRACKING (automatic by default):
  ./test.py tests/text_formatting/                 # Auto-tracks changes vs last run
  ./test.py --no-track                             # Disable automatic tracking
  
VIEW RESULTS (no tests run):
  ./test.py --history                               # Show test run history
  ./test.py --diff=-1                               # Compare last run vs current
  ./test.py --diff="-5,-1"                          # Compare 5th last vs last run
  ./test.py --diff="0,10"                           # Compare first vs 10th run

FAILURE ANALYSIS:
  ./test.py --detailed                             # Parse and show expected vs actual
  ./test.py --full-diff                            # Show full assertion diffs
  ./test.py --summary                              # Show YAML summary of failures on screen
  
COMMON WORKFLOWS:
  ./test.py tests/text_formatting/ --sequential --detailed
                                                   # Debug text formatting issues
  ./test.py --parallel 8 tests/text_formatting/   # Fast parallel text formatting tests
  ./test.py --diff=-3                              # Check changes since 3 runs ago
  ./test.py tests/text_formatting/ --history      # Run tests then show history

PURE PYTEST (if you prefer direct access):
  python3 -m pytest tests/text_formatting/ --track-diff --sequential
  python3 -m pytest tests/text_formatting/ -n 4 --detailed
  python3 -m pytest tests/text_formatting/ --history

For more pytest options: python3 -m pytest --help
"""
    print(examples)

def main():
    """Parse args and run pytest with appropriate settings."""
    import os
    
    # Custom help handling
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ["-h", "--help"]):
        show_examples()
        return 0
    
    # Parse our specific args, pass everything else to pytest
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--sequential", action="store_true", 
                       help="Force sequential execution (disable parallel)")
    parser.add_argument("--parallel", default="auto",
                       help='Parallel workers: "auto" (7), "off" (sequential), or number like "4"')
    parser.add_argument("--no-track", action="store_true",
                       help="Disable automatic diff tracking")
    parser.add_argument("--detailed", action="store_true",
                       help="Show detailed failure analysis")
    parser.add_argument("--full-diff", action="store_true",
                       help="Show full assertion diffs")
    parser.add_argument("--history", nargs="?", const=True, 
                       help="Show test run history. Optional: number of runs to show")
    parser.add_argument("--diff", dest="diff_range", 
                       help="Compare test runs (e.g., --diff=-1 or --diff='-5,-1')")
    parser.add_argument("--install", action="store_true",
                       help="Install the project with all dependencies")
    parser.add_argument("--summary", action="store_true",
                       help="Show YAML summary of test failures")
    
    # Parse known args, keep the rest for pytest
    known_args, pytest_args = parser.parse_known_args()
    
    # Handle installation
    if known_args.install:
        import os
        import platform
        
        print("🔧 GOOBITS STT Installation")
        print("=" * 50)
        
        # Check if we're in a virtual environment
        in_venv = sys.prefix != sys.base_prefix or os.environ.get('VIRTUAL_ENV') is not None
        
        if not in_venv:
            print("⚠️  Not in a virtual environment!")
            
            # Check if test-env already exists
            test_env_path = os.path.join(".test_artifacts", "test-env")
            if not os.path.exists(test_env_path):
                print("\nCreating test environment...")
                os.makedirs(".test_artifacts", exist_ok=True)
                subprocess.run([sys.executable, "-m", "venv", test_env_path], check=True)
                print(f"✅ Test environment created in {test_env_path}")
            else:
                print(f"✅ Using existing test environment in {test_env_path}")
            
            # Determine the correct python executable path
            if platform.system() == "Windows":
                python_exe = os.path.join(test_env_path, "Scripts", "python.exe")
            else:
                python_exe = os.path.join(test_env_path, "bin", "python")
            
            print(f"\n📝 Activate it with:")
            if platform.system() == "Windows":
                print(f"   .\\{test_env_path}\\Scripts\\activate")
            else:
                print(f"   source {test_env_path}/bin/activate")
            print("\nUsing test environment's pip for installation...")
        else:
            print("✅ Already in a virtual environment")
        
        print("\n📦 Installing GOOBITS STT with all dependencies...")
        # Use the venv's python to ensure pip is available
        if not in_venv and 'python_exe' in locals():
            install_cmd = [python_exe, "-m", "pip", "install", "-e", ".[dev]"]
        else:
            install_cmd = [sys.executable, "-m", "pip", "install", "-e", ".[dev]"]
        result = subprocess.run(install_cmd, check=False)
        
        if result.returncode == 0:
            print("\n✅ Installation complete!")
            
            # Install SpaCy language model
            print("\n📥 Installing SpaCy English language model...")
            spacy_python = sys.executable if in_venv else python_exe
            spacy_cmd = [spacy_python, "-m", "spacy", "download", "en_core_web_sm"]
            spacy_result = subprocess.run(spacy_cmd, check=False)
            if spacy_result.returncode == 0:
                print("✅ SpaCy model installed successfully!")
            else:
                print("⚠️  SpaCy model installation failed, trying fallback method...")
                fallback_cmd = [spacy_python, "-m", "pip", "install", 
                               "en_core_web_sm@https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"]
                fallback_result = subprocess.run(fallback_cmd, check=False)
                if fallback_result.returncode == 0:
                    print("✅ SpaCy model installed via fallback method!")
                else:
                    print("❌ SpaCy model installation failed!")
                    print("   Text formatting may not work properly.")
            
            print("\n🧪 Verifying installation...")
            verify_cmd = [sys.executable if in_venv else python_exe, 
                         "tests/__tools__/verify_test_setup.py"]
            subprocess.run(verify_cmd, check=False)
            print("\n🚀 Ready to run tests with: ./test.py")
        else:
            print("\n❌ Installation failed!")
            print("   Check the error messages above for details.")
            return 1
        
        return 0
    
    # Handle read-only operations (history and diff) without running tests
    if known_args.history is not None or known_args.diff_range is not None:
        # Check if test environment exists and use it
        test_env_python = os.path.join(".test_artifacts", "test-env", "bin", "python")
        if os.path.exists(test_env_python):
            python_cmd = test_env_python
        else:
            python_cmd = "python3"
        
        cmd = [python_cmd, "-m", "pytest"]
        
        # Add test path first
        if pytest_args:
            # Use existing pytest args first
            cmd.extend(pytest_args)
        else:
            # Default to text_formatting for history/diff operations
            cmd.append("tests/text_formatting/")
        
        # Then add our options
        if known_args.history is not None:
            if known_args.history is True:
                # Just --history without a number
                cmd.append("--history")
            else:
                # --history=N
                cmd.extend(["--history", str(known_args.history)])
        
        if known_args.diff_range is not None:
            cmd.append("--diff")
            # Parse the diff range string
            if ',' in known_args.diff_range:
                # Format like "-5,-1"
                parts = known_args.diff_range.split(',')
                cmd.extend([part.strip() for part in parts])
            else:
                # Single value like "-1"
                cmd.append(known_args.diff_range)
        
        # Run pytest for read-only operations
        result = subprocess.run(cmd, check=False)
        return result.returncode
    
    # Regular test execution
    # Check if test environment exists and use it
    test_env_python = os.path.join(".test_artifacts", "test-env", "bin", "python")
    if os.path.exists(test_env_python):
        python_cmd = test_env_python
    else:
        python_cmd = "python3"
    
    cmd = [python_cmd, "-m", "pytest"] + pytest_args
    
    # Handle summary mode - force sequential for proper plugin support
    if known_args.summary:
        print("🚀 Running tests in sequential mode (required for summary)...")
    elif not known_args.sequential and known_args.parallel != "off":
        try:
            import xdist
            workers = known_args.parallel if known_args.parallel != "auto" else "7"
            
            # Only add if not already specified
            if not any(arg.startswith("-n") for arg in pytest_args):
                cmd.extend(["-n", workers])
                print(f"🚀 Running tests in parallel with {workers} workers...")
        except ImportError:
            print("⚠️  pytest-xdist not installed. Install with: pip install pytest-xdist")
            print("Falling back to sequential execution...")
    else:
        print("🚀 Running tests in sequential mode...")
    
    # Add automatic diff tracking unless disabled (including for summary mode)
    if not known_args.no_track and "--track-diff" not in pytest_args:
        cmd.append("--track-diff")
    
    # Add detailed analysis if requested
    if known_args.detailed and "--detailed" not in pytest_args:
        cmd.append("--detailed")
    
    # Add full diff if requested
    if known_args.full_diff and "--full-diff" not in pytest_args:
        cmd.append("--full-diff")
    
    # Handle summary mode specially
    if known_args.summary:
        # Run pytest with summary but capture all output
        cmd.append("--summary")
        cmd.extend(["-q", "--tb=no", "--disable-warnings"])
        
        # Try using rich for better terminal management
        try:
            from rich.live import Live
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text
            
            console = Console()
            
            # Start the process
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                     text=True, bufsize=1, universal_newlines=True)
            
            recent_lines = []
            max_recent_lines = 5
            output_lines = []
            
            def create_progress_panel():
                if not recent_lines:
                    return Panel("🧪 Running tests...", title="Test Progress")
                
                content = Text()
                for line in recent_lines[-max_recent_lines:]:
                    content.append(line + "\n")
                
                return Panel(content, title="Test Progress")
            
            # Use rich Live display
            with Live(create_progress_panel(), console=console, refresh_per_second=4) as live:
                while True:
                    line = process.stdout.readline()
                    if line == '' and process.poll() is not None:
                        break
                    if line:
                        output_lines.append(line)
                        line_clean = line.strip()
                        
                        # Skip empty lines and certain noise
                        if line_clean and not line_clean.startswith("=") and "warnings summary" not in line_clean:
                            recent_lines.append(line_clean)
                            if len(recent_lines) > max_recent_lines:
                                recent_lines.pop(0)
                            
                            # Update the live display
                            live.update(create_progress_panel())
            
            # Wait for completion and ensure Live display is completely cleared
            process.wait()
            
            # Move cursor up to clear the Live display area manually
            import time
            time.sleep(0.1)  # Give Rich time to finish
            
            # Calculate lines to clear (box height + border)
            lines_to_clear = max_recent_lines + 3  # Content + top/bottom borders + title
            
            # Move cursor up and clear
            for _ in range(lines_to_clear):
                print("\033[1A\033[K", end="")  # Move up one line and clear it
            
        except ImportError:
            # Fallback to simple mode if rich not available
            print("🧪 Running tests with summary mode...")
            print("Running tests... (progress display requires 'rich' library)")
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                     text=True)
            output_lines = []
            for line in process.stdout:
                output_lines.append(line)
            process.wait()
        
        # Get full output
        output = ''.join(output_lines)
        
        # Check for collection errors or other critical issues first
        if "ERROR" in output and ("Interrupted" in output or "error during collection" in output):
            print("❌ Test Collection Error")
            print("=" * 60)
            # Extract and show the error details
            error_start = output.find("ERRORS")
            if error_start != -1:
                error_section = output[error_start:]
                # Stop at the next major section
                for stop_marker in ["short test summary", "==========", "!!!!!!"]:
                    if stop_marker in error_section:
                        error_section = error_section[:error_section.find(stop_marker)]
                        break
                print(error_section.strip())
            return process.returncode
        
        # Find and display the YAML summary
        yaml_start = output.find("TEST FAILURE SUMMARY")
        if yaml_start != -1:
            # Find the start of the actual YAML (after the header)
            yaml_content_start = output.find("test_failure_summary:", yaml_start)
            if yaml_content_start != -1:
                # Print just the YAML part
                yaml_section = output[yaml_content_start:]
                # Stop at the next major section or end
                for stop_marker in ["\n\n\n", "warnings summary", "short test summary"]:
                    if stop_marker in yaml_section:
                        yaml_section = yaml_section[:yaml_section.find(stop_marker)]
                        break
                
                print("🎯 Test Results Summary")
                print("=" * 60)
                print(yaml_section.strip())
            else:
                print("📊 Final Results: All tests completed")
        else:
            # If no failures, show a simple completion message
            print("📊 Tests completed - checking for failures...")
        
        return process.returncode
    else:
        # Always use at least -v for better output unless user specified verbosity
        if not any(arg.startswith("-v") or arg in ["-q", "--quiet"] for arg in pytest_args):
            cmd.append("-v")
    
    # Default to tests/ if no test paths specified
    if not any(arg.startswith("tests/") or arg.endswith(".py") for arg in pytest_args):
        # Check if we have any non-flag arguments
        non_flag_args = [arg for arg in pytest_args if not arg.startswith("-")]
        if not non_flag_args:
            cmd.append("tests/")
    
    # Run pytest
    result = subprocess.run(cmd, check=False)
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())