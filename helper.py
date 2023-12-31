import os
import random
from datetime import datetime

import discord
from discord.ext import commands

import chatdb_tables
import chatdb_utils
from bot_commands import setup_commands
from bot_utils import analyze_image, fetch_and_log_missed_messages
from chatdb_utils import create_connection, recent_chats
from lc_testing import new_process_chat

PROCESS_MESSAGES = True
intents = discord.Intents.all()
intents.members = True
intents.presences = True
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'BotData/discordbotapi-393503-0947dda1c133.json'

# establish connection
conn = chatdb_utils.create_connection()

# create table
chatdb_tables.create_user_table(conn)  # Creating user table on bot start
chatdb_tables.create_chat_channels_table(conn)  # Creating chat_channels table on bot start


class MyClient(commands.Bot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conn = None

    async def on_ready(self):
        print(os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))
        print('Logged on as {0}!'.format(self.user))
        self.conn = create_connection()
        # Call create_chat_channels_table for each guild the bot is in
        for guild in self.guilds:
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):  # Ensure it's a text channel
                    chatdb_utils.insert_chat_channel(self.conn, channel)
        #check for missed messages
        conn = create_connection()
        await fetch_and_log_missed_messages(self,conn)

    async def on_message(self, message):
        if not PROCESS_MESSAGES:
            return
        # don't respond to ourselves
        if message.author == self.user:
            timestamp = datetime.now().isoformat()
            # checks to see if the message is from a user we've never interacted with
            chatdb_utils.insert_user_if_not_exists(self.conn, (str(message.author.id), message.author.name))
            channel = str(message.channel) if not isinstance(message.channel, discord.DMChannel) else 'DM'
            clean_message = message.clean_content  # replaces discord ID mentions with user names
            chatdb_utils.insert_chat(self.conn, (timestamp, message.author.name, channel, clean_message))
            print(f"Logged a message: {clean_message} from {message.author.name} in {channel}")
            return

        # process commands and return if the message starts with the command prefix
        if message.content.startswith('!'):
            await self.process_commands(message)
            return

        # If the message author is "Zos", send a special response
        elif message.author.name.lower() == "zos":
            random_name = get_random_line_from_file("BotData/names.txt")
            await message.channel.send(f"ok, {random_name}")

        # Ensure Message was sent by a bot buddy
        elif isinstance(message.channel, discord.TextChannel):
            for role in message.author.roles:
                if role.name == "Bot Buddy":
                    if message.attachments:
                        for attachment in message.attachments:
                            # Download the attachment
                            file_path = f'./images/{attachment.filename}'
                            await attachment.save(file_path)
                            # Analyze the image
                            #description = analyze_image(file_path)
                            # Send the description
                            # await message.channel.send(description)
                    else:
                        await self.handle_bot_buddy_message(message)

        # If the message is a DM, treat the author as a Bot Buddy
        elif isinstance(message.channel, discord.DMChannel):
            await self.handle_bot_buddy_message(message)

    async def handle_bot_buddy_message(self, message):
        #try:
            # log all messages from authors with the "Bot Buddy" role
            timestamp = datetime.now().isoformat()
            # checks to see if the message is from a user we've never interacted with
            chatdb_utils.insert_user_if_not_exists(self.conn, (str(message.author.id), message.author.name))
            channel = str(message.channel) if not isinstance(message.channel, discord.DMChannel) else 'DM'
            clean_message = message.clean_content  # replaces discord ID mentions with user names
            chatdb_utils.insert_chat(self.conn, (timestamp, message.author.name, channel, clean_message))
            print(f"Logged a message: {clean_message} from {message.author.name} in {channel}")
            # respond only when the bot is mentioned
            if self.user in message.mentions:
                channel_name = message.channel.name
                message_content = message.clean_content
                chat_history = recent_chats(client.conn, channel_name, 40)
                response = new_process_chat(self.conn, chat_history, message_content, channel)
                # send the response back to the channel
                await message.channel.send(response)
                print(f"Responded to a mention in a message: {clean_message} from {message.author.name}")

        #except Exception as e:
           #print(f"Error occurred: {e}")
def get_discord_token():
    with open('BotData/discord_token.txt', 'r') as file:
        return file.read().strip()

def get_random_line_from_file(file_name):
    """Return a random line from a file."""
    with open(file_name, 'r') as f:
        lines = f.readlines()
    return random.choice(lines).strip()  # Removes newline characters from the chosen line

client = MyClient(command_prefix='!', intents=intents)  # Added a command prefix "!"
# Add your bot commands
setup_commands(client)
client.run(get_discord_token())
