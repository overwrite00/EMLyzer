#!/usr/bin/env python3
"""
EMLyzer Email Analysis Test Runner
Starts the backend and runs the comprehensive email threat detection analysis
"""

import subprocess
import sys
import time
import os
from pathlib import Path

# Add the backend directory to path so we can import EMLyzer modules
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# Set environment variables
os.environ["PYTHONUNBUFFERED"] = "1"


def check_port_in_use(port: int) -> bool:
    """Check if a port is already in use."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", port))
    sock.close()
    return result == 0


def main():
    """Main runner."""
    print("=" * 80)
    print("EMLyzer Email Threat Detection Analysis Test")
    print("=" * 80)

    project_root = Path(__file__).parent
    backend_dir = project_root / "backend"
    script_path = project_root / "email_analysis_test.py"

    # Check if port 8000 is available
    print("\nChecking server port 8000...", end=" ")
    if check_port_in_use(8000):
        print("IN USE (assuming server is running)")
    else:
        print("AVAILABLE")
        print("Starting EMLyzer backend server...")
        # Start the backend server
        os.chdir(backend_dir)
        server_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for server to start
        print("Waiting for server to become ready...", end=" ")
        sys.stdout.flush()
        time.sleep(5)

        # Check if server is ready
        for attempt in range(10):
            if check_port_in_use(8000):
                print("OK")
                break
            time.sleep(1)
        else:
            print("TIMEOUT")
            print("Server may not have started. Check the output above.")
            server_process.terminate()
            return 1

    # Run the analysis test
    print(f"\nRunning analysis script: {script_path}")
    print("-" * 80)

    os.chdir(project_root)
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(project_root),
    )

    print("-" * 80)
    if result.returncode == 0:
        results_file = project_root / "testing" / "analysis_results.json"
        if results_file.exists():
            print(f"\nAnalysis complete! Results saved to:")
            print(f"  {results_file}")
        return 0
    else:
        print("\nAnalysis failed with return code:", result.returncode)
        return 1


if __name__ == "__main__":
    sys.exit(main())
