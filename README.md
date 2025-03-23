# Aiblushi Bot

Aiblushi Bot is a Telegram bot designed to help manage dehydration processes, track working sessions, and generate reports for small business operations.

## Features

- **User Authentication**: Admin approval system for new users
- **Dehydrator Management**: Track and control dehydrator sessions
- **Work Tracking**: Monitor different types of work including:
  - Production
  - Packaging
  - Sales
  - Other work types
- **Reporting**: Generate detailed reports on work sessions by month
- **Multi-user Collaboration**: Support for working with partners

## Getting Started

### Prerequisites

- Python 3.8 or higher
- PostgreSQL database

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/Mak5er/AiblushiBot.git
   cd AiblushiBot
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file with the following variables:
   ```
   BOT_TOKEN=your_telegram_bot_token
   ADMIN_ID=your_telegram_id
   DATABASE_URL=postgresql+asyncpg://username:password@host:port/dbname
   CHAT_ID=your_notification_chat_id
   ```

### Running the Bot

```
python main.py
```

## Usage

1. **User Registration**:
   - Start the bot by sending `/start` command
   - An admin will need to approve your access

2. **Dehydrator Management**:
   - Select "🍇 Дегідратори" from the main menu
   - Choose a dehydrator number
   - Set drying time

3. **Work Tracking**:
   - Select the appropriate work type from the main menu
   - Track time spent on different activities
   - Add partner if working with someone

4. **Reporting**:
   - Select "📊 Звітність" from the main menu
   - Choose the month and report type
   - View detailed work summary

## Project Structure

- `main.py` - Entry point of the application
- `config.py` - Configuration settings
- `handlers/` - Request handlers for different bot functions
- `services/` - Business logic and database operations
- `keyboards/` - Telegram keyboard layouts
- `utils/` - Helper functions
- `middleware/` - Middleware for bot requests

## Environment Variables

| Variable | Description |
|----------|-------------|
| BOT_TOKEN | Telegram Bot API token from BotFather |
| ADMIN_ID | Telegram user ID of the administrator |
| DATABASE_URL | PostgreSQL connection string |
| CHAT_ID | Telegram chat ID for notifications |

## License

This project is licensed under the MIT License - see the LICENSE file for details. 