import os
import re
import asyncio
from typing import Optional, Tuple
import discord
from discord.ext import commands
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Configure intents
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True  # Need this for reaction handling

# Initialize bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Constants
RICK_BOT_ID = 1081815963990761542
TRASH_EMOJI = "🗑️"
REACTION_TIMEOUT = 30  # seconds


def parse_contract_info(message: discord.Message) -> Optional[Tuple[str, str]]:
    """
    Parse chain and contract address from Rick bot's message.
    Returns tuple of (chain, contract_address) if found, None otherwise.
    """
    if len(message.embeds) == 0:
        return None

    for embed in message.embeds:
        if not embed.description:
            continue

        # Split description into lines
        lines = embed.description.split("\n")
        if not lines:
            continue

        # Get chain from first line
        first_line = lines[0].lower()

        if "solana" not in first_line:
            return None

        # Look for contract address in a code block
        # Reverse the lines since contract usually appears near the bottom
        for line in reversed(lines):
            # For Solana addresses (base58 in code block)
            matches = re.findall(r"`([1-9A-HJ-NP-Za-km-z]{32,44})`", line)
            for match in matches:
                # Verify it's a valid base58 address (basic check)
                if len(match) >= 32 and len(match) <= 44:
                    return match

    return None


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")


async def remove_reaction_after_delay(message: discord.Message):
    """Remove our trash reaction after the specified timeout."""
    await asyncio.sleep(REACTION_TIMEOUT)
    try:
        # Try to fetch the message to see if it still exists
        channel = message.channel
        await channel.fetch_message(message.id)
        # If message exists, remove our reaction
        await message.remove_reaction(TRASH_EMOJI, bot.user)
    except discord.NotFound:
        # Message was deleted, nothing to do
        return
    except Exception as e:
        print(f"Error removing reaction: {e}")


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """Handle reaction adds to manage message deletion."""
    # Ignore our own reactions
    if payload.user_id == bot.user.id:
        return

    # Only handle trash emoji reactions
    if str(payload.emoji) != TRASH_EMOJI:
        return

    # Get the channel and message
    channel = bot.get_channel(payload.channel_id)
    if not channel:
        return

    try:
        # Get our bot's message that was reacted to
        message = await channel.fetch_message(payload.message_id)
        if not message or message.author != bot.user:
            return

        # Check if this is a reply
        if not message.reference:
            return

        try:
            # Try to get Rick's message
            rick_message = await channel.fetch_message(message.reference.message_id)
            if not rick_message or rick_message.author.id != RICK_BOT_ID:
                await message.delete()
                return
        except discord.NotFound:
            # Rick's message was deleted
            await message.delete()
            return

        try:
            # Try to get the original message Rick replied to
            original_message = await channel.fetch_message(
                rick_message.reference.message_id
            )
            if not original_message:
                await message.delete()
                return

            # Check if the reaction was added by the original message author
            if payload.user_id == original_message.author.id:
                await message.delete()
        except discord.NotFound:
            # Original message was deleted
            await message.delete()

    except discord.NotFound:
        pass  # Our message was already deleted
    except Exception as e:
        print(f"Error handling reaction: {e}")


def get_trench_bundle_metadata(contract_address: str) -> Optional[str]:
    url = f"https://trench.bot/api/bundle/bundle_advanced/{contract_address}"
    headers = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Pragma": "no-cache",
        "Referer": f"https://trench.bot/bundles/{contract_address}",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    }
    response = requests.get(url, headers=headers)
    return response.json()


@bot.event
async def on_message(message: discord.Message):
    # Check environment and guild ID
    environment = os.getenv("ENVIRONMENT", "production")
    development_guild_id = int(os.getenv("DEVELOPMENT_GUILD_ID", "0"))
    if environment == "development" and message.guild.id != development_guild_id:
        return

    # Only process messages from Rick bot
    if message.author.id != RICK_BOT_ID:
        return

    # Try to parse contract info
    result = parse_contract_info(message)
    if not result:
        return

    contract_address = result

    try:
        # Send initial "checking" message
        initial_message = await message.reply("🔍 Checking bundle data...")

        # Get trench bundle metadata
        trench_bundle_metadata = get_trench_bundle_metadata(contract_address)
        if not trench_bundle_metadata:
            error_msg = "❌ Failed to fetch bundle data. Try again later."
            await initial_message.edit(content=error_msg)
            await asyncio.sleep(10)  # Wait 10 seconds before deleting
            await initial_message.delete()
            return

        # Create embed
        embed = discord.Embed(
            color=discord.Color.blue(),
        )

        # Currently Held Bundles
        currently_held_emoji = (
            "✅"
            if trench_bundle_metadata["total_holding_percentage"] < 3
            else (
                "⚠️" if trench_bundle_metadata["total_holding_percentage"] < 10 else "🚨"
            )
        )
        currently_held_bundles = f"{currently_held_emoji} Currently Held Bundles: **{trench_bundle_metadata['total_holding_percentage']:.2f}%**"
        embed.add_field(
            name="Current Bundles", value=currently_held_bundles, inline=False
        )

        # Initial Bundle Stats
        initial_bundle_stats = f"📦 {trench_bundle_metadata['total_bundles']} bundles, **{trench_bundle_metadata['total_percentage_bundled']:.1f}%** with **{trench_bundle_metadata['total_sol_spent']:.2f}** SOL\n"
        embed.add_field(
            name="Initial Bundles", value=initial_bundle_stats, inline=False
        )

        # Creator Stats
        creator = trench_bundle_metadata["creator_analysis"]

        # Warnings (if any, shown at bottom)
        risk_level_emoji = {
            "LOW": "✅",
            "MEDIUM": "⚠️",
            "HIGH": "🚨",
        }
        creator_info = f"{risk_level_emoji[creator['risk_level']]} Risk Level: {creator['risk_level']}"
        if creator["warning_flags"]:
            warnings = " • ".join(flag for flag in creator["warning_flags"] if flag)
            if warnings:
                creator_info = f"{creator_info}\n⚠️ Warnings: {warnings}"
        embed.add_field(name="Creator Info", value=creator_info, inline=False)

        # Add footer
        embed.set_footer(
            text="Powered by trench.bot • Made by blankxbt",
            icon_url="https://cdn.discordapp.com/app-icons/1334376887421505560/7e1949a152920d6b50f1020e771b193d.png?size=256",
        )

        # Update the initial message with the embed
        await initial_message.edit(
            content=f"[**Trench.bot Analysis: {trench_bundle_metadata['ticker']}**](https://trench.bot/bundles/{contract_address})",
            embed=embed,
        )

        # Add trash reaction for deletion
        try:
            await initial_message.add_reaction(TRASH_EMOJI)
            asyncio.create_task(remove_reaction_after_delay(initial_message))
        except Exception as e:
            print(f"Failed to add reaction: {e}")

    except Exception as e:
        print(f"Error processing bundle data: {e}")
        try:
            error_msg = "❌ An error occurred while processing the bundle data. Try again later."
            if "initial_message" in locals():
                await initial_message.edit(content=error_msg)
                await asyncio.sleep(10)  # Wait 10 seconds before deleting
                await initial_message.delete()
        except Exception as e:
            print(f"Error handling failure: {e}")


def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN not found in environment variables")
    bot.run(token)


if __name__ == "__main__":
    main()
