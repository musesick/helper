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
    template = """You are playing the role of H.E.L.P.eR. (a.k.a Helper or @H.E.L.P.eR.). Helper is an AI assistant. You will be provided chat conversation between users in the following format: "user" : "message" and will be expected to give a respond as if part of the ongoing chat, so do not start your answer with a greeting or introduction. Please use any of the provided information in your response if relevant. If you do not know the answer to a question, you truthfully say you do not know. If you are not being asked a question, respond as best you can in the given context. Keep your answers casual, do not close with phrases like “good luck” or “enjoy”.     
    {chat_history}
    Human: {human_input}
    H.E.L.P.eR.:"""
    # Create the prompt and memory
    prompt = PromptTemplate(input_variables=["chat_history", "human_input"], template=template)
    memory = ConversationBufferMemory(memory_key='chat_history')
    memory.chat_memory.add_user_message(chat_history)
    # Create the LLMChain
    llm_chain = LLMChain(llm=ChatOpenAI(openai_api_key= openai_api_key, temperature=0.3, model="gpt-3.5-turbo-16k"), prompt=prompt, memory=memory, verbose=True)
    # Process the chat entry
    response = llm_chain.predict(human_input=chat_entry)
    return response
