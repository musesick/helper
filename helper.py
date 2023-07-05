import discord
import os
import chatdb_utils
from chatdb_utils import create_connection, insert_chat
from datetime import datetime

intents = discord.Intents.all()
intents.members = True
intents.presences = True
# establish connection
conn = chatdb_utils.create_connection()
# create table
chatdb_utils.create_table(conn)

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.conn = None

    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))
        self.conn = create_connection()

    async def on_message(self, message):
        # don't respond to ourselves
        if message.author == self.user:
            return
        # check if the author has the "Bot Buddy" role
        for role in message.author.roles:
            if role.name == "Bot Buddy":
                try:
                    # log all messages from authors with the "Bot Buddy" role
                    timestamp = datetime.now().isoformat()
                    insert_chat(self.conn, (timestamp, message.author.name, message.content))
                    print(f"Logged a message: {message.content} from {message.author.name}")

                    # respond only when the bot is mentioned
                    if self.user in message.mentions:
                        await message.channel.send('Received')
                        print(f"Responded to a mention in a message: {message.content} from {message.author.name}")
                except Exception as e:
                    print(f"Error occurred: {e}")
                break


def get_discord_token():
    with open('BotData/discord_token.txt', 'r') as file:
        return file.read().strip()


client = MyClient(intents=intents)
client.run(get_discord_token())
