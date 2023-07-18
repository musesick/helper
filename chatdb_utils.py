import sqlite3
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
    if not message.startswith("@"):
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

def search_chat_history(conn, query):
    cur = conn.cursor()
    cur.execute("SELECT * FROM chat_history")
    rows = cur.fetchall()
    user_vector = lazy_loader.model.encode([query], show_progress_bar=False)[0]
    similar_msgs = []

    for i in range(len(rows)):
        msg_vector = string_to_vector(rows[i][5])  # Adjusted to correct index for 'vector' column
        similarity = cosine_similarity(user_vector, msg_vector)
        if similarity > 0.3:
            role = rows[i][2]  # 'sender' column
            content = rows[i][4]  # 'message' column
            similar_msgs.append({'role': role, 'content': content, 'similarity': similarity})

    similar_msgs = sorted(similar_msgs, key=lambda x: x['similarity'], reverse=True)

    # Take only the top 10 messages
    top_10_msgs = similar_msgs[:10]
    top_10_msgs_without_similarity = [{k: v for k, v in msg.items() if k != 'similarity'} for msg in top_10_msgs]

    return top_10_msgs_without_similarity