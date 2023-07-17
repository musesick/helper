import openai
import logging

from datetime import datetime

logging.basicConfig(filename='BotData/openai_log.txt', level=logging.INFO, format='%(asctime)s:%(message)s')

def count_tokens(text):
    return len(text.split())

def get_api_key():
    with open('BotData/api_key.txt', 'r') as file:
        api_key = file.read().replace('\n', '')
    return api_key

def log_openai_interaction(time, content, response, tokens_used):
    log_message = f"\n{'*' * 20}\nTime: {time}\nContent Sent: {content}\nResponse: {response}\nTokens Used: {tokens_used}\n{'*' * 20}"
    logging.info(log_message)

def get_timestamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def compile_recent_chats(conn, channel_name, n):
    cur = conn.cursor()
    cur.execute("SELECT sender, message FROM chat_history WHERE channel = ? ORDER BY id DESC LIMIT ?", (channel_name, n,))
    rows = cur.fetchall()
    # rows are returned in the format [(sender, message), ...]
    # We will compile the chats into a string where each message is in a new line with the format "sender: message"
    chat_string = "\n".join([f"{row[0]}: {row[1]}" for row in rows])
    # Write to a text file
    summary = generate_summary(chat_string)
    return summary

def generate_summary(text):
    openai.api_key = get_api_key()

    tokens = count_tokens(text)
    if tokens > 2048:  # Half of the maximum limit
        middle = len(text) // 2
        split1 = text[:middle]
        split2 = text[middle:]
        return generate_summary(split1) + generate_summary(split2)
    else:
        # Include a prompt to summarize the text
        prompt = f"I have the following text from a conversation, and I need a summary. \n\n{text}\n\nSummary:"
        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=prompt,
            temperature=0.3,
            max_tokens=1500
        )
        # Log the interaction with OpenAI
        timestamp = get_timestamp()
        content_sent = text
        response_text = response.choices[0].text.strip()
        tokens_used = response['usage']['total_tokens']
        log_openai_interaction(timestamp, content_sent, response_text, tokens_used)
        return response_text


def generate_user_summary(text):
    openai.api_key = get_api_key()

    tokens = count_tokens(text)
    if tokens > 2048:  # Half of the maximum limit
        middle = len(text) // 2
        split1 = text[:middle]
        split2 = text[middle:]
        return generate_user_summary(split1) + generate_user_summary(split2)
    else:
        # Include a prompt to summarize the text
        prompt = f"Here is a chat history for a single user. Please create a personality profile and summary of any personal information (likes, dislikes, historical data) the user has provided. Please try to retain as much specific data about the person as possible. \n\n{text}\n\nSummary:"
        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=prompt,
            temperature=0.6,
            max_tokens=1500
        )
        # Log the interaction with OpenAI
        timestamp = get_timestamp()
        content_sent = text
        response_text = response.choices[0].text.strip()
        tokens_used = response['usage']['total_tokens']
        log_openai_interaction(timestamp, content_sent, response_text, tokens_used)
        return response_text

