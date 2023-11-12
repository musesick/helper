import sqlite3
from bot_utils import process_search_results
from sqlite3 import Error
from numpy.linalg import norm
import numpy as np

class LazyLoader:
    def __init__(self):
        self._nlp = None
        self._model = None

    @property
    def nlp(self):
        if self._nlp is None:
            import spacy
            self._nlp = spacy.load('en_core_web_md')
        return self._nlp

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer('all-MiniLM-L6-v2')#multi-qa-mpnet-base-dot-v1
        return self._model

lazy_loader = LazyLoader()

def create_connection():
    conn = None
    try:
        conn = sqlite3.connect('BotData/chat_log.sqlite')
        print(sqlite3.version)
    except Error as e:
        print(f"Error occurred: {e}")
        raise  # Re-raise the exception so it can be handled elsewhere
    if not conn:
        raise Exception("Failed to create a database connection.")
    return conn

def insert_chat_channel(conn, channel):
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM chat_channels WHERE id = ?", (channel.id,))
        rows = cur.fetchall()
        if len(rows) == 0:
            cur.execute("INSERT INTO chat_channels(id, channel_name) VALUES(?, ?)", (channel.id, channel.name,))
            conn.commit()
    except Error as e:
        print(e)


def insert_user_if_not_exists(conn, user):
    discord_id, discord_name = user
    cur = conn.cursor()
    cur.execute("SELECT * FROM user_info WHERE discord_id = ?", (discord_id,))
    rows = cur.fetchall()
    if len(rows) == 0:
        cur.execute("INSERT INTO user_info(discord_id, discord_name) VALUES(?, ?)", user)
        conn.commit()

def compute_vector(message):
    return ','.join(str(x) for x in lazy_loader.model.encode([message], show_progress_bar=False)[0])

def preprocess_message(message):
    doc = lazy_loader.nlp(message.lower())
    return ' '.join([token.text for token in doc if not token.is_punct])

def string_to_vector(vector_string):
    return np.fromstring(vector_string, sep=',')

def cosine_similarity(a, b):
    return np.dot(a, b) / (norm(a) * norm(b))

