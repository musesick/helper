import discord
from discord.ext import commands
import chatdb_utils
import chatdb_tables
from chatdb_utils import create_connection
from datetime import datetime
from bot_utils import compile_recent_chats  # import this function from bot_utils.py

intents = discord.Intents.all()
intents.members = True
intents.presences = True

# establish connection
conn = chatdb_utils.create_connection()

# create table
chatdb_tables.create_user_table(conn)  # Creating user table on bot start
chatdb_tables.create_chat_channels_table(conn)  # Creating chat_channels table on bot start

class MyClient(commands.Bot):  # Changed from discord.Client to commands.Bot

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conn = None

    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))
        self.conn = create_connection()
        # Call create_chat_channels_table for each guild the bot is in
        for guild in self.guilds:
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):  # Ensure it's a text channel
                    chatdb_utils.insert_chat_channel(self.conn, channel)

    async def on_message(self, message):
        # don't respond to ourselves
        if message.author == self.user:
            return
        await self.process_commands(message)  # This line is needed to process commands
        # Ensure Message was sent by a bot buddy
        if isinstance(message.channel, discord.TextChannel):
            for role in message.author.roles:
                if role.name == "Bot Buddy":
                    await self.handle_bot_buddy_message(message)
                    break
        # If the message is a DM, treat the author as a Bot Buddy
        elif isinstance(message.channel, discord.DMChannel):
            await self.handle_bot_buddy_message(message)

    async def handle_bot_buddy_message(self, message):
        try:
            # log all messages from authors with the "Bot Buddy" role
            timestamp = datetime.now().isoformat()
            chatdb_utils.insert_user_if_not_exists(self.conn, (str(message.author.id), message.author.name))
            channel = str(message.channel) if not isinstance(message.channel, discord.DMChannel) else 'DM'
            clean_message = message.clean_content  # replaces discord ID mentions with user names
            chatdb_utils.insert_chat(self.conn, (timestamp, message.author.name, channel, clean_message))
            print(f"Logged a message: {clean_message} from {message.author.name} in {channel}")
            # respond only when the bot is mentioned
            if self.user in message.mentions:
                await message.channel.send('Received')
                print(f"Responded to a mention in a message: {clean_message} from {message.author.name}")
        except Exception as e:
            print(f"Error occurred: {e}")

def get_discord_token():
    with open('BotData/discord_token.txt', 'r') as file:
        return file.read().strip()

client = MyClient(command_prefix='!', intents=intents)  # Added a command prefix "!"

@client.command()
async def summarize(ctx, n: int):  # This decorator creates a new command named "summarize"
    """
    This command summarizes the last n messages from the channel it was called from.
    """
    channel_name = str(ctx.channel)
    summary = compile_recent_chats(client.conn, channel_name, n)

    # If the summary is longer than 2000 characters, Discord won't let us send it in a single message
    if len(summary) > 2000:
        # If it's too long, we can split it up and send it in chunks
        for i in range(0, len(summary), 2000):
            await ctx.send(summary[i:i+2000])
    else:
        # If it's short enough, we can just send it all at once
        await ctx.send(summary)

client.run(get_discord_token())
