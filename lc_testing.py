from bot_utils import get_serpapi_key
from chatdb_utils import vectorhistorysearch
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain_experimental.sql import SQLDatabaseChain
from langchain.agents import initialize_agent, AgentType, Tool
from langchain.chat_models import ChatOpenAI
from langchain.utilities import SerpAPIWrapper, SQLDatabase
from langchain.agents import AgentExecutor
from langchain.prompts import MessagesPlaceholder

def get_api_key():
 with open('BotData/api_key.txt', 'r') as file:
  api_key = file.read().replace('\n', '')
 return api_key

def vector_search_tool(conn, query):
    return vectorhistorysearch(conn, query)

def new_process_chat(conn,chat_history, query, channel):
    openai_api_key = get_api_key()
    serpapi_api_key = get_serpapi_key()
    # Define the prompt template
    template = """You are playing the role of H.E.L.P.eR. (a.k.a Helper or @H.E.L.P.eR.). Helper is an AI assistant. You will be provided chat conversation between users in the following format: "user" : "message" and will be expected to give a respond as if part of the ongoing chat. Do not begin your answer with a greeting or introduction, such as "Hey there" or "Hello (user)". Keep up the illusion you have been a part of the conversation the whole time. Please use any of the provided information in your response if relevant. If you do not know the answer to a question, you truthfully say you do not know. If you are not being asked a question, respond as best you can in the given context. Do not impart your ownaopinion such as "that's a great idea" or "x is an intresting topic". Do not close with phrases like “good luck” or “enjoy” as this converstaion is ongoing.     
        (Start Chat History)
        {chat_history}
        (End Chat History)
        Human: {human_input}
        """
    llm = ChatOpenAI(openai_api_key=openai_api_key, temperature=0.3, model="gpt-3.5-turbo-16k")
    search = SerpAPIWrapper(serpapi_api_key=serpapi_api_key)
    chatdb = SQLDatabase.from_uri("sqlite:///BotData/chat_log.sqlite")
    db_chain = SQLDatabaseChain.from_llm(llm,db=chatdb, verbose=True)
    tools = [
        Tool(
            name="net_search",
            func=search.run,
            description="useful for when you need to answer questions about current events, specifically events that have taken place after the cutoff of your training date. do not use for queries relating to events before your training date. You should ask targeted questions"
        ),
        Tool(
            name="db_search",
            func=db_chain.run,
            description=f"useful for when you need to answer questions about chat participants. Input should be in the form of a question containing full context. take into account the channel the query was sent from, in this case: {channel}. do not use this for searching for the text of user messages. do use it for meta information searches, like 'how many messages has Don sent in the games channel"
        ),
        Tool(
            name="vector_search",
            func=vector_search_tool,
            description=f"useful when you need to search the chat message history.",
            return_direct=True,
        )
    ]
    # Create the prompt and memory
    prompt = PromptTemplate(input_variables=["chat_history", "human_input"], template=template)
    memory = ConversationBufferMemory(memory_key='chat_history')
    memory.chat_memory.add_user_message(chat_history)
    print(memory.buffer)
    # Create the LLMChain
    agent_executor = initialize_agent(tools, llm, agent=AgentType.OPENAI_FUNCTIONS, prompt=prompt, memory=memory, verbose=True)
    response = agent_executor.run(query)
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