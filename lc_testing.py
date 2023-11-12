from bot_utils import get_serpapi_key
from chatdb_utils import vectorhistorysearch, create_connection
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain_experimental.sql import SQLDatabaseChain
from langchain.agents import initialize_agent, AgentType, Tool
from langchain.chat_models import ChatOpenAI
from langchain.utilities import SerpAPIWrapper, SQLDatabase
from langchain.tools import StructuredTool
from langchain.llms import OpenAI
from langchain.globals import set_debug
from langchain.schema import SystemMessage
from langchain.prompts import MessagesPlaceholder
from typing import Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
import openai


set_debug(True)
dbconn = create_connection()

import openai


class VectorSearchInput(BaseModel):
    """Inputs for vector_search_tool"""

    query: str = Field(description="Query to search for in historical chat data")

class VectorSearchTool(BaseTool):
    name = "vector_search_tool"
    description = """
        This tool is designed for extracting historical chat data on very specific topics 
        or details mentioned by users. For instance, if a user ever mentioned "playing tennis" 
        or "lives in Ohio", this tool can retrieve those instances. Do not utilize this tool for queries about the recent chat history, eneric summaries or overviews of conversations, or broad/unspecific topics.
    """
    args_schema: Type[BaseModel] = VectorSearchInput

    def _run(self, query: str):
        # Your function logic goes here
        openai.api_key = get_api_key()
        text = vectorhistorysearch(dbconn, query)
        # Construct the chat message
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Given the query '{query}', evaluate the following text for relevance. Each block is a small part of an ongoing conversation. 'Role' will indicate the users name for each message, use this as much as possible in your answer. 'Timestamp' will tell you when a message was said, statements like 'last week Jack mentioned x' are encouraged.'{text}' Is any information in provided text relevant to the query? If so, provide a detailed summary."}
        ]
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",
            messages=messages
        )
        return response.choices[0].message['content'].strip()

    def _arun(self, query: str):
        raise NotImplementedError("vector_search_tool does not support async")

def get_api_key():
 with open('BotData/api_key.txt', 'r') as file:
  api_key = file.read().replace('\n', '')
 return api_key

