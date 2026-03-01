# Selection Message Service Documentation

## Overview

The Selection Message Service is an AI-powered tool that intelligently matches text messages from general channels with media messages from media-specific channels. It uses Google's Gemini AI to analyze semantic relationships and select the most relevant media content.

## Architecture

The service consists of two main components:

1. **selection_message_service.py** - Core AI selection logic
2. **selection_action.py** - Main execution script

## How It Works

### Step 1: Text Message Collection

- Connects to configured text channels (via `TELEGRAM_CHANNEL_USERNAMES` or `TELEGRAM_CHANNEL_IDS`)
- Fetches messages from the last `TELEGRAM_WINDOW_SECONDS` (default: 3600 seconds = 1 hour)
- Extracts raw text content from each message
- Filters out empty messages

### Step 2: Media Message Collection

- Connects to configured media channels (via `TELEGRAM_CHANNEL_MEDIA_USERNAME` or `TELEGRAM_CHANNEL_MEDIA_ID`)
- Fetches messages from the last `TELEGRAM_MEDIA_WINDOW_SECONDS` (default: 1200 seconds = 20 minutes)
- Identifies messages containing media (photos, videos, documents, etc.)
- Groups album messages together (messages with the same `grouped_id`)
- Extracts metadata: message ID, media type, channel name, timestamp, text preview

### Step 3: AI Selection

- Formats text messages into a numbered list
- Formats media messages with detailed metadata
- Sends both to Gemini AI with a specialized prompt
- Gemini analyzes semantic relationships and selects the most relevant media
- Returns the selected media message or None if no match

### Step 4: Result Display

- Shows selection statistics
- Displays selected media details (ID, type, channel, preview, etc.)
- For grouped media (albums), shows group information

## Configuration

### Required Environment Variables

```bash
# Telegram API Credentials (required)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_NAME=telethon_session

# Gemini AI (required for selection)
GEMINI_API_KEY=your_gemini_api_key

# Text Channel Configuration (at least one required)
TELEGRAM_CHANNEL_USERNAMES=text_channel1,text_channel2
TELEGRAM_CHANNEL_IDS=123456789
TELEGRAM_CHANNEL_ID=123456789  # Alternative to TELEGRAM_CHANNEL_IDS

# Media Channel Configuration (at least one required)
TELEGRAM_CHANNEL_MEDIA_USERNAME=media_channel
TELEGRAM_CHANNEL_MEDIA_ID=987654321
```

### Optional Environment Variables

```bash
# Text channel settings
TELEGRAM_WINDOW_SECONDS=3600        # 1 hour
TELEGRAM_FETCH_LIMIT=200            # Max messages to fetch

# Media channel settings
TELEGRAM_MEDIA_WINDOW_SECONDS=1200  # 20 minutes
TELEGRAM_MEDIA_FETCH_LIMIT=100      # Max messages to fetch
```

## Usage

### Basic Usage

1. **Configure environment variables** in `.env` file:

```bash
cp .env.example .env
# Edit .env with your values
```

2. **Run the service**:

```bash
python selection_action.py
```

### Example Output

```
Selection Message Service: Running single selection cycle...
================================================================================
TEXT CHANNELS:
  Usernames: news_channel, updates_channel
  IDs:
  Time window: 3600 seconds (60 minutes)
  Fetch limit: 200

MEDIA CHANNELS:
  Usernames: photos_channel
  IDs:
  Time window: 1200 seconds (20 minutes)
  Fetch limit: 100
================================================================================

Resolved TEXT channels:
  - News Channel (id: 123456789)
  - Updates Channel (id: 987654321)

Resolved MEDIA channels:
  - Photos Channel (id: 111222333)
================================================================================

Fetching text messages...
[TEXT] 01/03/2026 10:30 Breaking news: Market reaches new high...
[TEXT] 01/03/2026 10:35 Analysis of recent economic trends...
Found 2 text messages

Fetching media messages...
[MEDIA] 01/03/2026 10:32 Photos Channel - PHOTO: Stock market chart showing growth
[MEDIA GROUP] 01/03/2026 10:40 Photos Channel - PHOTO, VIDEO [Album: 6751234567890, 3 items]: Economic report visuals
Found 2 media messages

Selecting most relevant media using Gemini AI...
[GEMINI SELECTION] Raw response: 1
[SELECTION] Gemini selected media #1: ID=100, Type=photo

========================================================================
SELECTION MESSAGE SERVICE - RESULTS
========================================================================
Text messages analyzed: 2
Media messages analyzed: 2
========================================================================
SELECTED MEDIA:
  Media ID: 100
  Message IDs: 100
  Type: PHOTO
  Channel: Photos Channel
  Time: 01/03/2026 10:32
  Preview: Stock market chart showing growth
========================================================================

Selection cycle complete.
```

## Use Cases

### 1. News Aggregation

Match news text articles with relevant image or video content from media channels.

```python
# Text Channel: News articles
# Media Channel: News photos/videos
# Output: Best matching visual for the news story
```

