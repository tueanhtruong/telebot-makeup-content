# TeleNotiApp - Telegram Message Listener

A Python server application that listens to messages from Telegram channels using the Telethon library, with support for Gemini AI and Facebook API integrations.

## Setup

### 1. Get Telegram API Credentials

1. Go to [https://my.telegram.org/apps](https://my.telegram.org/apps)
2. Log in with your Telegram account
3. Create a new application
4. Copy your **API ID** and **API Hash**

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and fill in your credentials:

```bash
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE_NUMBER=+1234567890
TELEGRAM_CHANNEL_IDS=123456789,987654321
```

### 4. Run the Application

```bash
python main.py
```

On first run, you'll be prompted to authenticate with your phone number. Follow the Telegram authentication flow:

1. You'll receive a code via Telegram
2. Enter the code when prompted
3. If you have 2FA enabled, you may be asked for a password

## Usage

### Listening to Specific Channels

Set the `TELEGRAM_CHANNEL_IDS` environment variable with comma-separated channel IDs:

```
TELEGRAM_CHANNEL_IDS=123456789,987654321
```

### Getting Channel ID

To get a channel ID:

1. Forward a message from the channel to [@userinfobot](https://t.me/userinfobot)
2. The bot will show you the channel ID

### Listening to All Messages

Leave `TELEGRAM_CHANNEL_IDS` empty to listen to all personal messages.

## GitHub Actions Automation

The project includes a GitHub Actions workflow that automatically polls Telegram channels every 2 hours and posts to Facebook.

### Setting Up GitHub Actions

1. **Push the repository to GitHub**

2. **Configure GitHub Secrets**

   Go to your repository → Settings → Secrets and variables → Actions, then add the following secrets:

   **Required secrets:**
   - `TELEGRAM_API_ID` - Your Telegram API ID
   - `TELEGRAM_API_HASH` - Your Telegram API Hash
   - `TELEGRAM_SESSION_BASE64` - Base64-encoded session file (see below)

   **Optional secrets:**
   - `TELEGRAM_SESSION_NAME` - Session name (default: `telethon_session`)
   - `TELEGRAM_CHANNEL_USERNAMES` - Comma-separated channel usernames (default: `vietnam_wallstreet`)
   - `TELEGRAM_CHANNEL_IDS` - Comma-separated channel IDs
   - `TELEGRAM_CHANNEL_ID` - Single channel ID
   - `TELEGRAM_WINDOW_SECONDS` - Time window in seconds (default: `7200`)
   - `TELEGRAM_FETCH_LIMIT` - Message fetch limit (default: `400`)
   - `GEMINI_API_KEY` - Google Gemini API key for message summarization
   - `FACEBOOK_TOKEN` - Facebook page access token
   - `FACEBOOK_PAGE_ID` - Facebook page ID

3. **Create the Telegram Session File**

   First, run the app locally to create a session file:

   ```bash
   python action.py
   ```

   Then convert the session file to base64:

   ```bash
   # On macOS/Linux:
   base64 -i telethon_session.session | pbcopy

   # On Windows (PowerShell):
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("telethon_session.session")) | Set-Clipboard
   ```

   Add the base64 string as `TELEGRAM_SESSION_BASE64` secret in GitHub.

4. **Trigger the Workflow**

   The workflow runs automatically every 2 hours, or you can trigger it manually:
   - Go to Actions tab in your repository
   - Select "Telegram Poll and Post"
   - Click "Run workflow"

### Workflow Features

- ✅ Runs every 2 hours automatically
- ✅ Manual trigger via workflow_dispatch
- ✅ Automatic dependency caching for faster builds
- ✅ Session file management and artifact storage
- ✅ All environment variables from GitHub secrets

## Features

- ✅ Async/await patterns for efficient I/O
- ✅ Listen to single or multiple channels
- ✅ Automatic error handling and logging
- ✅ Session persistence (no need to re-authenticate every run)
- ✅ Support for 2FA authentication
- ✅ Environment variable configuration
- ✅ Support for Gemini AI integration
- ✅ Support for Facebook API integration

## Project Structure

```
TeleNotiApp/
├── main.py                 # Main server application
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── .gitignore             # Git ignore rules
├── .copilot-instructions  # AI assistant instructions
└── README.md              # This file
```

## Future Modules

The application is structured to support:

- **AI Integration**: Process messages with Gemini AI
- **Facebook Integration**: Cross-post to Facebook
- **Database**: Store messages for analysis
- **Notifications**: Send alerts based on message content
- **Webhooks**: Forward messages to external services

## Troubleshooting

### "Wrong phone number"

- Ensure your phone number includes the country code (e.g., +1 for US)

### "Session password needed"

- You have 2FA enabled on your Telegram account
- Enter your 2FA password when prompted

### "No such session"

- Delete the `telethon_session*` files and run again to re-authenticate

### No messages being received

- Verify the channel ID is correct
- Ensure the bot/account has access to the channel
- Check that the channel isn't archived

## Security Notes

- Never commit `.env` file to version control
- Telethon session files are created automatically and ignored by git
- Keep your API credentials secure
- Use environment variables for all sensitive data
- Don't share your phone number or API credentials

## Requirements

- Python 3.8+
- Telethon 1.35.0+
- python-dotenv 1.0.1+
- Active Telegram account

## License

MIT

## Contributing

Contributions welcome! Please follow PEP 8 style guide and include docstrings.
