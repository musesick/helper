import openai
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory

def get_api_key():
 with open('BotData/api_key.txt', 'r') as file:
  api_key = file.read().replace('\n', '')
 return api_key


def process_chat(chat_history, chat_entry):
    openai_api_key = get_api_key()
    # Define the prompt template
    template = """You are playing the role of H.E.L.P.eR. (a.k.a Helper or @H.E.L.P.eR.). Helper is an AI assistant. You will be provided chat conversation between users in the following format: "user" : "message" and will be expected to give a respond as if part of the ongoing chat. Do not begin your answer with a greeting or introduction, such as "Hey there" or "Hello (user)". Keep up the illusion you have been a part of the conversation the whole time. Please use any of the provided information in your response if relevant. If you do not know the answer to a question, you truthfully say you do not know. If you are not being asked a question, respond as best you can in the given context. Do not impart your ownaopinion such as "that's a great idea" or "x is an intresting topic". Do not close with phrases like “good luck” or “enjoy” as this converstaion is ongoing.     
    (Start Chat History)
    {chat_history}
    (End Chat History)
    Human: {human_input}
    """
    # Create the prompt and memory
    prompt = PromptTemplate(input_variables=["chat_history", "human_input"], template=template)
    memory = ConversationBufferMemory(memory_key='chat_history')
    memory.chat_memory.add_user_message(chat_history)
    # Create the LLMChain
    llm_chain = LLMChain(llm=ChatOpenAI(openai_api_key= openai_api_key, temperature=0.3, model="gpt-3.5-turbo-16k"), prompt=prompt, memory=memory, verbose=True)
    # Process the chat entry
    response = llm_chain.predict(human_input=chat_entry)
    return response


def build_primer(chat_history, chat_entry):
    openai_api_key = get_api_key()
    # Define the prompt template
    template = """You are going to be given a chat history for a single user.   
    (Start Chat History)
    {chat_history}
    (End Chat History)
    Human: {human_input} Please review the data and build a "primer" for the user. We are looking for facts, likes, dislikes, political leanings, and personality traits. Important details should be retained, but small details are not as relevant. You should not return a list of facts but more a paragraph or two about the person and what they have talked about.
    """

    prompt = PromptTemplate(input_variables=["chat_history", "human_input"], template=template)
    memory = ConversationBufferMemory(memory_key='chat_history', max_token_limit=15000)
    # Split the chat history into chunks
    chat_chunks = chunkify(chat_history)

    # Process each chunk and combine the responses
    combined_response = ""
    for chunk in chat_chunks:
        memory.chat_memory.add_user_message(chunk)
        llm_chain = LLMChain(llm=ChatOpenAI(openai_api_key=openai_api_key, temperature=0.3, model="gpt-3.5-turbo-16k"), prompt=prompt, memory=memory, verbose=True)
        response = llm_chain.predict(human_input=chat_entry)
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