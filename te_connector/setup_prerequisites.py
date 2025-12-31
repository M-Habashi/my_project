"""
Setup script to check and install prerequisites for Claude Telegram Bridge
"""

import subprocess
import sys

def run_command(cmd, description):
    """Run a command and report success/failure."""
    print(f"\n{'='*50}")
    print(f"Checking: {description}")
    print(f"{'='*50}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} - OK")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ {description} - FAILED")
            if result.stderr:
                print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n" + "="*50)
    print("Claude Telegram Bridge - Prerequisites Setup")
    print("="*50)

    # Check Python
    print("\n1. Checking Python...")
    run_command("python --version", "Python")

    # Check Claude CLI
    print("\n2. Checking Claude CLI...")
    if run_command("claude --version", "Claude CLI"):
        print("✅ Claude CLI is installed")
    else:
        print("❌ Claude CLI not found. Installing...")
        run_command("npm install -g @anthropic-ai/claude-code", "Install Claude CLI")

    # Check required Python packages
    print("\n3. Checking Python packages...")
    packages = ["requests"]
    for package in packages:
        run_command(f"pip show {package}", f"Package: {package}")

    # Optional packages
    print("\n4. Optional packages for advanced features...")
    print("   For screenshots: pip install playwright && playwright install chromium")
    print("   For git/PR features: Install Git and GitHub CLI (gh)")

    print("\n" + "="*50)
    print("Setup check complete!")
    print("="*50)
    print("\nNext steps:")
    print("1. Edit config.env with your settings")
    print("2. Run: python claude_telegram_bridge.py")
    print("   OR double-click: start_bridge.bat")

if __name__ == "__main__":
    main()
