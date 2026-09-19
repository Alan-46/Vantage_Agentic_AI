from dotenv import load_dotenv
load_dotenv(override=True)


from langchain_ollama import ChatOllama
from ragas.llms import LangchainLLMWrapper

eval_llm = LangchainLLMWrapper(ChatOllama(model="gemma4-31b:cloud"))