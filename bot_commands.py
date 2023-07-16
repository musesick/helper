from discord.ext import commands
from bot_utils import compile_recent_chats
import chatdb_utils

def setup_commands(client: commands.Bot):
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
    @client.command()
    async def usersummary(ctx, discord_name: str):  # This decorator creates a new command named "usersummary"
        """
        This command retrieves and summarizes the chat history of a specific user.
        """
        channel_name = str(ctx.channel)
        chat_history = chatdb_utils.retrieve_user_chat_history(client.conn, discord_name, channel_name)

        # If the chat history is empty, notify the user
        if not chat_history:
            await ctx.send(f"No chat history found for user {discord_name} in channel {channel_name}.")
        else:
            # We will compile the chats into a string where each message is in a new line with the format "discord_name: message"
            chat_string = "\n".join([f"{discord_name}: {message}" for message in chat_history])
            summary = bot_utils.generate_summary(chat_string)

            # If the summary is longer than 2000 characters, Discord won't let us send it in a single message
            if len(summary) > 2000:
                # If it's too long, we can split it up and send it in chunks
                for i in range(0, len(summary), 2000):
                    await ctx.send(summary[i:i+2000])
            else:
                # If it's short enough, we can just send it all at once
                await ctx.send(summary)