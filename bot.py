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
        print(f"First line: {first_line}")

        if "solana" not in first_line:
            print(f"No solana in first line {first_line}")
            return None

        # Look for contract address in a code block
        # Reverse the lines since contract usually appears near the bottom
        for line in reversed(lines):
            # For Solana addresses (base58 in code block)
            matches = re.findall(r"`([1-9A-HJ-NP-Za-km-z]{32,44})`", line)
            for match in matches:
                # Verify it's a valid base58 address (basic check)
                if len(match) >= 32 and len(match) <= 44:
                    print(f"Found contract address: {match}")
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
    # Example response
    # {
    #     "bonded": false,
    #     "bundles": {
    #         "317279880": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 0,
    #                     "regular": 4,
    #                     "sniper": 0
    #                 },
    #                 "copytrading_groups": {
    #                     "DjSnzgruKsGtpKFuf1QSqiRDffkd45gc3KfUW9nddX2j": "group_0",
    #                     "GWkb2gT4vkeLGiuVzBPMYHQDk6zZnL4uFXsvGVmDQ7W6": "group_0",
    #                     "H65GM32ms2LDf5486tmYDtd6fZVNG6HnRyjmF2GdgtiJ": "group_0"
    #                 },
    #                 "is_likely_bundle": false,
    #                 "primary_category": "regular"
    #             },
    #             "holding_amount": 0,
    #             "holding_percentage": 0.0,
    #             "token_percentage": 14.8591147819156,
    #             "total_sol": 9.311910592,
    #             "total_tokens": 148591147819156,
    #             "unique_wallets": 4,
    #             "wallet_categories": {
    #                 "431qunLZiXiatZvepvkNGfECwzqeEg9eZj6C4WxmnsBK": "regular",
    #                 "DjSnzgruKsGtpKFuf1QSqiRDffkd45gc3KfUW9nddX2j": "regular",
    #                 "GWkb2gT4vkeLGiuVzBPMYHQDk6zZnL4uFXsvGVmDQ7W6": "regular",
    #                 "H65GM32ms2LDf5486tmYDtd6fZVNG6HnRyjmF2GdgtiJ": "regular"
    #             },
    #             "wallet_info": {
    #                 "431qunLZiXiatZvepvkNGfECwzqeEg9eZj6C4WxmnsBK": {
    #                     "sol": 3.430693069,
    #                     "sol_percentage": 36.84198892488679,
    #                     "token_percentage": 34.96620933844746,
    #                     "tokens": 51956691804848
    #                 },
    #                 "DjSnzgruKsGtpKFuf1QSqiRDffkd45gc3KfUW9nddX2j": {
    #                     "sol": 1.960405841,
    #                     "sol_percentage": 21.05267035837107,
    #                     "token_percentage": 17.81823990859349,
    #                     "tokens": 26476327201350
    #                 },
    #                 "GWkb2gT4vkeLGiuVzBPMYHQDk6zZnL4uFXsvGVmDQ7W6": {
    #                     "sol": 1.960405841,
    #                     "sol_percentage": 21.05267035837107,
    #                     "token_percentage": 24.69777955399433,
    #                     "tokens": 36698714125125
    #                 },
    #                 "H65GM32ms2LDf5486tmYDtd6fZVNG6HnRyjmF2GdgtiJ": {
    #                     "sol": 1.960405841,
    #                     "sol_percentage": 21.05267035837107,
    #                     "token_percentage": 22.517771198964716,
    #                     "tokens": 33459414687833
    #                 }
    #             }
    #         },
    #         "317279884": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 0,
    #                     "regular": 3,
    #                     "sniper": 3
    #                 },
    #                 "copytrading_groups": {
    #                     "HJgKiuWfWb6y5V8RFeC67yetfjumSUrvuxYU229rpFnM": "group_0",
    #                     "suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK": "group_0"
    #                 },
    #                 "is_likely_bundle": false,
    #                 "primary_category": "sniper"
    #             },
    #             "holding_amount": 6569544884725,
    #             "holding_percentage": 0.6569544884725,
    #             "token_percentage": 18.5172021029537,
    #             "total_sol": 17.680736914999997,
    #             "total_tokens": 185172021029537,
    #             "unique_wallets": 6,
    #             "wallet_categories": {
    #                 "6dgfLoZMDg3fyW4xYekFShDgrpoBNXQbeXVJaXAYn3RS": "regular",
    #                 "HJgKiuWfWb6y5V8RFeC67yetfjumSUrvuxYU229rpFnM": "regular",
    #                 "HWPYVL6pyKhMyQGXC7D3vF46Vm1UBqyCekJvoawsT22y": "sniper",
    #                 "J1LxUEyd2Rpu8qyneu7dcihmBsZVYpRasr6KGru9n84W": "sniper",
    #                 "oZo6aCsaVh9AxUA6Sg2cnar15aGyL8syvKomX34dRiT": "regular",
    #                 "suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK": "sniper"
    #             },
    #             "wallet_info": {
    #                 "6dgfLoZMDg3fyW4xYekFShDgrpoBNXQbeXVJaXAYn3RS": {
    #                     "sol": 1.369747929,
    #                     "sol_percentage": 7.747120131842086,
    #                     "token_percentage": 10.34345900490434,
    #                     "tokens": 19153192083743
    #                 },
    #                 "HJgKiuWfWb6y5V8RFeC67yetfjumSUrvuxYU229rpFnM": {
    #                     "sol": 3.904888006,
    #                     "sol_percentage": 22.085550080704884,
    #                     "token_percentage": 17.104086148602313,
    #                     "tokens": 31671982000000
    #                 },
    #                 "HWPYVL6pyKhMyQGXC7D3vF46Vm1UBqyCekJvoawsT22y": {
    #                     "sol": 4.073464798,
    #                     "sol_percentage": 23.038998982809087,
    #                     "token_percentage": 21.047618200258864,
    #                     "tokens": 38974300000000
    #                 },
    #                 "J1LxUEyd2Rpu8qyneu7dcihmBsZVYpRasr6KGru9n84W": {
    #                     "sol": 1.0,
    #                     "sol_percentage": 5.655872856473642,
    #                     "token_percentage": 4.73779212449304,
    #                     "tokens": 8773065429102
    #                 },
    #                 "oZo6aCsaVh9AxUA6Sg2cnar15aGyL8syvKomX34dRiT": {
    #                     "sol": 1.451446104,
    #                     "sol_percentage": 8.209194622248019,
    #                     "token_percentage": 10.34345900490434,
    #                     "tokens": 19153192083743
    #                 },
    #                 "suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK": {
    #                     "sol": 5.881190078,
    #                     "sol_percentage": 33.2632633259223,
    #                     "token_percentage": 36.42358551683711,
    #                     "tokens": 67446289432949
    #                 }
    #             }
    #         },
    #         "317279885": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 0,
    #                     "regular": 2,
    #                     "sniper": 3
    #                 },
    #                 "copytrading_groups": {
    #                     "6aCkxkvr3C3KuyWntSK19zKtkpG8DHEsbEzHHJwtHqNG": "group_0",
    #                     "Dm2Ds8sBzaCgbEq4ndyxgF43ggjrg42bXbVia56uy8qS": "group_2",
    #                     "TKKmLBiyXTXhnM7BnThv4szZps1u9XLec4jcQ45LiRf": "group_0",
    #                     "zerowfY91rbHy5bqcMToo2HaHMYFPB6UhZdTQw3av7C": "group_2"
    #                 },
    #                 "is_likely_bundle": false,
    #                 "primary_category": "sniper"
    #             },
    #             "holding_amount": 0,
    #             "holding_percentage": 0.0,
    #             "token_percentage": 8.1618825979651,
    #             "total_sol": 6.867106253999999,
    #             "total_tokens": 81618825979651,
    #             "unique_wallets": 5,
    #             "wallet_categories": {
    #                 "6aCkxkvr3C3KuyWntSK19zKtkpG8DHEsbEzHHJwtHqNG": "sniper",
    #                 "Dm2Ds8sBzaCgbEq4ndyxgF43ggjrg42bXbVia56uy8qS": "sniper",
    #                 "TKKmLBiyXTXhnM7BnThv4szZps1u9XLec4jcQ45LiRf": "regular",
    #                 "qxqoBDFmQR1TfBt9SbS9DQwkczC7WhE4JAyXyZDcjGv": "regular",
    #                 "zerowfY91rbHy5bqcMToo2HaHMYFPB6UhZdTQw3av7C": "sniper"
    #             },
    #             "wallet_info": {
    #                 "6aCkxkvr3C3KuyWntSK19zKtkpG8DHEsbEzHHJwtHqNG": {
    #                     "sol": 3.069,
    #                     "sol_percentage": 44.69131372785076,
    #                     "token_percentage": 50.66413985413689,
    #                     "tokens": 41351476141635
    #                 },
    #                 "Dm2Ds8sBzaCgbEq4ndyxgF43ggjrg42bXbVia56uy8qS": {
    #                     "sol": 0.418338437,
    #                     "sol_percentage": 6.091917345189225,
    #                     "token_percentage": 7.419055215448338,
    #                     "tokens": 6055345765631
    #                 },
    #                 "TKKmLBiyXTXhnM7BnThv4szZps1u9XLec4jcQ45LiRf": {
    #                     "sol": 2.4694017,
    #                     "sol_percentage": 35.95985861674422,
    #                     "token_percentage": 28.445032532090426,
    #                     "tokens": 23216501602222
    #                 },
    #                 "qxqoBDFmQR1TfBt9SbS9DQwkczC7WhE4JAyXyZDcjGv": {
    #                     "sol": 0.499352308,
    #                     "sol_percentage": 7.271655476557302,
    #                     "token_percentage": 6.052717182876004,
    #                     "tokens": 4940156704532
    #                 },
    #                 "zerowfY91rbHy5bqcMToo2HaHMYFPB6UhZdTQw3av7C": {
    #                     "sol": 0.411013809,
    #                     "sol_percentage": 5.985254833658499,
    #                     "token_percentage": 7.419055215448338,
    #                     "tokens": 6055345765631
    #                 }
    #             }
    #         },
    #         "317279886": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 0,
    #                     "regular": 5,
    #                     "sniper": 1
    #                 },
    #                 "copytrading_groups": {},
    #                 "is_likely_bundle": false,
    #                 "primary_category": "sniper"
    #             },
    #             "holding_amount": 0,
    #             "holding_percentage": 0.0,
    #             "token_percentage": 6.5773472115230005,
    #             "total_sol": 5.796150609,
    #             "total_tokens": 65773472115230,
    #             "unique_wallets": 6,
    #             "wallet_categories": {
    #                 "34VCi1DkWR9wxTQr2Ud5Xq92u7PbhgVLfBUtQE3U1E4f": "regular",
    #                 "4BiWbEM2RsfshiYg2ZM8xkrYRChg1zJ9KvZS8cEF6y6J": "regular",
    #                 "5Kv2yDys7PvneeQTAvNtCwfSgbt2a9U7DREy7rp19BMW": "regular",
    #                 "7UJspRAD3LTecUZWefBPx47gJXKMCv2N85V5AuFCPHFx": "regular",
    #                 "8uNLyuofKQU2SDuRsXoiEcEcZBX8mWQwQn485ymL7DUF": "sniper",
    #                 "EaLRypqyA28NAERMMojWtHikqa421fDhJqBvaz1HQ1XG": "regular"
    #             },
    #             "wallet_info": {
    #                 "34VCi1DkWR9wxTQr2Ud5Xq92u7PbhgVLfBUtQE3U1E4f": {
    #                     "sol": 0.198702944,
    #                     "sol_percentage": 3.428188075228119,
    #                     "token_percentage": 3.093410309254259,
    #                     "tokens": 2034643367167
    #                 },
    #                 "4BiWbEM2RsfshiYg2ZM8xkrYRChg1zJ9KvZS8cEF6y6J": {
    #                     "sol": 0.585473389,
    #                     "sol_percentage": 10.101072737670128,
    #                     "token_percentage": 10.288809236900562,
    #                     "tokens": 6767307074422
    #                 },
    #                 "5Kv2yDys7PvneeQTAvNtCwfSgbt2a9U7DREy7rp19BMW": {
    #                     "sol": 0.099174711,
    #                     "sol_percentage": 1.7110444101643256,
    #                     "token_percentage": 1.5341573471705896,
    #                     "tokens": 1009068554945
    #                 },
    #                 "7UJspRAD3LTecUZWefBPx47gJXKMCv2N85V5AuFCPHFx": {
    #                     "sol": 0.513756491,
    #                     "sol_percentage": 8.863753302101264,
    #                     "token_percentage": 8.100924375434072,
    #                     "tokens": 5328259235152
    #                 },
    #                 "8uNLyuofKQU2SDuRsXoiEcEcZBX8mWQwQn485ymL7DUF": {
    #                     "sol": 3.903543074,
    #                     "sol_percentage": 67.34716430485356,
    #                     "token_percentage": 67.6507318198499,
    #                     "tokens": 44496235229278
    #                 },
    #                 "EaLRypqyA28NAERMMojWtHikqa421fDhJqBvaz1HQ1XG": {
    #                     "sol": 0.4955,
    #                     "sol_percentage": 8.54877716998261,
    #                     "token_percentage": 9.33196691139062,
    #                     "tokens": 6137958654266
    #                 }
    #             }
    #         },
    #         "317279887": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 0,
    #                     "regular": 6,
    #                     "sniper": 0
    #                 },
    #                 "copytrading_groups": {
    #                     "9L3Bhxb7xj7A1JvboSvfnU9Y5ujLvhTycGFkcv2ECm5Y": "group_0",
    #                     "DjSnzgruKsGtpKFuf1QSqiRDffkd45gc3KfUW9nddX2j": "group_0",
    #                     "GWkb2gT4vkeLGiuVzBPMYHQDk6zZnL4uFXsvGVmDQ7W6": "group_0",
    #                     "H65GM32ms2LDf5486tmYDtd6fZVNG6HnRyjmF2GdgtiJ": "group_0"
    #                 },
    #                 "is_likely_bundle": false,
    #                 "primary_category": "regular"
    #             },
    #             "holding_amount": 22804198899965,
    #             "holding_percentage": 2.2804198899965,
    #             "token_percentage": 8.9628591288478,
    #             "total_sol": 10.464934638999999,
    #             "total_tokens": 89628591288478,
    #             "unique_wallets": 6,
    #             "wallet_categories": {
    #                 "9L3Bhxb7xj7A1JvboSvfnU9Y5ujLvhTycGFkcv2ECm5Y": "regular",
    #                 "ANnBPHScLMJsZpZmbzRsejAhRtgdhaFeRPZtKQXJiZgd": "regular",
    #                 "CPgpkgiEkNwX3Ag5B1wzekqq2iyAFAXTQ1tifmEJo9iU": "regular",
    #                 "DjSnzgruKsGtpKFuf1QSqiRDffkd45gc3KfUW9nddX2j": "regular",
    #                 "GWkb2gT4vkeLGiuVzBPMYHQDk6zZnL4uFXsvGVmDQ7W6": "regular",
    #                 "H65GM32ms2LDf5486tmYDtd6fZVNG6HnRyjmF2GdgtiJ": "regular"
    #             },
    #             "wallet_info": {
    #                 "9L3Bhxb7xj7A1JvboSvfnU9Y5ujLvhTycGFkcv2ECm5Y": {
    #                     "sol": 1.398073553,
    #                     "sol_percentage": 13.359601385275313,
    #                     "token_percentage": 12.6036154731489,
    #                     "tokens": 11296443000000
    #                 },
    #                 "ANnBPHScLMJsZpZmbzRsejAhRtgdhaFeRPZtKQXJiZgd": {
    #                     "sol": 0.245049504,
    #                     "sol_percentage": 2.3416247922539943,
    #                     "token_percentage": 2.2674966167690522,
    #                     "tokens": 2032325275124
    #                 },
    #                 "CPgpkgiEkNwX3Ag5B1wzekqq2iyAFAXTQ1tifmEJo9iU": {
    #                     "sol": 2.940594059,
    #                     "sol_percentage": 28.09949761216086,
    #                     "token_percentage": 24.78664108350425,
    #                     "tokens": 22215917230876
    #                 },
    #                 "DjSnzgruKsGtpKFuf1QSqiRDffkd45gc3KfUW9nddX2j": {
    #                     "sol": 1.960405841,
    #                     "sol_percentage": 18.73309207010328,
    #                     "token_percentage": 18.80443941566629,
    #                     "tokens": 16854154147957
    #                 },
    #                 "GWkb2gT4vkeLGiuVzBPMYHQDk6zZnL4uFXsvGVmDQ7W6": {
    #                     "sol": 1.960405841,
    #                     "sol_percentage": 18.73309207010328,
    #                     "token_percentage": 20.070011628804284,
    #                     "tokens": 17988468694331
    #                 },
    #                 "H65GM32ms2LDf5486tmYDtd6fZVNG6HnRyjmF2GdgtiJ": {
    #                     "sol": 1.960405841,
    #                     "sol_percentage": 18.73309207010328,
    #                     "token_percentage": 21.46779578210722,
    #                     "tokens": 19241282940190
    #                 }
    #             }
    #         },
    #         "317279888": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 0,
    #                     "regular": 2,
    #                     "sniper": 0
    #                 },
    #                 "copytrading_groups": {},
    #                 "is_likely_bundle": false,
    #                 "primary_category": "regular"
    #             },
    #             "holding_amount": 910808791989,
    #             "holding_percentage": 0.0910808791989,
    #             "token_percentage": 2.5127974456057,
    #             "total_sol": 3.332673266,
    #             "total_tokens": 25127974456057,
    #             "unique_wallets": 2,
    #             "wallet_categories": {
    #                 "4QuwcA8W8B6RNU2nnhVC9zDbBGrFRTyAznHLaVYVWXkw": "regular",
    #                 "8GFWqCRxumLXkFTaTv3cDQdFKD98RuwPJDaZAnGhxB7M": "regular"
    #             },
    #             "wallet_info": {
    #                 "4QuwcA8W8B6RNU2nnhVC9zDbBGrFRTyAznHLaVYVWXkw": {
    #                     "sol": 2.940594059,
    #                     "sol_percentage": 88.23529414059279,
    #                     "token_percentage": 87.69547618267053,
    #                     "tokens": 22036096854299
    #                 },
    #                 "8GFWqCRxumLXkFTaTv3cDQdFKD98RuwPJDaZAnGhxB7M": {
    #                     "sol": 0.392079207,
    #                     "sol_percentage": 11.76470585940722,
    #                     "token_percentage": 12.304523817329475,
    #                     "tokens": 3091877601758
    #                 }
    #             }
    #         },
    #         "317279891": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 1,
    #                     "regular": 1,
    #                     "sniper": 0
    #                 },
    #                 "copytrading_groups": {
    #                     "134m3z3vwAjvhFrFczFf4jXpVyVXoRXFRdm1pHTyjMYH": "group_0",
    #                     "CDQzwUqXAJ4v4nyuthwBXAQCAnVW3tt5XtDXECyiom5c": "group_0"
    #                 },
    #                 "is_likely_bundle": false,
    #                 "primary_category": "regular"
    #             },
    #             "holding_amount": 0,
    #             "holding_percentage": 0.0,
    #             "token_percentage": 4.9361531188589,
    #             "total_sol": 6.920792014,
    #             "total_tokens": 49361531188589,
    #             "unique_wallets": 2,
    #             "wallet_categories": {
    #                 "134m3z3vwAjvhFrFczFf4jXpVyVXoRXFRdm1pHTyjMYH": "new_wallet",
    #                 "CDQzwUqXAJ4v4nyuthwBXAQCAnVW3tt5XtDXECyiom5c": "regular"
    #             },
    #             "wallet_info": {
    #                 "134m3z3vwAjvhFrFczFf4jXpVyVXoRXFRdm1pHTyjMYH": {
    #                     "sol": 2.999999926,
    #                     "sol_percentage": 43.34763882415958,
    #                     "token_percentage": 40.83830974161527,
    #                     "tokens": 20158415000000
    #                 },
    #                 "CDQzwUqXAJ4v4nyuthwBXAQCAnVW3tt5XtDXECyiom5c": {
    #                     "sol": 3.920792088,
    #                     "sol_percentage": 56.65236117584042,
    #                     "token_percentage": 59.16169025838474,
    #                     "tokens": 29203116188589
    #                 }
    #             }
    #         },
    #         "317279892": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 1,
    #                     "regular": 2,
    #                     "sniper": 0
    #                 },
    #                 "copytrading_groups": {},
    #                 "is_likely_bundle": false,
    #                 "primary_category": "regular"
    #             },
    #             "holding_amount": 2606894330686,
    #             "holding_percentage": 0.2606894330686,
    #             "token_percentage": 1.2211186151186,
    #             "total_sol": 1.950101079,
    #             "total_tokens": 12211186151186,
    #             "unique_wallets": 3,
    #             "wallet_categories": {
    #                 "2kYrzWhnfzqUwxANVGdgw7cS4BNqF9aXhhmDqPrpEH6d": "regular",
    #                 "B1TDn3rUJMeCVDRsrz95mcB2x78oBER9toLpHRt2L7Bi": "regular",
    #                 "HgZHoiqtsQXKUNQ3xHrXz1cgrpPPPjG218114cLyqVmH": "new_wallet"
    #             },
    #             "wallet_info": {
    #                 "2kYrzWhnfzqUwxANVGdgw7cS4BNqF9aXhhmDqPrpEH6d": {
    #                     "sol": 1.270066612,
    #                     "sol_percentage": 65.12824518056686,
    #                     "token_percentage": 65.74337517538609,
    #                     "tokens": 8028045924739
    #                 },
    #                 "B1TDn3rUJMeCVDRsrz95mcB2x78oBER9toLpHRt2L7Bi": {
    #                     "sol": 0.422288302,
    #                     "sol_percentage": 21.654687879899377,
    #                     "token_percentage": 21.348412008548472,
    #                     "tokens": 2606894330686
    #                 },
    #                 "HgZHoiqtsQXKUNQ3xHrXz1cgrpPPPjG218114cLyqVmH": {
    #                     "sol": 0.257746165,
    #                     "sol_percentage": 13.217066939533757,
    #                     "token_percentage": 12.908212816065445,
    #                     "tokens": 1576245895761
    #                 }
    #             }
    #         },
    #         "317279894": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 1,
    #                     "regular": 5,
    #                     "sniper": 2
    #                 },
    #                 "copytrading_groups": {
    #                     "7yhcD8sXi3rbCacekTwPNpsF55K3nN6WBJxsZHqr26o3": "group_0",
    #                     "H9kHjTaJqVrrSuZGwJWgQnjyhVmGANpqsA6eoqbbZrTk": "group_0"
    #                 },
    #                 "is_likely_bundle": false,
    #                 "primary_category": "regular"
    #             },
    #             "holding_amount": 0,
    #             "holding_percentage": 0.0,
    #             "token_percentage": 7.211904335338,
    #             "total_sol": 13.97773329,
    #             "total_tokens": 72119043353380,
    #             "unique_wallets": 8,
    #             "wallet_categories": {
    #                 "12zdrBP47dvHNbgdvWo7B8k9baR8sbqd5FG4QtMPBhj9": "regular",
    #                 "4pvQQMZvjTh8Dtg65aNTSM4355mZ5butLR9TAccGaeqX": "sniper",
    #                 "7yhcD8sXi3rbCacekTwPNpsF55K3nN6WBJxsZHqr26o3": "regular",
    #                 "C7akxSngiGgTqFkDcXoeXWhd114UPkPBV77prZxJzjAm": "new_wallet",
    #                 "DfYVFTR5YsEyAfPiePDqPVYWmfpGpLN5azYL3cdDhhg8": "regular",
    #                 "DvK9F9mtUbGYjZ4CKgPfcyX5CWVq5i6gsj5aQWVZD4fC": "regular",
    #                 "H9kHjTaJqVrrSuZGwJWgQnjyhVmGANpqsA6eoqbbZrTk": "sniper",
    #                 "LYHT6nEUHgcGu9kCUkJXtqLD5NcpLXESYQ5QUrEvLoL": "regular"
    #             },
    #             "wallet_info": {
    #                 "12zdrBP47dvHNbgdvWo7B8k9baR8sbqd5FG4QtMPBhj9": {
    #                     "sol": 1.960396039,
    #                     "sol_percentage": 14.025135537551812,
    #                     "token_percentage": 15.659824933207044,
    #                     "tokens": 11293715932643
    #                 },
    #                 "4pvQQMZvjTh8Dtg65aNTSM4355mZ5butLR9TAccGaeqX": {
    #                     "sol": 4.814646714,
    #                     "sol_percentage": 34.44511791797109,
    #                     "token_percentage": 31.114455983626595,
    #                     "tokens": 22439448000000
    #                 },
    #                 "7yhcD8sXi3rbCacekTwPNpsF55K3nN6WBJxsZHqr26o3": {
    #                     "sol": 1.470297029,
    #                     "sol_percentage": 10.5188516513753,
    #                     "token_percentage": 12.302122760581776,
    #                     "tokens": 8872173247090
    #                 },
    #                 "C7akxSngiGgTqFkDcXoeXWhd114UPkPBV77prZxJzjAm": {
    #                     "sol": 2.940595039,
    #                     "sol_percentage": 21.03771032105593,
    #                     "token_percentage": 21.22607973497829,
    #                     "tokens": 15308045646292
    #                 },
    #                 "DfYVFTR5YsEyAfPiePDqPVYWmfpGpLN5azYL3cdDhhg8": {
    #                     "sol": 0.614881767,
    #                     "sol_percentage": 4.399009154366258,
    #                     "token_percentage": 4.242933892642363,
    #                     "tokens": 3059963333490
    #                 },
    #                 "DvK9F9mtUbGYjZ4CKgPfcyX5CWVq5i6gsj5aQWVZD4fC": {
    #                     "sol": 0.068614155,
    #                     "sol_percentage": 0.4908818445483445,
    #                     "token_percentage": 0.5334259152135165,
    #                     "tokens": 384701667051
    #                 },
    #                 "H9kHjTaJqVrrSuZGwJWgQnjyhVmGANpqsA6eoqbbZrTk": {
    #                     "sol": 0.735148514,
    #                     "sol_percentage": 5.259425822110532,
    #                     "token_percentage": 4.445291254218708,
    #                     "tokens": 3205901526814
    #                 },
    #                 "LYHT6nEUHgcGu9kCUkJXtqLD5NcpLXESYQ5QUrEvLoL": {
    #                     "sol": 1.373154033,
    #                     "sol_percentage": 9.823867751020739,
    #                     "token_percentage": 10.475865525531706,
    #                     "tokens": 7555094000000
    #                 }
    #             }
    #         },
    #         "317279895": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 0,
    #                     "regular": 2,
    #                     "sniper": 2
    #                 },
    #                 "copytrading_groups": {
    #                     "7VXxBDExMXWzPzTkFSGbFYFf7FUrjzrW91MUzJbfsVzk": "group_2",
    #                     "9FNz4MjPUmnJqTf6yEDbL1D4SsHVh7uA8zRHhR5K138r": "group_0",
    #                     "BaXY3QKq3cat2hWzwbpWNH79SaMS1Mdus16EC82b2pAB": "group_0",
    #                     "DhiwMct2of1j2DnYJTKSM33J2FemzmSwDKtZyGNBgnVD": "group_2"
    #                 },
    #                 "is_likely_bundle": false,
    #                 "primary_category": "sniper"
    #             },
    #             "holding_amount": 0,
    #             "holding_percentage": 0.0,
    #             "token_percentage": 5.114964444412999,
    #             "total_sol": 12.742770314,
    #             "total_tokens": 51149644444130,
    #             "unique_wallets": 4,
    #             "wallet_categories": {
    #                 "7VXxBDExMXWzPzTkFSGbFYFf7FUrjzrW91MUzJbfsVzk": "regular",
    #                 "9FNz4MjPUmnJqTf6yEDbL1D4SsHVh7uA8zRHhR5K138r": "sniper",
    #                 "BaXY3QKq3cat2hWzwbpWNH79SaMS1Mdus16EC82b2pAB": "sniper",
    #                 "DhiwMct2of1j2DnYJTKSM33J2FemzmSwDKtZyGNBgnVD": "regular"
    #             },
    #             "wallet_info": {
    #                 "7VXxBDExMXWzPzTkFSGbFYFf7FUrjzrW91MUzJbfsVzk": {
    #                     "sol": 2.450593069,
    #                     "sol_percentage": 19.23124256824771,
    #                     "token_percentage": 19.060353147338137,
    #                     "tokens": 9749302864659
    #                 },
    #                 "9FNz4MjPUmnJqTf6yEDbL1D4SsHVh7uA8zRHhR5K138r": {
    #                     "sol": 3.920792088,
    #                     "sol_percentage": 30.76875743175229,
    #                     "token_percentage": 31.719938743511563,
    #                     "tokens": 16224635885202
    #                 },
    #                 "BaXY3QKq3cat2hWzwbpWNH79SaMS1Mdus16EC82b2pAB": {
    #                     "sol": 3.920792088,
    #                     "sol_percentage": 30.76875743175229,
    #                     "token_percentage": 29.076672359738758,
    #                     "tokens": 14872614528191
    #                 },
    #                 "DhiwMct2of1j2DnYJTKSM33J2FemzmSwDKtZyGNBgnVD": {
    #                     "sol": 2.450593069,
    #                     "sol_percentage": 19.23124256824771,
    #                     "token_percentage": 20.143035749411542,
    #                     "tokens": 10303091166078
    #                 }
    #             }
    #         },
    #         "317279896": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 0,
    #                     "regular": 1,
    #                     "sniper": 6
    #                 },
    #                 "copytrading_groups": {
    #                     "48kx1v5iNdpwmWKAcfwNKL8brRCZqATJrmrCAw8wnN29": "group_2",
    #                     "4hSXPtxZgXFpo6Vxq9yqxNjcBoqWN3VoaPJWonUtupzD": "group_2",
    #                     "9FNz4MjPUmnJqTf6yEDbL1D4SsHVh7uA8zRHhR5K138r": "group_0",
    #                     "BaXY3QKq3cat2hWzwbpWNH79SaMS1Mdus16EC82b2pAB": "group_0",
    #                     "EQgLrdnwsSLBqHsUgxAvAiaEuutEeA8Vb5FNMRY48Bn4": "group_2"
    #                 },
    #                 "is_likely_bundle": false,
    #                 "primary_category": "sniper"
    #             },
    #             "holding_amount": 0,
    #             "holding_percentage": 0.0,
    #             "token_percentage": 5.5615949963963,
    #             "total_sol": 16.661727937000002,
    #             "total_tokens": 55615949963963,
    #             "unique_wallets": 7,
    #             "wallet_categories": {
    #                 "48kx1v5iNdpwmWKAcfwNKL8brRCZqATJrmrCAw8wnN29": "sniper",
    #                 "4hSXPtxZgXFpo6Vxq9yqxNjcBoqWN3VoaPJWonUtupzD": "sniper",
    #                 "96YiDsQgwJi3VFVmNvmAqxFxB5wacVZh2pYcXk2dUB8J": "sniper",
    #                 "9FNz4MjPUmnJqTf6yEDbL1D4SsHVh7uA8zRHhR5K138r": "sniper",
    #                 "9oRjpK9gixZaoAyVGZovaa5CS9y4G5qKBbN37sF3wKPU": "sniper",
    #                 "BaXY3QKq3cat2hWzwbpWNH79SaMS1Mdus16EC82b2pAB": "sniper",
    #                 "EQgLrdnwsSLBqHsUgxAvAiaEuutEeA8Vb5FNMRY48Bn4": "regular"
    #             },
    #             "wallet_info": {
    #                 "48kx1v5iNdpwmWKAcfwNKL8brRCZqATJrmrCAw8wnN29": {
    #                     "sol": 2.450495049,
    #                     "sol_percentage": 14.70732842515264,
    #                     "token_percentage": 15.62153475333341,
    #                     "tokens": 8688064952017
    #                 },
    #                 "4hSXPtxZgXFpo6Vxq9yqxNjcBoqWN3VoaPJWonUtupzD": {
    #                     "sol": 2.450495049,
    #                     "sol_percentage": 14.70732842515264,
    #                     "token_percentage": 14.847948533211705,
    #                     "tokens": 8257827626906
    #                 },
    #                 "96YiDsQgwJi3VFVmNvmAqxFxB5wacVZh2pYcXk2dUB8J": {
    #                     "sol": 2.0,
    #                     "sol_percentage": 12.003556939365717,
    #                     "token_percentage": 13.76791853464257,
    #                     "tokens": 7657158683306
    #                 },
    #                 "9FNz4MjPUmnJqTf6yEDbL1D4SsHVh7uA8zRHhR5K138r": {
    #                     "sol": 3.920792088,
    #                     "sol_percentage": 23.5317255378613,
    #                     "token_percentage": 22.28561941069436,
    #                     "tokens": 12394358940611
    #                 },
    #                 "9oRjpK9gixZaoAyVGZovaa5CS9y4G5qKBbN37sF3wKPU": {
    #                     "sol": 0.706158614,
    #                     "sol_percentage": 4.238207565686288,
    #                     "token_percentage": 4.762951100240893,
    #                     "tokens": 2648960500718
    #                 },
    #                 "BaXY3QKq3cat2hWzwbpWNH79SaMS1Mdus16EC82b2pAB": {
    #                     "sol": 3.920792088,
    #                     "sol_percentage": 23.5317255378613,
    #                     "token_percentage": 20.649501561653555,
    #                     "tokens": 11484416456337
    #                 },
    #                 "EQgLrdnwsSLBqHsUgxAvAiaEuutEeA8Vb5FNMRY48Bn4": {
    #                     "sol": 1.212995049,
    #                     "sol_percentage": 7.280127568920104,
    #                     "token_percentage": 8.064526106223509,
    #                     "tokens": 4485162804068
    #                 }
    #             }
    #         },
    #         "317279897": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 1,
    #                     "regular": 0,
    #                     "sniper": 4
    #                 },
    #                 "copytrading_groups": {},
    #                 "is_likely_bundle": false,
    #                 "primary_category": "sniper"
    #             },
    #             "holding_amount": 0,
    #             "holding_percentage": 0.0,
    #             "token_percentage": 3.630206958927,
    #             "total_sol": 10.483425279999999,
    #             "total_tokens": 36302069589270,
    #             "unique_wallets": 5,
    #             "wallet_categories": {
    #                 "3agVGq6VceAnHiFhxdsDsMqh622KHeRJ2a9RUMuWhBh8": "new_wallet",
    #                 "6ESwF2ouiH7Vz2uRkzBXftY6Ko9jdqvebMvTFUG2Bthy": "sniper",
    #                 "ACkvMCryf6XyAyZjUZomUHGGuL2eCTJLfCXgyJoCEVPR": "sniper",
    #                 "EzbeF2bADKo6GutJyWmgodyGJFeBPhcrXSdZUXPX5WGc": "sniper",
    #                 "FarPNXCkx3NQaE2JUsZxZUeru1CmfSXPE1c48otHWUht": "sniper"
    #             },
    #             "wallet_info": {
    #                 "3agVGq6VceAnHiFhxdsDsMqh622KHeRJ2a9RUMuWhBh8": {
    #                     "sol": 0.087519098,
    #                     "sol_percentage": 0.8348330403705612,
    #                     "token_percentage": 0.9282834311644999,
    #                     "tokens": 336986097167
    #                 },
    #                 "6ESwF2ouiH7Vz2uRkzBXftY6Ko9jdqvebMvTFUG2Bthy": {
    #                     "sol": 1.960396039,
    #                     "sol_percentage": 18.69995718613068,
    #                     "token_percentage": 20.118333142763014,
    #                     "tokens": 7303371297687
    #                 },
    #                 "ACkvMCryf6XyAyZjUZomUHGGuL2eCTJLfCXgyJoCEVPR": {
    #                     "sol": 3.932861257,
    #                     "sol_percentage": 37.51504066617433,
    #                     "token_percentage": 35.00817098809258,
    #                     "tokens": 12708690594028
    #                 },
    #                 "EzbeF2bADKo6GutJyWmgodyGJFeBPhcrXSdZUXPX5WGc": {
    #                     "sol": 3.920792079,
    #                     "sol_percentage": 37.39991438180022,
    #                     "token_percentage": 37.818541792289246,
    #                     "tokens": 13728913359084
    #                 },
    #                 "FarPNXCkx3NQaE2JUsZxZUeru1CmfSXPE1c48otHWUht": {
    #                     "sol": 0.581856807,
    #                     "sol_percentage": 5.550254725524214,
    #                     "token_percentage": 6.126670645690657,
    #                     "tokens": 2224108241304
    #                 }
    #             }
    #         },
    #         "317279898": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 2,
    #                     "regular": 1,
    #                     "sniper": 5
    #                 },
    #                 "copytrading_groups": {
    #                     "4wCX2fnJknjAJBGqaYRiEVVycFU7Dh4fVZRng9nrDVFt": "group_0",
    #                     "ACkvMCryf6XyAyZjUZomUHGGuL2eCTJLfCXgyJoCEVPR": "group_0"
    #                 },
    #                 "is_likely_bundle": false,
    #                 "primary_category": "sniper"
    #             },
    #             "holding_amount": 0,
    #             "holding_percentage": 0.0,
    #             "token_percentage": 6.0524918703555,
    #             "total_sol": 20.733989098,
    #             "total_tokens": 60524918703555,
    #             "unique_wallets": 8,
    #             "wallet_categories": {
    #                 "3tc4BVAdzjr1JpeZu6NAjLHyp4kK3iic7TexMBYGJ4Xk": "sniper",
    #                 "4wCX2fnJknjAJBGqaYRiEVVycFU7Dh4fVZRng9nrDVFt": "regular",
    #                 "5nHZ6YVbE3MXt8iAoaVFYoNZ8hfC273tL85UqxU6fALE": "new_wallet",
    #                 "8XMuZZPkCpxK7wBGpqTeXtGDVzGiHZvgeKQUFsjRNGwC": "new_wallet",
    #                 "ACkvMCryf6XyAyZjUZomUHGGuL2eCTJLfCXgyJoCEVPR": "sniper",
    #                 "EBK8TFxqhWcsA8hFbuGrFGrJzKrCXddUaE32xazvR2D8": "sniper",
    #                 "suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK": "sniper",
    #                 "w5E2AUgS76NcVg39AmTViyCFHrVYirg7usx6DkNg1vR": "sniper"
    #             },
    #             "wallet_info": {
    #                 "3tc4BVAdzjr1JpeZu6NAjLHyp4kK3iic7TexMBYGJ4Xk": {
    #                     "sol": 3.0,
    #                     "sol_percentage": 14.468995743271515,
    #                     "token_percentage": 14.957291063142343,
    #                     "tokens": 9052888256221
    #                 },
    #                 "4wCX2fnJknjAJBGqaYRiEVVycFU7Dh4fVZRng9nrDVFt": {
    #                     "sol": 0.198,
    #                     "sol_percentage": 0.9549537190559201,
    #                     "token_percentage": 0.94042807593324,
    #                     "tokens": 569193328424
    #                 },
    #                 "5nHZ6YVbE3MXt8iAoaVFYoNZ8hfC273tL85UqxU6fALE": {
    #                     "sol": 5.881188136,
    #                     "sol_percentage": 28.364962035054315,
    #                     "token_percentage": 30.01791142786593,
    #                     "tokens": 18168316488221
    #                 },
    #                 "8XMuZZPkCpxK7wBGpqTeXtGDVzGiHZvgeKQUFsjRNGwC": {
    #                     "sol": 2.178217603,
    #                     "sol_percentage": 10.50554040857536,
    #                     "token_percentage": 9.048809910514287,
    #                     "tokens": 5476784841978
    #                 },
    #                 "ACkvMCryf6XyAyZjUZomUHGGuL2eCTJLfCXgyJoCEVPR": {
    #                     "sol": 3.932861257,
    #                     "sol_percentage": 18.96818426213682,
    #                     "token_percentage": 17.261342450573768,
    #                     "tokens": 10447413485352
    #                 },
    #                 "EBK8TFxqhWcsA8hFbuGrFGrJzKrCXddUaE32xazvR2D8": {
    #                     "sol": 2.20566611,
    #                     "sol_percentage": 10.637924518889415,
    #                     "token_percentage": 10.719374711619276,
    #                     "tokens": 6487892829737
    #                 },
    #                 "suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK": {
    #                     "sol": 2.940595039,
    #                     "sol_percentage": 14.18248570065878,
    #                     "token_percentage": 15.24026716921176,
    #                     "tokens": 9224159314370
    #                 },
    #                 "w5E2AUgS76NcVg39AmTViyCFHrVYirg7usx6DkNg1vR": {
    #                     "sol": 0.397460953,
    #                     "sol_percentage": 1.91695361235788,
    #                     "token_percentage": 1.8145751911394008,
    #                     "tokens": 1098270159252
    #                 }
    #             }
    #         },
    #         "317279899": {
    #             "bundle_analysis": {
    #                 "category_breakdown": {
    #                     "new_wallet": 0,
    #                     "regular": 2,
    #                     "sniper": 3
    #                 },
    #                 "copytrading_groups": {
    #                     "7yhcD8sXi3rbCacekTwPNpsF55K3nN6WBJxsZHqr26o3": "group_0",
    #                     "LYHT6nEUHgcGu9kCUkJXtqLD5NcpLXESYQ5QUrEvLoL": "group_0"
    #                 },
    #                 "is_likely_bundle": false,
    #                 "primary_category": "sniper"
    #             },
    #             "holding_amount": 0,
    #             "holding_percentage": 0.0,
    #             "token_percentage": 4.131459230166399,
    #             "total_sol": 14.930496336,
    #             "total_tokens": 41314592301664,
    #             "unique_wallets": 5,
    #             "wallet_categories": {
    #                 "35yvcawwYP2o7FHUYp4jcBCqyaXkweCtvyYaqQba9yQ3": "sniper",
    #                 "5sSXftrP6ZE6U3fwdubFmAYFVVA5otBQnvR2eYv3T8SP": "sniper",
    #                 "7yhcD8sXi3rbCacekTwPNpsF55K3nN6WBJxsZHqr26o3": "regular",
    #                 "LYHT6nEUHgcGu9kCUkJXtqLD5NcpLXESYQ5QUrEvLoL": "regular",
    #                 "niggerd597QYedtvjQDVHZTCCGyJrwHNm2i49dkm5zS": "sniper"
    #             },
    #             "wallet_info": {
    #                 "35yvcawwYP2o7FHUYp4jcBCqyaXkweCtvyYaqQba9yQ3": {
    #                     "sol": 0.497393988,
    #                     "sol_percentage": 3.331396202822122,
    #                     "token_percentage": 3.6463217618858725,
    #                     "tokens": 1506462969930
    #                 },
    #                 "5sSXftrP6ZE6U3fwdubFmAYFVVA5otBQnvR2eYv3T8SP": {
    #                     "sol": 1.980198019,
    #                     "sol_percentage": 13.262774220207277,
    #                     "token_percentage": 14.175054576702495,
    #                     "tokens": 5856366006903
    #                 },
    #                 "7yhcD8sXi3rbCacekTwPNpsF55K3nN6WBJxsZHqr26o3": {
    #                     "sol": 1.470297029,
    #                     "sol_percentage": 9.8476098577839,
    #                     "token_percentage": 10.690998528529839,
    #                     "tokens": 4416942455039
    #                 },
    #                 "LYHT6nEUHgcGu9kCUkJXtqLD5NcpLXESYQ5QUrEvLoL": {
    #                     "sol": 1.300000041,
    #                     "sol_percentage": 8.707011553698159,
    #                     "token_percentage": 9.20462187362995,
    #                     "tokens": 3802852000000
    #                 },
    #                 "niggerd597QYedtvjQDVHZTCCGyJrwHNm2i49dkm5zS": {
    #                     "sol": 9.682607259,
    #                     "sol_percentage": 64.85120816548854,
    #                     "token_percentage": 62.28300325925184,
    #                     "tokens": 25731968869792
    #                 }
    #             }
    #         }
    #     },
    #     "creator_analysis": {
    #         "address": "DUKVDysvzUK5tdfe1Y3kShdEtgHy7j92caUHSHHrECiW",
    #         "current_holdings": 0,
    #         "history": {
    #             "average_market_cap": 39.148765039640004,
    #             "high_risk": true,
    #             "previous_coins": [
    #                 {
    #                     "created_at": 1738213865004,
    #                     "is_rug": false,
    #                     "market_cap": 589.7,
    #                     "mint": "CpiREbXwSBqHtrQWJQS2QrwVHRDVghgxdnzkuux9sZup",
    #                     "symbol": ".FUN"
    #                 },
    #                 {
    #                     "created_at": 1738213563895,
    #                     "is_rug": true,
    #                     "market_cap": 28.043232045,
    #                     "mint": "4wWhC5JNNoRz8YVwQoR3bDKUjbV3PHdvfVxSfnzssw9m",
    #                     "symbol": "TREBUCHET"
    #                 },
    #                 {
    #                     "created_at": 1738213264975,
    #                     "is_rug": true,
    #                     "market_cap": 28.052622524,
    #                     "mint": "CwnvR2zKA8zfoRqvKvBW1wsQJbdtC3wap5tH2dg82KV2",
    #                     "symbol": "8E"
    #                 },
    #                 {
    #                     "created_at": 1738211276908,
    #                     "is_rug": true,
    #                     "market_cap": 28.177461462,
    #                     "mint": "JCfj9PmFpkz5i6ZfxKjdrLEAT9h3goRUvLu3V848FXAF",
    #                     "symbol": "DEATH"
    #                 },
    #                 {
    #                     "created_at": 1738210605879,
    #                     "is_rug": true,
    #                     "market_cap": 27.95899348,
    #                     "mint": "BbVxut3PdwHpiLkmtzRUbaDwYCAeuMSxuTpegvhDxrfD",
    #                     "symbol": "DF"
    #                 },
    #                 {
    #                     "created_at": 1738210267816,
    #                     "is_rug": true,
    #                     "market_cap": 28.05747707,
    #                     "mint": "7T6XhEbmM82pFHU164xwpDkaipN1vu5T39JmB6MBDDVF",
    #                     "symbol": "IPO"
    #                 },
    #                 {
    #                     "created_at": 1738210221378,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993479,
    #                     "mint": "8sptJsiS4i92ZjWPpkKicWJP3W5hcjPy2GEinuHpj3S9",
    #                     "symbol": "IPO"
    #                 },
    #                 {
    #                     "created_at": 1738209692348,
    #                     "is_rug": true,
    #                     "market_cap": 28.567190928,
    #                     "mint": "CLk4aZFMF27fzhqrDZxAv8HNnYrt1JTbPj17x6L9APkv",
    #                     "symbol": "ALONPUMP"
    #                 },
    #                 {
    #                     "created_at": 1738209669205,
    #                     "is_rug": true,
    #                     "market_cap": 27.977642119,
    #                     "mint": "4FHcmiLgtCP7ETCRT2mBWKh6EnVHjfWpwvSLaatVECE5",
    #                     "symbol": "UWATERLOO"
    #                 },
    #                 {
    #                     "created_at": 1738209544870,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993486,
    #                     "mint": "9n4kwoZbN78YCpjDAvLDZpic8jX1SoAdQSuLKrusx5pq",
    #                     "symbol": "YCJMT"
    #                 },
    #                 {
    #                     "created_at": 1738209368836,
    #                     "is_rug": true,
    #                     "market_cap": 27.97759739,
    #                     "mint": "A1qEf71r8W1EKS2KdJ8EHviYXFr72obEnVVih4WvGBvP",
    #                     "symbol": "GELSA"
    #                 },
    #                 {
    #                     "created_at": 1738209365266,
    #                     "is_rug": true,
    #                     "market_cap": 27.977642099,
    #                     "mint": "8wXYNAUNvgoKQaLR8oqmmDB6AeEzf3ymRB1kY6dnXiMa",
    #                     "symbol": "JACK"
    #                 },
    #                 {
    #                     "created_at": 1738209328132,
    #                     "is_rug": true,
    #                     "market_cap": 27.977642096,
    #                     "mint": "D4aDvE4exR2oZmYy1e9SCzKXW6ci1LTepYzbKq1VCK5Z",
    #                     "symbol": "RAJ"
    #                 },
    #                 {
    #                     "created_at": 1738209054696,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993483,
    #                     "mint": "J1Cs72bGnfEoNJVzDTqBxwzJKxDDzpLQeCL3U2mvHmLp",
    #                     "symbol": "P2A"
    #                 },
    #                 {
    #                     "created_at": 1738208944833,
    #                     "is_rug": true,
    #                     "market_cap": 25.82,
    #                     "mint": "ViWh5bvkvtG9oH3XYRjemQAerQgoQR85YhAUQd6hkQd",
    #                     "symbol": "IPO"
    #                 },
    #                 {
    #                     "created_at": 1738208609254,
    #                     "is_rug": true,
    #                     "market_cap": 27.977642099,
    #                     "mint": "9hgP7DmaB6nTt3qRrPQzyU1Zkj8Hcmmubr2c12gtCW4N",
    #                     "symbol": "ABOVE"
    #                 },
    #                 {
    #                     "created_at": 1738207415055,
    #                     "is_rug": false,
    #                     "market_cap": 34.673243594,
    #                     "mint": "6o64JjUza7Dpow295eMGJiD4pjmn4HgAH6NQD3fhhias",
    #                     "symbol": "VINE"
    #                 },
    #                 {
    #                     "created_at": 1738207034761,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993477,
    #                     "mint": "CTptkQGtp8teAC8UiTsrRGVjZDEavH5rGQqN5rVpDx5P",
    #                     "symbol": "STRAWBERRY"
    #                 },
    #                 {
    #                     "created_at": 1738206973873,
    #                     "is_rug": true,
    #                     "market_cap": 28.095909996,
    #                     "mint": "6oj2UdnbJ2tPo4DSHWxPpTxidbVJeFqgqBiPK7gu1YqQ",
    #                     "symbol": "STRAWBERRY"
    #                 },
    #                 {
    #                     "created_at": 1738206892293,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993479,
    #                     "mint": "CRqUvfMnj1XRNBQMdMZcWXmQEvEJFxaH8zEQqyAfXtkp",
    #                     "symbol": "STRAWBERRY"
    #                 },
    #                 {
    #                     "created_at": 1738206871251,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993477,
    #                     "mint": "C9idFKDmrHURSCD56oiMGUhCwJzPx6bgrnDKpTNUJ41C",
    #                     "symbol": "B2B"
    #                 },
    #                 {
    #                     "created_at": 1738206815440,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993477,
    #                     "mint": "BH7WSHi613sGwo42WE56vcYYYpBBHjyxDrXJkd44LcMP",
    #                     "symbol": "STRAWBERRY"
    #                 },
    #                 {
    #                     "created_at": 1738206806244,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993478,
    #                     "mint": "7JiiUZmaafwKxHG1CsVQHLbqvgZ2DmjjcEKp7DzEh6zq",
    #                     "symbol": "STRAWBERRY"
    #                 },
    #                 {
    #                     "created_at": 1738206775580,
    #                     "is_rug": true,
    #                     "market_cap": 29.104095126,
    #                     "mint": "GgjYdVTsPe3qmn8Hh32SFeoMNWTL7him5P8L3TCJWazc",
    #                     "symbol": "A"
    #                 },
    #                 {
    #                     "created_at": 1738206757399,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993478,
    #                     "mint": "DU1ent2qwyvhGDCfxrwGkDTiQsjdBfehbxShwiAPW6xE",
    #                     "symbol": "STRAWBERRY"
    #                 },
    #                 {
    #                     "created_at": 1738206622316,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993478,
    #                     "mint": "4GtuwrbgPTxJuLQjPcYaFsGxfSmdjUe6AGbCeN4T3pNv",
    #                     "symbol": "B2B"
    #                 },
    #                 {
    #                     "created_at": 1738206568216,
    #                     "is_rug": true,
    #                     "market_cap": 27.959179873,
    #                     "mint": "GqW6BKxc9FAKodauoya8YXeuTGmK8KkiHBjDpBqeDTHV",
    #                     "symbol": "A"
    #                 },
    #                 {
    #                     "created_at": 1738206561040,
    #                     "is_rug": true,
    #                     "market_cap": 27.95917987,
    #                     "mint": "FpLmoMKDCYrPD9oLnbCYHYT4Gi8ccMoUqKxpRWsSG9TL",
    #                     "symbol": "B2B"
    #                 },
    #                 {
    #                     "created_at": 1738206463660,
    #                     "is_rug": true,
    #                     "market_cap": 27.977556339,
    #                     "mint": "GC36DrQN2yt43Y4eABosHqRwJ8DvKgN1aZcGneVo5Yec",
    #                     "symbol": "B2B"
    #                 },
    #                 {
    #                     "created_at": 1738206415265,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993478,
    #                     "mint": "6UZJh7Qx9wabuNJdo8KWYG6ghVQQmjTfagEvTsdP41na",
    #                     "symbol": "B2B"
    #                 },
    #                 {
    #                     "created_at": 1738206378325,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993479,
    #                     "mint": "HSxq4XNiSnF6SDQyo5g9PfZDmj7GRzzbR7HL7C8TncD9",
    #                     "symbol": "B2B"
    #                 },
    #                 {
    #                     "created_at": 1738206326166,
    #                     "is_rug": true,
    #                     "market_cap": 27.977388586,
    #                     "mint": "6niGnKEPfkaGTbR7XewzrkRV3rTSXJXN9zrtT7zVnep5",
    #                     "symbol": "SOL"
    #                 },
    #                 {
    #                     "created_at": 1738206254830,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993477,
    #                     "mint": "1NrTuCc8rcEAravJ5Q2P763RM8zww9w5PNnwAPKW5Dw",
    #                     "symbol": "B2B"
    #                 },
    #                 {
    #                     "created_at": 1738206253726,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993477,
    #                     "mint": "FqSMLbPoETUo6bJ4PstnSHkrMS8qZSBbYmzmYV74Hj8H",
    #                     "symbol": "B2B"
    #                 },
    #                 {
    #                     "created_at": 1738206153683,
    #                     "is_rug": true,
    #                     "market_cap": 27.95899348,
    #                     "mint": "A7DVtJt3HKqzbzJ25exbHcuBqvrJfYnCegobVLZjE7XP",
    #                     "symbol": "B2B"
    #                 },
    #                 {
    #                     "created_at": 1738206098123,
    #                     "is_rug": true,
    #                     "market_cap": 17.360000000000003,
    #                     "mint": "AWDdJj6HFq1oXFwDgG4fu9wxUZs2FMQRgAfoQ8owYxce",
    #                     "symbol": "B2B"
    #                 },
    #                 {
    #                     "created_at": 1738206051711,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993485,
    #                     "mint": "4kk9QyY1di7wJRvxciz4GE8e1sar19NbqLnQTcEUjLFP",
    #                     "symbol": "STRAWBERRY"
    #                 },
    #                 {
    #                     "created_at": 1738206005563,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993482,
    #                     "mint": "8ysSXqxY4HM9Uh1WnuZgBHj5DnnkeH1Ve5bfZgBqQ6Bo",
    #                     "symbol": "STRAWBERRY"
    #                 },
    #                 {
    #                     "created_at": 1738205986439,
    #                     "is_rug": true,
    #                     "market_cap": 27.975255784,
    #                     "mint": "AKxwXZSeDtXKrGTJRZ1sv2buee1Un6bEM6g6uZMtwGay",
    #                     "symbol": "STRAWBERRY"
    #                 },
    #                 {
    #                     "created_at": 1738205773124,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993482,
    #                     "mint": "EFNBtWbzSSARLAJXcjzHzurr7qgPr1cteo88zoSVMSai",
    #                     "symbol": "DEEPSEEK"
    #                 },
    #                 {
    #                     "created_at": 1738205773108,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993478,
    #                     "mint": "85HWGQmj4PELpPKF2LUeT5b1rch7o5NmY5H7sJQDT7pW",
    #                     "symbol": "DEEPSEEK"
    #                 },
    #                 {
    #                     "created_at": 1738205720603,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993479,
    #                     "mint": "4tozWZK9xCW7o45bXbpRRgk8wa6DaoGMMKpcLzWx4Z25",
    #                     "symbol": "\u2726"
    #                 },
    #                 {
    #                     "created_at": 1738205684844,
    #                     "is_rug": true,
    #                     "market_cap": 28.09184534,
    #                     "mint": "H1awsszC9vLEh1YCv2HkLKWo7HWM9uhwBpmJ569sZaze",
    #                     "symbol": "EW"
    #                 },
    #                 {
    #                     "created_at": 1738205659361,
    #                     "is_rug": true,
    #                     "market_cap": 27.958993703,
    #                     "mint": "BJMdRy1gGgRYmkeTqzkgX6vvvvQsGGDh6mFmU18pRFiK",
    #                     "symbol": "SIFC"
    #                 },
    #                 {
    #                     "created_at": 1738205521973,
    #                     "is_rug": true,
    #                     "market_cap": 27.380000000000003,
    #                     "mint": "GUce24t2jG9V14QzXPCyJv9ZcxDxH2RSDndrk7Ws2PWP",
    #                     "symbol": "5342"
    #                 },
    #                 {
    #                     "created_at": 1738205475968,
    #                     "is_rug": true,
    #                     "market_cap": 27.95917987,
    #                     "mint": "BRpQ4Z2TxdCYWanarPEzqNKHZfnGPhnATbbnWbnQe2d4",
    #                     "symbol": "A"
    #                 },
    #                 {
    #                     "created_at": 1738205473062,
    #                     "is_rug": true,
    #                     "market_cap": 27.959179872,
    #                     "mint": "5PeKeH7B5rCpGbJZ7ENgcqkZoaY81DUtViaxUj6YgBMm",
    #                     "symbol": "A"
    #                 },
    #                 {
    #                     "created_at": 1738205439095,
    #                     "is_rug": true,
    #                     "market_cap": 27.977211192,
    #                     "mint": "LNyYJpBUC8dd2w5JUj5fTYwwG7w8Ytoude4JHwwWydx",
    #                     "symbol": "JIGGLECOIN"
    #                 },
    #                 {
    #                     "created_at": 1738205436146,
    #                     "is_rug": true,
    #                     "market_cap": 29.50756013,
    #                     "mint": "J5Xea5K4PVY7SehANik9AYUbz4V8gjo8qhi7HQ7sPMQJ",
    #                     "symbol": "JIGGLECOIN"
    #                 },
    #                 {
    #                     "created_at": 1738205420080,
    #                     "is_rug": true,
    #                     "market_cap": 28.077459806,
    #                     "mint": "EFAnPooDkdThcRDDBiRSUziPtvKh6VmiExCA5CJo2mug",
    #                     "symbol": "TOLYCOIN"
    #                 }
    #             ],
    #             "recent_rugs": 3,
    #             "rug_count": 3,
    #             "rug_percentage": 6.0,
    #             "total_coins_created": 50
    #         },
    #         "holding_percentage": 0.0,
    #         "risk_level": "HIGH",
    #         "warning_flags": [
    #             "Previous rugs detected",
    #             "Recent rug activity",
    #             "Suspicious token spam",
    #             null
    #         ]
    #     },
    #     "distributed_amount": 0,
    #     "distributed_percentage": 0,
    #     "distributed_wallets": 0,
    #     "ticker": ".FUN",
    #     "total_bundles": 14,
    #     "total_holding_amount": 32891446907365,
    #     "total_holding_percentage": 3.2891446907365,
    #     "total_percentage_bundled": 97.4510968383846,
    #     "total_sol_spent": 151.85454762299997,
    #     "total_tokens_bundled": 974510968383846
    # }
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
    print(f"Message received: {message.content}")
    # Check environment and guild ID
    environment = os.getenv("ENVIRONMENT", "production")
    development_guild_id = int(os.getenv("DEVELOPMENT_GUILD_ID", "0"))
    if environment == "development" and message.guild.id != development_guild_id:
        print(f"Message from non-development guild: {message.guild.id}")
        return

    # Only process messages from Rick bot
    if message.author.id != RICK_BOT_ID:
        print(f"Message from non-Rick bot: {message.author.id}")
        return

    # Try to parse contract info
    result = parse_contract_info(message)
    if not result:
        print("Failed to parse contract info")
        return

    contract_address = result
    # Get trench bundle metadata
    trench_bundle_metadata = get_trench_bundle_metadata(contract_address)
    if not trench_bundle_metadata:
        print("Failed to get trench bundle metadata")
        return

    # Create embed
    embed = discord.Embed(
        color=discord.Color.blue(),
    )
    print(f"Created embed for {trench_bundle_metadata['ticker']}")

    # Currently Held Bundles
    currently_held_emoji = (
        "✅"
        if trench_bundle_metadata["total_holding_percentage"] < 3
        else "⚠️" if trench_bundle_metadata["total_holding_percentage"] < 10 else "🚨"
    )
    currently_held_bundles = f"{currently_held_emoji} Currently Held Bundles: **{trench_bundle_metadata['total_holding_percentage']:.2f}%**"
    embed.add_field(name="Current Bundles", value=currently_held_bundles, inline=False)

    # Initial Bundle Stats
    initial_bundle_stats = f"📦 {trench_bundle_metadata['total_bundles']} bundles, **{trench_bundle_metadata['total_percentage_bundled']:.1f}%** with **{trench_bundle_metadata['total_sol_spent']:.2f}** SOL\n"
    embed.add_field(name="Initial Bundles", value=initial_bundle_stats, inline=False)

    # Creator Stats (Right Column)
    creator = trench_bundle_metadata["creator_analysis"]

    # Warnings (if any, shown at bottom)
    risk_level_emoji = {
        "LOW": "✅",
        "MEDIUM": "⚠️",
        "HIGH": "🚨",
    }
    creator_info = (
        f"{risk_level_emoji[creator['risk_level']]} Risk Level: {creator['risk_level']}"
    )
    if creator["warning_flags"]:
        warnings = " • ".join(flag for flag in creator["warning_flags"] if flag)
        if warnings:
            creator_info = f"\n⚠️ Warnings: {warnings}"
    embed.add_field(name="Creator Info", value=creator_info, inline=False)

    try:
        # Send reply with embed
        print(f"Sending reply with embed for {trench_bundle_metadata['ticker']}")
        bot_message = await message.reply(
            content=f"[**Trench.bot Analysis: {trench_bundle_metadata['ticker']}**](https://trench.bot/bundles/{contract_address})",
            embed=embed,
        )

        # Add trash reaction for deletion
        try:
            print(f"Adding trash reaction for {trench_bundle_metadata['ticker']}")
            await bot_message.add_reaction(TRASH_EMOJI)
            asyncio.create_task(remove_reaction_after_delay(bot_message))
        except discord.Forbidden as e:
            print(f"Bot lacks permission to add reactions: {e}")
        except discord.HTTPException as e:
            print(f"Failed to add reaction: {e}")
        except Exception as e:
            print(f"Unexpected error adding reaction: {e}")

    except Exception as e:
        print(f"Failed to send message or add reaction: {e}")


def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN not found in environment variables")
    bot.run(token)


if __name__ == "__main__":
    main()
