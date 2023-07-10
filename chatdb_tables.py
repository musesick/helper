from sqlite3 import Error

def create_chat_channels_table(conn):
    try:
        sql = ''' CREATE TABLE IF NOT EXISTS chat_channels (
                                          id integer PRIMARY KEY,
                                          channel_name text NOT NULL,
                                          description text,
                                          short_term text,
                                          long_term text
                                      ); '''
        conn.execute(sql)
    except Error as e:
        print(e)

def create_user_table(conn):
    try:
        sql = ''' CREATE TABLE IF NOT EXISTS user_info (
                                          id integer PRIMARY KEY,
                                          discord_id text NOT NULL,
                                          discord_name text NOT NULL,
                                          real_name text,
                                          primer text,
                                          history_summary text
                                      ); '''
        conn.execute(sql)
    except Error as e:
        print(e)

def create_chat_table(conn):
    try:
        sql = ''' CREATE TABLE IF NOT EXISTS chat_history (
                                          id integer PRIMARY KEY,
                                          timestamp text NOT NULL,
                                          sender text NOT NULL,
                                          channel text NOT NULL,
                                          message text NOT NULL,
                                          vector text NOT NULL
                                      ); '''
        conn.execute(sql)
    except Error as e:
        print(e)
