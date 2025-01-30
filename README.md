# trench.bot Discord Bot

A simple Discord bot that listens for messages from Rick (a popular crypto metadata bot) and responds with formatted trench.bot metadata about the bundles. When Rick posts information about a token contract, this bot automatically analyzes the token's bundles.

## Add to your server

If you want to add this bot to your server, you can do so by clicking [this link](https://discord.com/oauth2/authorize?client_id=1334376887421505560).

## Features

- Automatically detects messages from Rick bot
- Parses contract addresses and chain information from Rick's embeds
- Queries trench.bot for bundle metadata

## TODO

- [ ] Add support for pumpfun pre-migrations on Rick

## Prerequisites

- Python 3.8 or higher
- A Discord bot token with MESSAGE_CONTENT intent enabled

## Setup

1. Create a Discord Bot:

   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to the Bot section
   - Enable MESSAGE_CONTENT intent
   - Copy the bot token

2. Clone this repository:

```bash
git clone https://github.com/bl-nkd-v/trench-radar-discord-bot.git
cd trench-radar-discord-bot
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file:

```bash
cp .env.example .env
```

5. Edit the `.env` file with your:

   - Discord bot token (from step 1)

6. Run the bot:

```bash
python bot.py
```

## Configuration

The bot uses environment variables for configuration:

- `DISCORD_BOT_TOKEN`: Your Discord bot token
- `ENVIRONMENT`: The environment (development/production)

## Supported Chains

The bot currently supports the following chains:

- Solana (SOL)

## Contributing

Feel free to submit issues and pull requests to improve the bot.

## License

MIT License