### 2. Content Curation

Find the best visual representation for text content across channels.

```python
# Text Channel: Blog posts
# Media Channel: Stock photos/graphics
# Output: Most relevant image for the blog
```

### 3. Cross-Channel Matching

Link related content from different specialized channels.

```python
# Text Channel: Product announcements
# Media Channel: Product photography
# Output: Matching product image
```

### 4. Automated Content Selection

Let AI choose the best media for your content automatically.

```python
# Text Channel: Social media posts
# Media Channel: Media library
# Output: AI-selected best match
```

## API Reference

### `select_most_relevant_media(model, text_messages, media_messages)`

Compares text messages with media messages using Gemini AI.

**Parameters:**

- `model` (GenerativeModel): Gemini AI model instance
- `text_messages` (list[str]): List of text message contents
- `media_messages` (list[dict]): List of media message metadata dictionaries

**Returns:**

- `dict` or `None`: Selected media message dictionary or None if no match

**Media Message Dictionary Structure:**

```python
{
    "message_id": 123,
    "message_ids": [123, 124, 125],  # Multiple for albums
    "channel_id": 987654321,
    "channel_name": "Media Channel",
    "timestamp": "01/03/2026 10:30",
    "media_types": ["photo", "video"],
    "media_type": "photo, video",
    "grouped_id": 6751234567890,  # Or None
    "text_preview": "Caption text...",
    "message": <Message object>,
    "messages": [<Message objects>]
}
```

### `format_selection_result(text_message_count, media_message_count, selected_media)`

Formats selection results for display.

**Parameters:**

- `text_message_count` (int): Number of text messages analyzed
- `media_message_count` (int): Number of media messages analyzed
- `selected_media` (dict or None): Selected media message

**Returns:**

- `str`: Formatted result string

## Advanced Usage

### Using in Your Own Scripts

```python
from selection_message_service import (
    create_gemini_model,
    select_most_relevant_media,
    format_selection_result
)

# Initialize Gemini model
model = create_gemini_model()

# Your text messages (list of strings)
text_messages = [
    "Breaking news about technology",
    "New AI breakthrough announced"
]

# Your media messages (list of dicts)
media_messages = [
    {
        "message_id": 100,
        "channel_name": "Tech Photos",
        "media_type": "photo",
        "text_preview": "AI robot image"
    }
]

# Select most relevant
selected = select_most_relevant_media(model, text_messages, media_messages)

if selected:
    print(f"Selected: {selected['media_type']} - {selected['text_preview']}")
else:
    print("No relevant media found")
```

### Integration with Other Services

```python
from selection_action import main as run_selection
from facebook_service import post_to_facebook

# Run selection
selected_media = await run_selection()

# Post selected media to Facebook
if selected_media:
    message_ids = selected_media['message_ids']
    # Download and post media...
```

## Troubleshooting

### "No valid text channel targets found"

- Check `TELEGRAM_CHANNEL_USERNAMES` or `TELEGRAM_CHANNEL_IDS` in .env
- Ensure your account has access to these channels
- Verify channel names don't include the @ symbol

### "No valid media channel targets found"

- Check `TELEGRAM_CHANNEL_MEDIA_USERNAME` or `TELEGRAM_CHANNEL_MEDIA_ID`
- Ensure your account has access to the media channels

### "Gemini is disabled (missing GEMINI_API_KEY)"

- Add your Gemini API key to .env
- Get a key from https://aistudio.google.com/apikey

### "Gemini returned unparseable response"

- The AI may be having difficulty with the content
- Try adjusting your channel selections or time windows
- Check if messages have sufficient content for comparison

### No messages found

- Adjust `TELEGRAM_WINDOW_SECONDS` or `TELEGRAM_MEDIA_WINDOW_SECONDS`
- Increase fetch limits
- Verify channels have recent activity

## Performance Tips

1. **Time Window Balance**:
   - Shorter windows = faster execution, fewer messages
   - Longer windows = more context, better matching

2. **Fetch Limits**:
   - Higher limits = more comprehensive but slower
   - Lower limits = faster but may miss relevant content

3. **Channel Selection**:
   - Focus on specific, relevant channels
   - Avoid overly broad channels with mixed content

## Security

- Never commit `.env` file or session files
- Keep `GEMINI_API_KEY` and `TELEGRAM_API_*` credentials secure
- Session files contain authentication tokens - protect them

## Limitations

- Requires active Telegram session (must authenticate once)
- Gemini API rate limits apply
- Selection quality depends on message content quality
- Only analyzes text previews from media messages (not full media content)

## Future Enhancements

- [ ] Support for multiple media types preferences
- [ ] Custom selection criteria/prompts
- [ ] Caching and result persistence
- [ ] Webhook integration for real-time selection
- [ ] Batch processing mode
- [ ] Image analysis integration (OCR, object detection)
- [ ] Similarity scoring and confidence levels
- [ ] Multi-language support

## License

MIT

## Support

For issues or questions, please refer to the main README.md or open an issue on GitHub.
