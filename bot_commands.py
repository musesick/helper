from discord.ext import commands
from bot_utils import compile_recent_chats, generate_summary, generate_user_summary, process_search_results
from chatdb_utils import search_chat_history
import chatdb_utils

def setup_commands(client: commands.Bot):
    @client.command()
    async def summarize(ctx, n: int):
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
    async def usersummary(ctx, discord_name: str):
        """
        This command retrieves and summarizes the chat history of a specific user for the current channel.
        """
        channel_name = str(ctx.channel)
        chat_history = chatdb_utils.retrieve_user_chat_history(client.conn, discord_name, channel_name)

        # If the chat history is empty, notify the user
        if not chat_history:
            await ctx.send(f"No chat history found for user {discord_name} in channel {channel_name}.")
        else:
            # We will compile the chats into a string where each message is in a new line with the format "discord_name: message"
            chat_string = "\n".join([f"{discord_name}: {message}" for message in chat_history])
            summary = generate_summary(chat_string)

            # If the summary is longer than 2000 characters, Discord won't let us send it in a single message
            if len(summary) > 2000:
                # If it's too long, we can split it up and send it in chunks
                for i in range(0, len(summary), 2000):
                    await ctx.send(summary[i:i + 2000])
            else:
                # If it's short enough, we can just send it all at once
                await ctx.send(summary)

    @client.command()
    async def userhistory(ctx, discord_name: str, file_name: str = "BotData/user_chat_history.txt"):
        """
        This command retrieves all chat history of a specific user and outputs it to a text file.
        """
        # Get the chat history from the database
        chat_history = chatdb_utils.retrieve_user_chat_history(ctx.bot.conn, discord_name)

        # Check if the chat history is empty
        if not chat_history:
            await ctx.send(f"No chat history found for user {discord_name}.")
            return

        # Prepare the chat history for writing to a file
        chat_text = []
        for idx, message in enumerate(chat_history):
            try:
                line = f"{message[2]}: {message[4]}"  # create the line
                chat_text.append(line)
            except IndexError as e:
                print(
                    f"Error at index {idx} with message: {message}")  # print an error message with the offending tuple and its index
                raise e  # re-raise the exception to stop the program

        chat_text = "\n".join(chat_text)

        # Generate summary using bot_utils.generate_summary
        summary = generate_user_summary(chat_text)
        # If the summary is longer than 2000 characters, Discord won't let us send it in a single message
        if len(summary) > 2000:
            # If it's too long, we can split it up and send it in chunks
            for i in range(0, len(summary), 2000):
                await ctx.send(summary[i:i + 2000])
        else:
            # If it's short enough, we can just send it all at once
            await ctx.send(summary)

    @client.command()
    async def historysearch(ctx, *, query: str):
        """
        This command searches the chat history for the provided query and returns the top 10 relevant messages.
        """
        results = search_chat_history(client.conn, query)

        # Format results for displaying as "user: message"
        results_text = "\n\n".join([f"{result['role']}: {result['content']}" for result in results])

        if not results_text.strip():
            await ctx.send("No results found.")
            return

        # Send the query and results to your new function in bot_utils.py
        processed_results = process_search_results(query, results_text)

        # If the processed_results is longer than 2000 characters, Discord won't let us send it in a single message
        if len(processed_results) > 2000:
            # If it's too long, we can split it up and send it in chunks
            for i in range(0, len(processed_results), 2000):
                await ctx.send(processed_results[i:i + 2000])
        else:
            # If it's short enough, we can just send it all at once
            await ctx.send(processed_results)


