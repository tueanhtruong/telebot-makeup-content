# TeleNotiApp - Copilot Instructions

## Project Overview

TeleNotiApp is a Python-based application that integrates Telegram, Gemini AI, and Facebook APIs to provide intelligent notification and interaction capabilities.

## Technology Stack

- **Language**: Python 3.8+
- **Primary Library**: Telethon (Telegram client)
- **AI Integration**: Google Gemini API
- **Social Media Integration**: Facebook API
- **Additional**: asyncio for async operations, environment variables for secrets

## Key Instructions for Code Generation

### Architecture & Structure

- Organize code into logical modules:
  - `telegram/` - Telethon client setup and handlers
  - `ai/` - Gemini API integration
  - `facebook/` - Facebook API integration
  - `config/` - Configuration and settings
  - `utils/` - Helper functions and utilities
  - `main.py` or `app.py` - Entry point

### Telegram Integration (Telethon)

- Use async/await patterns for event handlers
- Handle session files securely (ignore in git)
- Implement proper error handling for connection issues
- Use event filters for message routing
- Implement rate limiting to respect Telegram API limits

### Gemini AI Integration

- Store API keys in environment variables (.env file)
- Implement retry logic for API calls
- Handle token limits and context window constraints
- Cache responses when appropriate
- Implement proper error handling for API failures

### Facebook API Integration

- Handle OAuth tokens securely
- Implement proper permission scopes
- Include error handling for API authentication
- Log API interactions for debugging

### Code Standards

- Follow PEP 8 style guide
- Use type hints for function signatures
- Include docstrings for all functions and classes
- Use descriptive variable names
- Implement proper logging throughout

### Configuration Management

- Use environment variables for:
  - API keys (TELEGRAM_API_ID, TELEGRAM_API_HASH, GEMINI_API_KEY, FACEBOOK_TOKEN)
  - Database URLs
  - Service endpoints
- Create a `.env.example` file documenting required variables
- Never commit sensitive credentials

### Error Handling

- Implement try-catch blocks for external API calls
- Log errors with context information
- Gracefully handle connection failures
- Implement exponential backoff for retries

### Dependencies Management

- Use requirements.txt for dependency pinning
- Document Python version requirements
- Keep dependencies up-to-date and secure

### Testing

- Write unit tests for utility functions
- Integration tests for API interactions
- Mock external API calls in tests
- Use pytest or unittest framework

## Common Patterns

### Telethon Event Handler

```python
@client.on(events.NewMessage(pattern=r'/command'))
async def handler(event):
    # Handle incoming message
    pass
```

### Gemini API Call Pattern

Use async-compatible patterns and proper error handling.

### Logging

Use Python's logging module consistently throughout the app.

## Important Notes

- Respect Telegram's API rate limits
- Handle Gemini token consumption wisely
- Implement user authentication where necessary
- Document all external API interactions
- Keep API integrations modular for easy updates

## File Naming Conventions

- Python modules: `snake_case.py`
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

## When Suggesting Code

- Consider async/await when dealing with I/O operations
- Include error handling and logging
- Provide configuration examples
- Document API interactions
- Suggest environment variable usage for secrets
