"""
Telegram Bridge for Claude Code CLI
Runs on your desktop, polls Telegram for messages, runs Claude, sends responses back.
"""

import os
import sys
import time
import subprocess
import requests
from datetime import datetime
from pathlib import Path
import signal
import filelock
import re

# ============== LOAD CONFIG ==============
def load_config():
    """Load configuration from config.env file."""
    config_path = Path(__file__).parent / "config.env"
    if config_path.exists():
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    os.environ.setdefault(key, value)

load_config()

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()
ALLOWED_USER_ID = os.environ.get("TG_ALLOWED_USER_ID", CHAT_ID).strip()
REPO_DIR = os.environ.get("REPO_DIR", os.getcwd()).strip()

# Validate required config
if not BOT_TOKEN or not CHAT_ID:
    print("[ERROR] Missing required config!")
    print("   TG_BOT_TOKEN:", "[OK]" if BOT_TOKEN else "[MISSING]")
    print("   TG_CHAT_ID:", "[OK]" if CHAT_ID else "[MISSING]")
    sys.exit(1)

CLAUDE_TIMEOUT = 600  # 10 minutes max per request
# ============================================


class TelegramBot:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"

    def send_message(self, text, parse_mode=None):
        """Send a text message, splitting if too long."""
        url = f"{self.base_url}/sendMessage"
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]

        for chunk in chunks:
            data = {"chat_id": self.chat_id, "text": chunk}
            if parse_mode:
                data["parse_mode"] = parse_mode
            try:
                response = requests.post(url, json=data, timeout=30)
                if not response.ok:
                    print(f"[ERROR] Failed to send message: {response.status_code} {response.text}")
                else:
                    print(f"[OK] Message sent ({len(chunk)} chars)")
            except Exception as e:
                print(f"[ERROR] Error sending message: {e}")

    def send_file(self, file_path, caption=""):
        """Send a file (screenshot, etc.)."""
        url = f"{self.base_url}/sendDocument"
        try:
            with open(file_path, "rb") as f:
                requests.post(
                    url,
                    data={"chat_id": self.chat_id, "caption": caption[:1024]},
                    files={"document": f},
                    timeout=60
                )
        except Exception as e:
            print(f"Error sending file: {e}")

    def send_photo(self, file_path, caption=""):
        """Send a photo/screenshot."""
        url = f"{self.base_url}/sendPhoto"
        try:
            with open(file_path, "rb") as f:
                requests.post(
                    url,
                    data={"chat_id": self.chat_id, "caption": caption[:1024]},
                    files={"photo": f},
                    timeout=60
                )
        except Exception as e:
            print(f"Error sending photo: {e}")

    def get_updates(self, offset=None, timeout=30):
        """Long-poll for new messages."""
        url = f"{self.base_url}/getUpdates"
        params = {"timeout": timeout}
        if offset:
            params["offset"] = offset
        try:
            response = requests.get(url, params=params, timeout=timeout + 10)
            data = response.json()
            if not data.get("ok"):
                error_msg = data.get("description", "Unknown error")
                print(f"[ERROR] Telegram API Error: {error_msg}")
                return {"result": []}
            return data
        except Exception as e:
            print(f"[ERROR] Error getting updates: {e}")
            return {"result": []}