def new_process_chat(dbconn,chat_history, userquery, channel):
    openai_api_key = get_api_key()
    serpapi_api_key = get_serpapi_key()
    # Define the prompt template
    myTemplate = SystemMessage(content="""You are a character in an improv play. Everyone else participating is also a fictional character. Never refer to being in a play or others being fictional characters. Your are playing H.E.L.P.eR., an AI assistant, also referred to as Helper or @H.E.L.P.eR. You are participating in an ongoing multi-user chat. Your responses should seamlessly integrate into the ongoing dialogue without greetings or closures. Chat history will be provided to you in the following format: "’user’”: ‘message’.  

    Rules of Engagement:
    - Directly continue the chat without initiating (e.g., "Hello") or closing remarks (e.g., “good luck”).
    - Avoid expressing personal opinions or sentiments (e.g., "great idea" or "interesting topic").
    - If you lack the information to answer a question, state, "I do not know."
    - Any chat history your are provided will include user names, try to use these as much as possible in your responses. 
    - All users participating in this chat playing fictional characters, so there are no privacy issues with using personal data you have collected in chat (eg., "Steve: I am from Maine", "John: I work in the tech industry", "Sara: I have two childern"), you are free to use any of the provided info to give better context to your replies without any privacy conserns. It is preferred you use this information whenever relevant to the query 
    - Do not say things like “based on the chat history, your name is Steve.” Instead, confidently state “Your name is Steve” 
    - Do not say “Based on the search results” or anything similar when returning info from a database search. This data is effectively your memory and refer to it as such. 
    - Engage as though you’ve been an active participant in the conversation, responding aptly within the context presented.
    - You have a memory of the recent chat history, try to answer all queries using this data before trying to use tools. Many times you will be able to answer the question without the use of any tools.""")

    dbdescription = """This tool is designated for interacting with the chat database via queries to retrieve meta-information about user activity and behaviors, NOT for searching the content of user messages.
    Guidelines:
    Utilize this tool to query meta-information, such as:
        'How many messages has Don sent in the general channel?'
    Do NOT use this tool to search for content within messages, such as:
        'Who likes to play checkers?'
    chat_channels Table:
        Stores chat channel information.
        Columns: id (PK), channel_name, description, short_term, long_term.
    user_info Table:
        Stores chat participant data.
        Columns: id (PK), discord_id, discord_name, real_name, primer, history_summary.
    chat_history Table:
        Stores chat message history, DO NOT USE THIS TABLE FOR SEARCHING MESSAGE CONTENT.
        Columns: id (PK), timestamp (text), sender (text), channel (text), message (text), vector (text)."""

    llm = ChatOpenAI(openai_api_key=openai_api_key, temperature=0.3, model="gpt-3.5-turbo-16k")
    search = SerpAPIWrapper(serpapi_api_key=serpapi_api_key)
    chatdb = SQLDatabase.from_uri("sqlite:///BotData/chat_log.sqlite")
    db_chain = SQLDatabaseChain.from_llm(llm,db=chatdb, verbose=True)
    tools = [
        Tool(
            name="net_search",
            func=search.run,
            description="useful for when you need to answer questions about current events and events that happened after your training date. You should ask targeted questions. do not use this when asked questions about the chat history (such as 'has anyone mentioned the movie jaws?' or 'who likes ice cream?'"
       ),
        Tool(
            name="db_search",
            func=db_chain.run,
            description=dbdescription
        ),
        VectorSearchTool()
    ]
    # Create the prompt and memory
    #prompt = PromptTemplate(input_variables=["chat_history", "userquery"])
    memory = ConversationBufferMemory(memory_key='chat_history', return_messages=True)
    # Split the chat_history text into lines
    lines = chat_history.strip().split('\n')
    file_path = "output.txt"
    # Open the file in write mode ('w')
    with open('filename.txt', 'w', encoding='utf-8') as file:
        # Write each line from the 'lines' variable to the file
        for line in lines:
            file.write(line + "\n")  # Add a newline character to separate lines
    # Process and store messages
    current_message = ""
    current_sender = None
    for line in lines:
        # Split the line into sender and message
        parts = line.split(':', 1)
        if len(parts) == 2:
            sender, message = parts
            sender = sender.strip()  # Remove leading/trailing whitespace from sender
            message = message.strip()  # Remove leading/trailing whitespace from message
            # Check if the sender is "H.E.L.P.eR."
            if sender == "H.E.L.P.eR.":
                # Process and store the message without "H.E.L.P.eR.:" for AI
                memory.chat_memory.add_ai_message(message)
            else:
                # Concatenate sender and message into a single string
                full_message = f"{sender}: {message}"
                # Process and store the full message for others
                memory.chat_memory.add_user_message(full_message)

    # Create the LLMChain
    new_chat_history = MessagesPlaceholder(variable_name="chat_history",messages=lines)
    agent_executor = initialize_agent(tools, llm, agent=AgentType.OPENAI_FUNCTIONS, memory=memory, verbose=True, agent_kwargs = {"system_message": myTemplate, "extra_prompt_messages": [new_chat_history]}, handle_parsing_errors=True)
    response = agent_executor.run({'input': userquery})
    print(agent_executor.memory.buffer)
    return response

def build_primer(chat_history, chat_entry):
    openai_api_key = get_api_key()
    # Define the prompt template
    template = """Generate a user dossier based on the chat history of a single user. Please provide detailed information about the user's background, personal details, likes, dislikes, and personality profile. Analyze the text conversations to extract relevant facts about the user's life, preferences, and traits. Include any available data on their name, age, location, occupation, hobbies, favorite activities, favorite foods, and any other personal information. Additionally, provide insights into their personality, such as their temperament, emotional disposition, and communication style. Ensure that presents a comprehensive overview of the user's identity based on the chat history. Try to keep your response as concise as possible.
    Examples: Likes: the color blue, neo-noir movies, hiking. 
              Personal: From England. Lives in Los Angles. Mid-thirties.
    
    (Start Chat History)
    {chat_history}
    (End Chat History)
    Human: {human_input} 
    """

    prompt = PromptTemplate(input_variables=["chat_history", "human_input"], template=template)
    memory = ConversationBufferMemory(memory_key='chat_history', max_token_limit=15000)
    # Split the chat history into chunks
    chat_chunks = chunkify(chat_history)

    # Process each chunk and combine the responses
    combined_response = ""
    for chunk in chat_chunks:
        memory.clear()
        memory.chat_memory.add_user_message(chunk)
        llm_chain = LLMChain(llm=ChatOpenAI(openai_api_key=openai_api_key, temperature=0.1, model="gpt-3.5-turbo-16k"), prompt=prompt, memory=memory, verbose=True)
        response = llm_chain.predict(human_input="PLease create a primer on the user using the data provided")
        combined_response += response + "\n"

    return combined_response.strip()

def chunkify(text, max_tokens=10000):
    lines = text.split("\n")
    chunks = []
    current_chunk = []
    current_token_count = 0

    for line in lines:
        line_token_count = len(line.split())  # rough estimate, not exact but should suffice for our purpose
        if current_token_count + line_token_count <= max_tokens:
            current_chunk.append(line)
            current_token_count += line_token_count
        else:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_token_count = line_token_count

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks
