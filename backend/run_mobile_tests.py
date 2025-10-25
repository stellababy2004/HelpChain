#!/usr/bin/env python3
"""
Mobile Testing Runner for HelpChain
Provides easy commands to run mobile responsive tests
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(command, description):
    """Run a command and return success status"""
    print(f"\nTesting {description}")
    print("-" * 50)

    try:
        result = subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        print("Success!")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed with exit code {e.returncode}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False


def install_dependencies():
    """Install required dependencies"""
    return run_command(
        "pip install -r requirements.txt", "Installing dependencies including Selenium"
    )


def run_quick_mobile_test():
    """Run quick mobile responsive test"""
    return run_command(
        "python mobile_test.py --quick", "Running quick mobile responsive test"
    )


def run_full_mobile_test():
    """Run comprehensive mobile responsive test"""
    return run_command(
        "python mobile_test.py", "Running full mobile responsive test suite"
    )


def run_pytest_mobile():
    """Run pytest mobile responsive tests"""
    return run_command(
        "pytest test_mobile_responsive.py -v", "Running pytest mobile responsive tests"
    )


def run_cross_browser_test():
    """Run cross-browser compatibility test"""
    return run_command(
        "python cross_browser_test.py", "Running cross-browser compatibility test"
    )


def run_quick_cross_browser_test():
    """Run quick cross-browser compatibility test"""
    return run_command(
        "python cross_browser_test.py --quick",
        "Running quick cross-browser compatibility test",
    )


def check_app_running():
    """Check if Flask app is running"""
    import requests

    try:
        response = requests.get("http://127.0.0.1:5000", timeout=5)
        if response.status_code == 200:
            print("Flask app is running on http://127.0.0.1:5000")
            return True
        else:
            print(f"Flask app returned status code {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Flask app is not running: {e}")
        print("   Please start the app with: python appy.py")
        return False


def start_app():
    """Start the Flask application"""
    print("\nStarting Flask application...")
    print("   The app will run in the background.")
    print("   Press Ctrl+C to stop when testing is complete.")
    print("-" * 50)

    try:
        # Start app in background
        process = subprocess.Popen([sys.executable, "appy.py"])
        print(f"App started with PID: {process.pid}")
        print("   Waiting 3 seconds for app to initialize...")

        import time

        time.sleep(3)

        # Check if app is responding
        if check_app_running():
            print("App is ready for testing!")
            return process
        else:
            process.terminate()
            return None

    except Exception as e:
        print(f"Failed to start app: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="HelpChain Mobile Testing Runner")
    parser.add_argument(
        "command",
        choices=[
            "install",
            "quick",
            "full",
            "pytest",
            "cross-browser",
            "quick-cross-browser",
            "check",
            "start",
            "all",
        ],
        help="Command to run",
    )

    args = parser.parse_args()

    print("HelpChain Mobile Responsive Testing")
    print("=" * 50)

    if args.command == "install":
        success = install_dependencies()

    elif args.command == "check":
        success = check_app_running()

    elif args.command == "start":
        process = start_app()
        if process:
            try:
                print("\n⏳ App is running. Press Ctrl+C to stop...")
                process.wait()
            except KeyboardInterrupt:
                print("\n🛑 Stopping app...")
                process.terminate()
                process.wait()
        success = process is not None

    elif args.command == "quick":
        if not check_app_running():
            print("App must be running for tests. Use 'start' command first.")
            success = False
        else:
            success = run_quick_mobile_test()

    elif args.command == "full":
        if not check_app_running():
            print("App must be running for tests. Use 'start' command first.")
            success = False
        else:
            success = run_full_mobile_test()

    elif args.command == "cross-browser":
        if not check_app_running():
            print("App must be running for tests. Use 'start' command first.")
            success = False
        else:
            success = run_cross_browser_test()

    elif args.command == "quick-cross-browser":
        if not check_app_running():
            print("App must be running for tests. Use 'start' command first.")
            success = False
        else:
            success = run_quick_cross_browser_test()

    elif args.command == "all":
        print("Running complete mobile testing workflow...")

        # Step 1: Install dependencies
        if not install_dependencies():
            success = False
        else:
            # Step 2: Start app
            process = start_app()
            if not process:
                success = False
            else:
                try:
                    # Step 3: Run tests
                    test_success = run_quick_mobile_test()
                    if test_success:
                        test_success = run_pytest_mobile()

                    success = test_success

                finally:
                    # Step 4: Stop app
                    print("\nStopping Flask app...")
                    process.terminate()
                    process.wait()

    if "success" in locals():
        sys.exit(0 if success else 1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
