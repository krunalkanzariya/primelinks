# Amazon Affiliate Telegram Bot

A modern Telegram bot that automatically generates Amazon affiliate links and provides random product deals to users. The bot includes an admin panel for management and monitoring.

## Features

- Welcome message for new users
- Random product deals command (/deals)
- Automatic affiliate link generation
- Modern admin panel
- AI-based product recommendations
- Secure authentication system

## Setup

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with the following variables:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
AMAZON_ACCESS_KEY=your_amazon_access_key
AMAZON_SECRET_KEY=your_amazon_secret_key
AMAZON_ASSOCIATE_TAG=krunalweb20-21
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_admin_password
```

4. Run the bot:
```bash
python main.py
```

5. Run the admin panel:
```bash
python admin_panel.py
```

## Usage

### Bot Commands
- `/start` - Welcome message and bot introduction
- `/deals` - Get random Amazon product deals
- `/help` - Show available commands

### Admin Panel
Access the admin panel at `http://localhost:8000/admin`
- Monitor bot statistics
- Manage product categories
- View user interactions
- Configure bot settings

## Security
- Admin panel protected with secure authentication
- Environment variables for sensitive data
- Rate limiting implemented
- Input validation and sanitization

## License
MIT License 