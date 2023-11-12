from discord.ext import commands
from lc_testing import build_primer
from bot_utils import compile_recent_chats, generate_summary, generate_user_summary, process_search_results, primer_check
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

        # Send the query and results to new function in bot_utils.py
        processed_results = process_search_results(query, results_text)

        # If the processed_results is longer than 2000 characters, Discord won't let us send it in a single message
        if len(processed_results) > 2000:
            # If it's too long, we can split it up and send it in chunks
            for i in range(0, len(processed_results), 2000):
                await ctx.send(processed_results[i:i + 2000])
        else:
            # If it's short enough, we can just send it all at once
            await ctx.send(processed_results)

    @client.command()
    async def buildprimerX(ctx, user_name: str, output_file="BotData/user_history.txt"):
        """
        This command compiles the chat history of a given user and writes it to a text file.
        """
        # Create a connection cursor
        cur = client.conn.cursor()
        # Query to fetch all messages by the user
        cur.execute("SELECT channel, sender, message FROM chat_history WHERE sender = ?", (user_name,))
        rows = cur.fetchall()
        # Group by channel
        channel_data = {}
        for row in rows:
            channel, sender, message = row
            if channel not in channel_data:
                channel_data[channel] = []
            channel_data[channel].append(message)  # Only appending the message, not the sender's name

        # Compile messages
        messages = []
        for channel, msgs in channel_data.items():
            messages.append(f"=== {channel} ===")
            messages.extend(msgs)

        chat_string = '\n'.join(messages)
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as file:
            for channel, messages in channel_data.items():
                file.write(f"--- {channel} ---\n")
                file.write('\n'.join(messages))
                file.write("\n\n")  # Separate channels with two newline characters

        # Generate the primer
        primer = build_primer(chat_string, " ")

        # Write the primer to a new file
        with open("BotData/user_primer.txt", 'w', encoding='utf-8') as primer_file:
            primer_file.write(primer)

        # Update the database
        cur.execute("UPDATE user_info SET primer = ? WHERE discord_name = ?", (primer, user_name))
        client.conn.commit()

        await ctx.send(f"User history for {user_name} has been written to {output_file} and primer saved.")

    @client.command()
    async def spillthetea(ctx, discord_name: str):
        """
        This command fetches the primer for a given user from the user_info table.
        """
        # Ensure that the discord_name is a string
        if not isinstance(discord_name, str):
            await ctx.send("Invalid username provided.")
            return

        # Create a connection cursor
        cur = client.conn.cursor()

        # Query the database for the primer associated with the provided discord_name
        cur.execute("SELECT primer FROM user_info WHERE discord_name = ?", (discord_name,))
        result = cur.fetchone()

        # If an entry is found, send the primer to the chat
        if result:
            primer_text = result[0]

            # Check if primer_text is longer than 2000 characters
            if len(primer_text) <= 2000:
                await ctx.send(f"Primer for {discord_name}: {primer_text}")
            else:
                # Split the text into chunks of 2000 characters and send them as separate messages
                chunks = [primer_text[i:i + 2000] for i in range(0, len(primer_text), 2000)]
                for chunk in chunks:
                    await ctx.send(chunk)
        else:
            await ctx.send(f"No primer found for {discord_name}.")

    @client.command()
    async def primercheck(ctx, input_string: str):
        """
        This command checks the first word of the input string, looks up the user in the database,
        and passes the username and the remaining messages to the primer_check function.
        """
        # Split the input string into words
        words = input_string.split()

        # Ensure that at least one word is provided
        if not words:
            await ctx.send("No input provided.")
            return

        # Check if the input string starts with "!" and remove it along with the next word
        if words[0].startswith("!") and len(words) >= 2:
            words.pop(0)  # Remove the "!" character
            words.pop(0)  # Remove the next word

        # Reconstruct the remaining words into a string
        cleaned_input = ' '.join(words)

        # Extract the first word (presumed to be the username)
        username = words[0]

        # Check if the user exists in the database
        cur = client.conn.cursor()
        cur.execute("SELECT * FROM user_info WHERE discord_name = ?", (username,))
        result = cur.fetchone()
        print(f"Primer function for: {words}")
        if result:
            # If the user is found, extract the primer text
            primer_text = result[1]  # Assuming primer text is in the second column (change as needed)

            # Pass both username and primer_text to the primer_check function
            await primer_check(ctx, username, primer_text)

        else:
            await ctx.send(f"No user with the username '{username}' found in the database.")