class ClaudeRunner:
    def __init__(self, repo_dir):
        self.repo_dir = repo_dir
        self.is_running = False

    def run(self, prompt, timeout=CLAUDE_TIMEOUT):
        """Run Claude Code CLI with the given prompt."""
        self.is_running = True

        cmd = [
            "claude",
            "--dangerously-skip-permissions",
            "-p", prompt
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=True
            )

            output = result.stdout or ""
            if result.stderr:
                output += f"\n\n[stderr]: {result.stderr}"

            return output.strip() if output.strip() else "Claude completed (no output)"

        except subprocess.TimeoutExpired:
            return "[TIMEOUT] Claude timed out after 10 minutes. The task might be too complex."
        except FileNotFoundError:
            return "[ERROR] Claude CLI not found. Make sure 'claude' is in your PATH."
        except Exception as e:
            return f"[ERROR] Error running Claude: {str(e)}"
        finally:
            self.is_running = False

    def create_pr(self, description):
        """Create a PR using GitHub CLI."""
        try:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True
            )

            if not status.stdout.strip():
                return "No changes to commit. Make some changes first!"

            branch_name = f"claude/{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            commands = [
                ["git", "checkout", "-b", branch_name],
                ["git", "add", "-A"],
                ["git", "commit", "-m", f"Claude: {description[:50]}"],
                ["git", "push", "-u", "origin", branch_name],
            ]

            for cmd in commands:
                result = subprocess.run(cmd, cwd=self.repo_dir, capture_output=True, text=True)
                if result.returncode != 0:
                    return f"[ERROR] Failed at: {' '.join(cmd)}\n{result.stderr}"

            pr_result = subprocess.run(
                ["gh", "pr", "create", "--title", f"Claude: {description[:50]}",
                 "--body", f"## Changes\n\n{description}\n\n---\n*Created by Claude via Telegram*"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True
            )

            if pr_result.returncode == 0:
                return f"[SUCCESS] PR created!\n{pr_result.stdout}"
            else:
                return f"[ERROR] PR creation failed:\n{pr_result.stderr}"

        except Exception as e:
            return f"[ERROR] Error creating PR: {str(e)}"


class ScreenshotTaker:
    def __init__(self, repo_dir):
        # Use absolute path based on script location
        self.screenshot_dir = Path(__file__).parent / "screenshots"
        self.screenshot_dir.mkdir(exist_ok=True)
        self.repo_dir = Path(repo_dir)
        self.html_files_cache = None
        print(f"[ScreenshotTaker] Using directory: {self.screenshot_dir}")

    def find_html_files(self):
        """
        Find all HTML files in the project directory.
        Returns dict mapping keywords to file paths.
        """
        if self.html_files_cache:
            return self.html_files_cache

        print(f"[HTMLDiscovery] Scanning {self.repo_dir} for HTML files...")

        html_files = []
        exclude_patterns = {'.git', 'node_modules', 'venv', '__pycache__', '.venv'}

        try:
            for html_file in self.repo_dir.rglob('*.html'):
                # Check if path contains excluded directories
                if any(excluded in html_file.parts for excluded in exclude_patterns):
                    continue
                html_files.append(html_file)

            if not html_files:
                print(f"[HTMLDiscovery] No HTML files found in {self.repo_dir}")
                return None

            # Sort for consistent ordering
            html_files.sort()
            print(f"[HTMLDiscovery] Found {len(html_files)} HTML files")

            # Create mapping with priority
            mapping = {}

            # Determine default - prioritize index.html, then main.html, then gold_webpage.html
            for priority_name in ['index.html', 'main.html', 'gold_webpage.html']:
                for html_file in html_files:
                    if html_file.name == priority_name:
                        mapping['default'] = html_file
                        break
                if 'default' in mapping:
                    break

            # Fallback to first found
            if 'default' not in mapping:
                mapping['default'] = html_files[0]

            # Set project/build/app mappings
            mapping['project'] = mapping['default']
            mapping['build'] = mapping['default']
            mapping['app'] = mapping['default']

            print(f"[HTMLDiscovery] Mapping: {[(k, v.name) for k, v in mapping.items()]}")

            self.html_files_cache = mapping
            return mapping

        except Exception as e:
            print(f"[HTMLDiscovery] ERROR: {e}")
            return None

    def start_http_server(self, directory, port=8000, max_retries=5):
        """
        Start a temporary HTTP server in the given directory.
        Returns: (subprocess.Popen, actual_port, base_url) or (None, None, None) on failure
        """
        directory = Path(directory)

        if not directory.exists():
            print(f"[HTTPServer] Directory does not exist: {directory}")
            return None, None, None

        for attempt in range(max_retries):
            current_port = port + attempt
            try:
                print(f"[HTTPServer] Attempting to start server on port {current_port}...")

                server_process = subprocess.Popen(
                    ["python", "-m", "http.server", str(current_port), "--directory", str(directory)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                # Wait for server to start
                time.sleep(2)

                # Verify server is running by making a request
                try:
                    response = requests.get(f"http://localhost:{current_port}", timeout=3)
                    print(f"[HTTPServer] Server started successfully on port {current_port}")
                    return server_process, current_port, f"http://localhost:{current_port}"
                except requests.ConnectionError:
                    server_process.terminate()
                    continue

            except Exception as e:
                print(f"[HTTPServer] Port {current_port} failed: {e}")
                continue

        print(f"[HTTPServer] Failed to start server on ports {port}-{port+max_retries-1}")
        return None, None, None

    def stop_http_server(self, server_process):
        """
        Stop the HTTP server process gracefully.
        """
        if not server_process:
            return

        try:
            print(f"[HTTPServer] Stopping server (PID: {server_process.pid})...")
            server_process.terminate()

            try:
                server_process.wait(timeout=5)
                print("[HTTPServer] Server stopped gracefully")
            except subprocess.TimeoutExpired:
                print("[HTTPServer] Server did not stop, forcing kill...")
                server_process.kill()
                server_process.wait()
                print("[HTTPServer] Server force killed")

        except Exception as e:
            print(f"[HTTPServer] Error stopping server: {e}")

    def take_project_screenshot(self, html_keyword='default'):
        """
        Take screenshot of a local HTML file.
        Starts HTTP server, takes screenshot, stops server.
        """
        try:
            # Find HTML files
            html_mapping = self.find_html_files()
            if not html_mapping:
                print("[ProjectShot] No HTML files found in project")
                return None

            # Get target HTML file
            html_file = html_mapping.get(html_keyword, html_mapping.get('default'))
            if not html_file:
                print(f"[ProjectShot] HTML file not found for keyword: {html_keyword}")
                return None

            print(f"[ProjectShot] Target: {html_keyword} -> {html_file.name}")

            # Start HTTP server at project root
            server_process, port, base_url = self.start_http_server(self.repo_dir)
            if not server_process:
                print("[ProjectShot] Failed to start HTTP server")
                return None

            try:
                # Build URL - get relative path from repo root
                relative_path = html_file.relative_to(self.repo_dir)
                url = f"{base_url}/{relative_path}".replace("\\", "/")

                print(f"[ProjectShot] Screenshot URL: {url}")

                # Take screenshot
                screenshot_path = self.take_browser_screenshot(url)
                return screenshot_path

            finally:
                # Always stop server
                self.stop_http_server(server_process)

        except Exception as e:
            print(f"[ProjectShot] ERROR: {e}")
            import traceback
            traceback.print_exc()
            return None

    def take_browser_screenshot(self, url):
        """Take a screenshot of a URL using Playwright."""
        try:
            from playwright.sync_api import sync_playwright

            screenshot_path = self.screenshot_dir / f"shot_{int(time.time())}.png"

            print(f"[Screenshot] Starting for URL: {url}")
            print(f"[Screenshot] Will save to: {screenshot_path}")

            with sync_playwright() as p:
                print("[Screenshot] Launching chromium...")
                browser = p.chromium.launch()
                print("[Screenshot] Creating page...")
                page = browser.new_page()
                print(f"[Screenshot] Navigating to {url}...")
                page.goto(url, timeout=30000)
                print("[Screenshot] Taking screenshot...")
                page.screenshot(path=str(screenshot_path), full_page=True)
                print("[Screenshot] Closing browser...")
                browser.close()

            print(f"[Screenshot] SUCCESS! Saved to: {screenshot_path}")
            return str(screenshot_path)
        except ImportError as e:
            print(f"[Screenshot] ImportError: Playwright not installed - {e}")
            return None
        except Exception as e:
            print(f"[Screenshot] ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None


def parse_screenshot_intent(text):
    """
    Detect if message is a screenshot request.
    Returns: (is_screenshot_command, target_keyword, url_if_external)
    """
    text_lower = text.lower()

    # Trigger words for screenshot commands
    trigger_patterns = [
        r'\bscreenshot\b',
        r'\bshot\b',
        r'\btake\s+a\s+screenshot\b',
        r'\bcapture\b',
        r'\bsnap\b'
    ]

    # Check if any trigger pattern matches
    has_trigger = any(re.search(pattern, text_lower) for pattern in trigger_patterns)

    if not has_trigger:
        return False, None, None

    # Look for action verbs (to avoid false positives like "about screenshots")
    action_patterns = [
        r'(?:take|make|capture|create|shoot|snap)',
        r'^screenshot\b',
        r'^shot\b'
    ]

    has_action = any(re.search(action, text_lower) for action in action_patterns)

    if not has_action:
        # Avoid false positives like "tell me about screenshots"
        if any(word in text_lower for word in ['about', 'feature', 'tool', 'tutorial']):
            return False, None, None

    # Extract target keyword
    keyword_patterns = {
        'page': r'\b(?:the\s+)?page\b',
        'project': r'\b(?:the\s+)?project\b',
        'build': r'\b(?:the\s+)?build\b',
        'app': r'\b(?:the\s+)?app(?:lication)?\b',
        'default': r'\b(?:the\s+)?(?:webpage|website|site)\b'
    }

    target_keyword = None
    for keyword, pattern in keyword_patterns.items():
        if re.search(pattern, text_lower):
            target_keyword = keyword if keyword != 'default' else 'default'
            break

    # Look for URL in text
    url_match = None
    url_patterns = [
        r'(?:https?://[^\s]+)',
        r'(?:www\.[^\s]+)',
        r'(?:[a-z0-9-]+\.(?:com|org|net|io|co|dev|app|site|web))'
    ]

    for pattern in url_patterns:
        match = re.search(pattern, text_lower)
        if match:
            url_match = match.group(0)
            break

    return True, target_keyword, url_match


def main():
    print("=" * 50)
    print("Claude Telegram Bridge Starting...")
    print(f"Repo: {REPO_DIR}")
    print("=" * 50)

    # Acquire lock to prevent multiple instances
    lock_file = Path(__file__).parent / ".bot.lock"
    lock = filelock.FileLock(str(lock_file), timeout=1)

    try:
        lock.acquire(timeout=0)
    except filelock.Timeout:
        print("[ERROR] Another bot instance is already running!")
        print("[ERROR] Kill it first with: taskkill /F /IM python.exe")
        sys.exit(1)

    def cleanup_and_exit(signum=None, frame=None):
        """Cleanup function called on exit."""
        try:
            lock.release()
        except:
            pass
        sys.exit(0)

    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)

    bot = TelegramBot(BOT_TOKEN, CHAT_ID)
    claude = ClaudeRunner(REPO_DIR)
    screenshotter = ScreenshotTaker(REPO_DIR)

    bot.send_message(
        "[ONLINE] Claude Bridge is ONLINE!\n\n"
        "Commands:\n"
        "- Send any message → Claude responds\n"
        "- /pr <description> → Create PR\n"
        "- /shot → Screenshot default page\n"
        "- /shot project|build|app → Screenshot specific page\n"
        "- /shot <url> → Screenshot external URL\n"
        "- Natural language: 'screenshot the page', 'shot the build'\n"
        "- /status → Check status"
    )

    offset = None

    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30)

            for update in updates.get("result", []):
                offset = update["update_id"] + 1

                message = update.get("message", {})
                text = message.get("text", "").strip()
                user_id = str(message.get("from", {}).get("id", ""))

                if not text:
                    continue

                # Check authorization
                if str(user_id) != str(ALLOWED_USER_ID):
                    bot.send_message("⛔ Unauthorized user")
                    continue

                print(f"[{datetime.now()}] Received: {text[:50]}...")

                # Handle commands
                if text.startswith("/status"):
                    status = "[ONLINE]" if not claude.is_running else "[PROCESSING]"
                    bot.send_message(f"Status: {status}\nRepo: {REPO_DIR}")

                elif text.startswith("/pr "):
                    description = text[4:].strip()
                    if not description:
                        bot.send_message("Usage: /pr <description of changes>")
                    else:
                        bot.send_message("[WAIT] Creating PR...")
                        result = claude.create_pr(description)
                        bot.send_message(result)

                elif text.startswith("/shot"):
                    args = text[5:].strip()  # Get everything after "/shot"

                    if not args:
                        # /shot → screenshot default page
                        bot.send_message("[WAIT] Taking screenshot of default page...")
                        screenshot_path = screenshotter.take_project_screenshot('default')
                        caption = "Screenshot: Default page"

                    elif args.lower() in ['project', 'build', 'app', 'page']:
                        # /shot project|build|app|page
                        bot.send_message(f"[WAIT] Taking screenshot of {args} page...")
                        screenshot_path = screenshotter.take_project_screenshot(args.lower())
                        caption = f"Screenshot: {args.capitalize()} page"

                    else:
                        # /shot <url> (existing behavior)
                        url = args if args.startswith("http") else "https://" + args
                        bot.send_message(f"[WAIT] Taking screenshot of {url}...")
                        screenshot_path = screenshotter.take_browser_screenshot(url)
                        caption = f"Screenshot: {url}"

                    if screenshot_path:
                        bot.send_photo(screenshot_path, caption=caption)
                    else:
                        bot.send_message("[ERROR] Screenshot failed. Check logs.")

                elif text.startswith("/"):
                    bot.send_message("Unknown command. Available:\n/status\n/pr <description>\n/shot <url>")

                else:
                    # Check for natural language screenshot commands
                    is_screenshot, keyword, url = parse_screenshot_intent(text)

                    if is_screenshot:
                        if url:
                            # External URL from natural language
                            url = url if url.startswith("http") else "https://" + url
                            bot.send_message(f"[WAIT] Taking screenshot of {url}...")
                            screenshot_path = screenshotter.take_browser_screenshot(url)
                            caption = f"Screenshot: {url}"
                        else:
                            # Local HTML file
                            target = keyword or 'default'
                            bot.send_message(f"[WAIT] Taking screenshot of {target} page...")
                            screenshot_path = screenshotter.take_project_screenshot(target)
                            caption = f"Screenshot: {target.capitalize()} page"

                        if screenshot_path:
                            bot.send_photo(screenshot_path, caption=caption)
                        else:
                            bot.send_message("[ERROR] Screenshot failed. Check logs.")

                        continue  # Skip Claude processing

                    # If not a screenshot command, continue to Claude handler

                    bot.send_message("[WAIT] Claude is thinking...")
                    response = claude.run(text)
                    bot.send_message(response)
                    print(f"[{datetime.now()}] Responded ({len(response)} chars)")

            time.sleep(1)

        except KeyboardInterrupt:
            bot.send_message("[OFFLINE] Claude Bridge is going OFFLINE")
            print("\nShutting down...")
            cleanup_and_exit()
        except Exception as e:
            print(f"[ERROR] Error in main loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
