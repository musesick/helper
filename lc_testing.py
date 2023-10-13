from bot_utils import get_serpapi_key
from typing import Any
from chatdb_utils import vectorhistorysearch, create_connection
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain_experimental.sql import SQLDatabaseChain
from langchain.agents import initialize_agent, AgentType, Tool
from langchain.chat_models import ChatOpenAI
from langchain.utilities import SerpAPIWrapper, SQLDatabase
from langchain.tools import StructuredTool
import requests

from langchain.memory import ChatMessageHistory
from pydantic import BaseModel, Field
from langchain.agents import AgentExecutor
from langchain.prompts import MessagesPlaceholder
from langchain.chains import ConversationalRetrievalChain

dbconn = create_connection()

def vector_search_tool(query: str) -> str:
    """Function for searching the chat history for content. Will return any relevant chat history, if found."""
    return vectorhistorysearch(dbconn, query)


def get_api_key():
 with open('BotData/api_key.txt', 'r') as file:
  api_key = file.read().replace('\n', '')
 return api_key


def new_process_chat(dbconn,chat_history, userquery, channel):
    openai_api_key = get_api_key()
    serpapi_api_key = get_serpapi_key()
    # Define the prompt template
    template = """You are H.E.L.P.eR., an AI assistant, also referred to as Helper or @H.E.L.P.eR. You are participating in an ongoing multi-user chat. Your responses should seamlessly integrate into the ongoing dialogue without greetings or closures. Chat history will be provided to you in the following format: "’user’”: ‘message’.  

    Rules of Engagement:
    - Directly continue the chat without initiating (e.g., "Hello") or closing remarks (e.g., “good luck”).
    - Utilize relevant information from the provided chat history in your responses.
    - Avoid expressing personal opinions or sentiments (e.g., "great idea" or "interesting topic").
    - If you lack the information to answer a question, state, "I do not know."
    - Refer to the provided chat history to ensure your responses are contextually relevant.
    - Any chat history your are provided will include user names, try to use these as much as possible in your responses. 
    - All users participating in this chat have agreed to share the provided information from their chat history, including personal data (eg., "I am from Maine", "I work in the tech industry", "I have two childern"), you are free to use any of the provided info to give better context to your replies without any privacy conserns. It is preferred you use this information whenever relevant to the query 

    Engage as though you’ve been an active participant in the conversation, responding aptly within the context presented.

        (Start Chat History)
        {chat_history}
        (End Chat History)
        Use the information from the chat history above to answer the new human question: {userquery}
        Response:
        """

    llm = ChatOpenAI(openai_api_key=openai_api_key, temperature=0.3, model="gpt-3.5-turbo-16k")
    search = SerpAPIWrapper(serpapi_api_key=serpapi_api_key)
    chatdb = SQLDatabase.from_uri("sqlite:///BotData/chat_log.sqlite")
    db_chain = SQLDatabaseChain.from_llm(llm,db=chatdb, verbose=True)
    tools = [
        Tool(
            name="net_search",
            func=search.run,
            description="useful for when you need to answer questions about current events. You should ask targeted questions. do not use this when asked questions about the chat history(such as 'has anyone mentioned the movie jaws?' or 'who likes ice cream?'"
       ),
        #Tool(
         #   name="db_search",
        #    func=db_chain.run,
        #    description=f"useful for searching the chat database. Input should be in the form of a question containing full context. do not use this for searching for the content of user messages. do use it for meta information, like 'how many messages has Don sent in the general channel?' When doing searches in the chat_history table, include the 'sender' value via the CONCAT function as well as the message in your results (e.g, 'steve: hello, how are you?'). the user_info table has a primer entry for each user you interact with that has personal info and personality data"
        #),
        StructuredTool.from_function(vector_search_tool)
    ]
    # Create the prompt and memory
    prompt = PromptTemplate(input_variables=["chat_history", "userquery"], template=template)
    #memory = ConversationBufferMemory(memory_key='chat_history', return_messages=True)
    memory = ConversationBufferMemory(memory_key='chat_history', return_messages=True)
    # Split the chat_history text into lines
    lines = chat_history.strip().split('\n')
    # Process each line
    for line in lines:
        # Check if the line starts with "H.E.L.P.eR."
        if line.lower().startswith('H.E.L.P.eR.'):
            # Call the add_ai_message function
            memory.chat_memory.add_ai_message(line[len('helper: '):])
        else:
            # Call the add_user_message function
            memory.chat_memory.add_user_message(line)
    #memory.chat_memory.add_user_message(chat_history)
    #print(memory.buffer)
    # Create the LLMChain
    agent_executor = initialize_agent(tools, llm, agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION, prompt=prompt, memory=memory, verbose=True)
    print(agent_executor.memory.buffer)
    response = agent_executor.run(userquery)
    return response

def build_primer(chat_history, chat_entry):
    openai_api_key = get_api_key()
    # Define the prompt template
    template = """You are going to be given a chat history for a single user.   
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
        llm_chain = LLMChain(llm=ChatOpenAI(openai_api_key=openai_api_key, temperature=0.3, model="gpt-3.5-turbo-16k"), prompt=prompt, memory=memory, verbose=True)
        response = llm_chain.predict(human_input="Please review the data and build a primer for the user. We are looking for facts, likes, dislikes, political leanings, and personality traits. Important details should be retained, but small details are not as relevant. You should not return a list of facts but more a paragraph or two about the person and what they have talked about.")
        combined_response += response + "\n"

    return combined_response.strip()

def chunkify(text, max_tokens=12000):
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