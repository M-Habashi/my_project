# Claude Telegram Bridge - Setup Guide

## Overview
The Claude Telegram Bridge allows you to interact with Claude Code CLI through Telegram messages. Send messages to your bot, and Claude will respond!

## Prerequisites
- Python 3.8+
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- A Telegram Bot Token (from BotFather)
- Your Telegram Chat ID

## Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/start`
3. Send `/newbot`
4. Follow the prompts to create your bot
5. **Copy your bot token** (format: `123456789:ABCDEFGHijklmnopqrstuvwxyz`)

## Step 2: Get Your Chat ID

1. Send a message to your newly created bot
2. Open this URL in your browser:
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
   Replace `YOUR_TOKEN` with your actual bot token

3. Look for `"id": 5653048942` in the response - that's your Chat ID
4. Or run in command line:
   ```
   curl -s "https://api.telegram.org/botYOUR_TOKEN/getUpdates" | findstr /C:"\"id\""
   ```

## Step 3: Configure the Bridge

1. Open `config.env` and fill in:
   ```
   TG_BOT_TOKEN=your_token_here
   TG_CHAT_ID=your_chat_id_here
   TG_ALLOWED_USER_ID=your_chat_id_here
   REPO_DIR=C:\path\to\your\project
   ```

2. Make sure there are **NO QUOTES** around the values

## Step 4: Install Prerequisites (Optional)

Run the setup script:
```bash
python setup_prerequisites.py
```

Or manually install requirements:
```bash
pip install requests
```

For screenshot feature:
```bash
pip install playwright
playwright install chromium
```

## Step 5: Start the Bridge

**Option 1: Double-click the batch file**
```
start_bridge.bat
```

**Option 2: Run from command line**
```bash
python claude_telegram_bridge.py
```

You should see:
```
==================================================
Claude Telegram Bridge Starting...
Repo: C:\your\repo\path
==================================================
✓ Message sent (XX chars)
```

## Step 6: Test It!

1. Open Telegram
2. Send a message to your bot
3. Claude will respond!

## Available Commands

| Command | Usage | Example |
|---------|-------|---------|
| Regular message | Claude processes it | "what is Python?" |
| `/status` | Check if bridge is online | `/status` |
| `/pr` | Create a pull request | `/pr Add dark mode` |
| `/shot` | Take a website screenshot | `/shot google.com` |

## Troubleshooting

### Bot doesn't respond
- Check config.env values are correct
- Make sure Claude CLI is installed: `claude --version`
- Restart the bridge application
- Check console for error messages

### "Claude CLI not found"
```bash
npm install -g @anthropic-ai/claude-code
```

### Permission denied errors
- Make sure REPO_DIR is a valid path
- Check folder permissions

### Screenshot feature not working
```bash
pip install playwright
playwright install chromium
```

## Features

✅ **Full Claude capabilities** - All tools and features work
✅ **Auto-permission granting** - No interactive prompts
✅ **Long polling** - Checks for messages every 30 seconds
✅ **Message chunking** - Handles long responses (4000 chars per message)
✅ **Command support** - Special commands for PR creation and screenshots
✅ **Error logging** - Detailed console output for debugging

## Security Notes

⚠️ **Important:**
- Keep your bot token secret!
- Only you can use this bot (user ID check)
- Regenerate token if exposed
- Use in trusted environments only

## Next Steps

- Customize commands in `claude_telegram_bridge.py`
- Add more features (webhooks, scheduled tasks, etc.)
- Set up auto-start on Windows startup
