#!/usr/bin/env python3

import datetime
import discord
from discord.ext import commands
import json
import logging

logfile = 'bot.log'
print("Writing to log at: " + logfile)
logging.basicConfig(filename=logfile, level=logging.WARNING, format='%(asctime)s %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# log version number.
version = "1.0.0"
logger.info("Running " + version)

# Load config file.
with open('config.json', 'r') as f:
    config = json.load(f)
discord_token = config['DISCORD_TOKEN']
prefix = config['PREFIX']

intents = discord.Intents.none()
intents.guilds = True
intents.messages = True
#intents.reactions = True

launch_time = datetime.datetime.utcnow()
bot = commands.Bot(command_prefix=prefix, case_insensitive=True, intents=intents)


@bot.event
async def on_ready():
    logger.info("We have logged in as {0}.".format(bot.user))
    if not bot.guilds:
        logger.error("The bot is not in any guilds. Shutting down.")
        await bot.close()
        return
    for guild in bot.guilds:
        logger.info('Welcome to {0}.'.format(guild))
    bot.load_extension('dev_cog')
    bot.load_extension('trade_cog')
    await bot.change_presence(activity=discord.Game(name=version))


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("Please use this command in a server.")
    else:
        await ctx.send(error, delete_after=10)
        if not isinstance(error, commands.CommandNotFound):
            logger.warning("Error for command: " + ctx.message.content)
            logger.warning(error)


@bot.check
async def globally_block_dms(ctx):
    if ctx.guild is None:
        raise commands.NoPrivateMessage("No dm allowed!")
    else:
        return True


bot.run(discord_token)
logger.info("Shutting down.")