def insert_chat(conn, chat):
    timestamp, sender, channel, message = chat
    #if not message.startswith("@"):
        # preprocess the message
    message = preprocess_message(message)
    vector = compute_vector(message)
    sql = ''' INSERT INTO chat_history(timestamp, sender, channel, message, vector)
                  VALUES(?,?,?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, chat[:2] + (channel, message, vector,))
    conn.commit()
    return cur.lastrowid

def update_vectors_in_database(conn):
    cur = conn.cursor()
    # Select all rows in the database
    cur.execute("SELECT * FROM chat_history")
    rows = cur.fetchall()
    # For each row, update the vector
    for row in rows:
        new_vector = compute_vector(row[3])  # Assuming the message is in the fourth column
        cur.execute("UPDATE chat_history SET vector = ? WHERE id = ?", (new_vector, row[0]))
    # Commit the changes
    conn.commit()

def retrieve_user_chat_history(conn, discord_name, channel_name=None):
    """
    Retrieve the chat history of a specific user from the database.
    """
    cur = conn.cursor()
    if channel_name:
        cur.execute("SELECT id, timestamp, sender, channel, message FROM chat_history WHERE sender = ? AND channel = ?", (discord_name, channel_name))
    else:
        cur.execute("SELECT id, timestamp, sender, channel, message FROM chat_history WHERE sender = ?", (discord_name,))
    rows = cur.fetchall()
    return rows

from datetime import datetime

def search_chat_history(conn, query):
    cur = conn.cursor()
    cur.execute("SELECT * FROM chat_history")
    rows = cur.fetchall()
    user_vector = lazy_loader.model.encode([query], show_progress_bar=False)[0]
    similar_msgs = []

    for i in range(len(rows)):
        msg_vector = string_to_vector(rows[i][5])
        similarity = cosine_similarity(user_vector, msg_vector)
        timestamp_str = rows[i][1]  # 'timestamp' column as a string
        sender = rows[i][2]  # 'sender' column
        message = rows[i][4]  # 'message' column
        channel = rows[i][3]  # 'channel' column
        # Exclude messages from the specified channel
        if sender != "H.E.L.P.eR." and similarity > 0.3 and "@h.e.l.p.er" not in message and channel != "python-enjoyers":
            # Parse the timestamp string into a datetime object
            timestamp_datetime = datetime.fromisoformat(timestamp_str)
            # Convert datetime to a Unix timestamp (integer)
            timestamp = int(timestamp_datetime.timestamp())
            similar_msgs.append({'id': rows[i][0], 'role': sender, 'content': message, 'similarity': similarity, 'timestamp': timestamp, 'channel': channel})

    similar_msgs = sorted(similar_msgs, key=lambda x: x['similarity'], reverse=True)[:20]
    print(similar_msgs)
    # Create conversation bits for the top 20 results
    top_20_conversations = []
    for msg in similar_msgs:
        idx = msg['id']
        channel = msg['channel']
        timestamp = msg['timestamp']
        conversation = []
        # Re-query the database for messages before and after the result within the same channel
        target_id = msg['id']
        cur.execute(
            "SELECT * FROM chat_history WHERE channel = ? AND id BETWEEN ? AND ? ORDER BY id",
            (channel, target_id - 2, target_id + 2))
        context_msgs = cur.fetchall()

        for context_msg in context_msgs:
            conversation.append({
                'id': context_msg[0],
                'role': context_msg[2],
                'content': context_msg[4],
                'timestamp': context_msg[1],
                'channel': context_msg[3]
            })

        # Add conversation bits with context to the list
        top_20_conversations.append(conversation)

    # ...

    # Remove 'similarity' field from each message in each conversation
    #for conversation in top_20_conversations:
    #    for msg in conversation:
    #        del msg['similarity']
    print(top_20_conversations)
    return top_20_conversations




def recent_chats(conn, channel_name, n):
    if not isinstance(channel_name, str):
        raise ValueError(f"channel_name must be a string, not {type(channel_name)}")
    if not isinstance(n, int):
        raise ValueError(f"n must be an integer, not {type(n)}")
    cur = conn.cursor()
    cur.execute("SELECT sender, message FROM chat_history WHERE channel = ? ORDER BY id DESC LIMIT ?",
                (channel_name, n,))
    rows = cur.fetchall()
    # Reverse the rows list
    rows = rows[::-1]
    chat_string = "\n".join([f"{row[0]}: {row[1]}" for row in rows])
    # Write to a text file
    return chat_string

def compile_user_history(conn, user_name, output_file="user_history.txt"):
    # Create a cursor object
    cur = conn.cursor()
    # Query to fetch all messages by the user
    cur.execute("SELECT channel, sender, message FROM chat_history WHERE sender = ?", (user_name,))
    rows = cur.fetchall()
    # Group by channel
    channel_data = {}
    for row in rows:
        channel, sender, message = row
        if channel not in channel_data:
            channel_data[channel] = []
        channel_data[channel].append(f"{sender}: {message}")
    # Write to file
    with open(output_file, 'w') as file:
        for channel, messages in channel_data.items():
            file.write(f"--- {channel} ---\n")
            file.write('\n'.join(messages))
            file.write("\n\n")  # Separate channels with two newline characters
    print(f"User history for {user_name} has been written to {output_file}")
    return


def vectorhistorysearch(ctx, query: str):
    """
    This command searches the chat history for the provided query and returns the top 10 relevant messages.
    """
    results = search_chat_history(ctx, query)

    if not results:
        ctx.send("No results found.")
        return

    results_text = ""
    for conversation in results:
        for result in conversation:
            results_text += f"{result['role']} ({result['timestamp']}): {result['content']}\n"
        results_text += "===\n"  # Separate conversation bits with ===

    return results_text


