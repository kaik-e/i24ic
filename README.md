# VNC Phishing Toolkit

A controlled test environment for studying Browser-in-the-Middle (BitM) phishing techniques with Telegram integration for real-time alerts.

> ⚠️ **DISCLAIMER**: This tool is for **educational and authorized security testing only**. Unauthorized use against systems you don't own or have permission to test is illegal.

## Overview

This toolkit demonstrates how noVNC-based phishing works:
1. Victim connects to a phishing URL
2. They see a real browser (Firefox) via noVNC streaming
3. Victim interacts normally - enters credentials, completes MFA
4. All cookies and session data are captured
5. Attacker receives real-time Telegram alerts
6. Full browser profile can be exported for session takeover

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         NGINX                                │
│                    (Reverse Proxy)                           │
└─────────────────┬───────────────────────┬───────────────────┘
                  │                       │
                  ▼                       ▼
┌─────────────────────────┐   ┌─────────────────────────────┐
│      CONTROLLER         │   │         noVNC               │
│  - Dashboard            │   │  - Xvfb (Virtual Display)   │
│  - Session Management   │   │  - Firefox Browser          │
│  - Telegram Alerts      │   │  - Cookie Monitor           │
│  - API                  │   │  - Profile Export           │
└─────────────────────────┘   └─────────────────────────────┘
           │                              │
           └──────────────┬───────────────┘
                          ▼
                    ┌───────────┐
                    │   LOOT    │
                    │ (Cookies, │
                    │ Profiles) │
                    └───────────┘
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Telegram Bot (for alerts)

### 1. Clone and Setup

```bash
cd /path/to/vnc
chmod +x setup.sh
./setup.sh install
```

### 2. Configure Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot` and follow prompts
3. Copy the bot token

4. Message [@userinfobot](https://t.me/userinfobot) to get your chat ID

5. Edit `.env`:
```bash
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
TARGET_URL=https://accounts.google.com
```

### 3. Test Telegram Connection

```bash
./setup.sh test-telegram
```

### 4. Run

```bash
./setup.sh run
```

### 5. Access

- **Dashboard**: http://localhost:80
- **noVNC Session**: http://localhost:80/novnc/vnc.html

## Usage

### Monitoring Sessions

The dashboard at `http://localhost/` shows:
- Active sessions
- Cookie counts
- Authentication status
- Session takeover options

### Telegram Alerts

You'll receive alerts for:
- 🟢 New session started
- 🍪 Cookies detected
- 🔐 Auth cookies captured
- 📦 Profile exported

### Session Takeover

When auth cookies are captured:

1. Exported profile is saved to `./loot/<session_id>/`
2. Load in Firefox:
   ```bash
   # Linux
   firefox -profile ./loot/session_1/profile_*/  --allow-downgrade
   
   # macOS
   /Applications/Firefox.app/Contents/MacOS/firefox -profile ./loot/session_1/profile_*/
   ```

## Commands

```bash
./setup.sh install        # Initial setup
./setup.sh run            # Start services
./setup.sh stop           # Stop services
./setup.sh logs           # View logs
./setup.sh logs controller # View specific service logs
./setup.sh status         # Container status
./setup.sh clean          # Remove everything
./setup.sh test-telegram  # Test Telegram connection
```

## Configuration

### Environment Variables (`.env`)

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |
| `TARGET_URL` | Target website to display |
| `PHISHING_DOMAIN` | Domain for phishing URLs |
| `NUM_SESSIONS` | Number of concurrent sessions |

### Customization

- **Target Site**: Change `TARGET_URL` in `.env`
- **Resolution**: Edit `novnc/supervisord.conf` Xvfb settings
- **Firefox Prefs**: Edit `novnc/scripts/start_firefox.sh`

## How It Works

### Cookie Capture

The `cookie_monitor.py` script:
1. Monitors Firefox's `cookies.sqlite` database
2. Detects authentication-related cookies (session, auth, token, etc.)
3. Reports to controller via API
4. Triggers Telegram alerts
5. Exports full browser profile

### Session Detection

Interesting cookies are identified by patterns:
- `session`, `auth`, `token`, `sid`
- `login`, `user`, `jwt`, `oauth`
- `saml`, `sso`, `credential`

## Troubleshooting

### noVNC not loading
```bash
./setup.sh logs novnc
# Check if Xvfb and Firefox started
```

### Telegram not working
```bash
./setup.sh test-telegram
# Verify bot token and chat ID
```

### No cookies captured
- Ensure Firefox is running: `./setup.sh logs novnc`
- Check cookie monitor: `docker exec -it vnc-novnc-1 tail -f /var/log/supervisor/cookie_monitor.log`

## Security Notes

- Uses self-signed certificates by default
- For real testing, use proper TLS certs
- Never use against unauthorized targets
- All data is stored locally in `./loot/`

## References

- [EvilnoVNC](https://github.com/JoelGMSec/EvilnoVNC)
- [EvilKnievelnoVNC](https://github.com/ms101/EvilKnievelnoVNC)
- [NoPhish](https://github.com/powerseb/NoPhish)
- [mrd0x BitM Research](https://mrd0x.com/bypass-2fa-phishing-with-novnc/)

## License

For educational purposes only. Use responsibly.
