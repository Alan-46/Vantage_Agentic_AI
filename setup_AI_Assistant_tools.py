from playwright.async_api import async_playwright
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
from dotenv import load_dotenv
import os
import requests
from langchain.tools import tool
# from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
# from langchain_experimental.tools import PythonREPLTool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper

from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings

from datetime import datetime
from zoneinfo import ZoneInfo


load_dotenv(override=True)


ntfy_url = os.getenv("NTFY_URL")
serper = GoogleSerperAPIWrapper()


@tool
def get_current_time_for_timezone(timezone_name: str = "Asia/Kolkata") -> str:
    """
        Useful when you need to check the current date and time for a specific time zone or city.
        Always use this tool if the user asks about live events, sports match schedules, 
        or local event timings in specific countries (e.g., 'Asia/Tokyo', 'America/New_York', 'UTC').
        Pass a valid IANA timezone string (like 'Asia/Kolkata', 'Asia/Tokyo', 'Europe/London').
    """

    try:
        # Fetch localized time cleanly using standard zoneinfo
        tz = ZoneInfo(timezone_name)
        localized_time = datetime.now(tz)
        return localized_time.strftime(f"The current time in {timezone_name} is: %Y-%m-%d %H:%M:%S (%Z %z)")
    except Exception as e:
        return f"Error fetching time for zone '{timezone_name}': {str(e)}. Please check the timezone string naming format."


@tool
def push_tool_def(text: str):
    """ Used to send a push notification to the user. """

    response = requests.post(
        ntfy_url,
        data = text.encode('utf-8')
    )
    if response.status_code == 200:
        return {"message": "Notification sent successfully!"}
    else:
        return {"message": f"Failed to send: {response.status_code}"}


# def file_tools_def():
#     toolkit = FileManagementToolkit(root_dir="sandbox")
#     return toolkit.get_tools()


@tool
def search_tool_def(query: str):
    """ Used to search the internet. """

    result = serper.run(query)
    return result

@tool
def rag_tool_def(query: str):
    """ Used to retrieve company-related information and context on InsureLLM """

    INDEX_NAME = "vantage-index"

    ### Connect to Chroma
    embeddings = HuggingFaceEmbeddings(model_name="nomic-ai/nomic-embed-text-v1.5")
    vectorstore = PineconeVectorStore(index_name=INDEX_NAME, embedding=embeddings)

    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    docs = retriever.invoke(query)
    context = "\n\n".join(doc.page_content for doc in docs)

    return context


async def playwright_tools():
    playwright = await async_playwright().start()
    is_prod = os.getenv("HF_TOKEN") is not None
    browser = await playwright.chromium.launch(headless=is_prod)
    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)
    return toolkit.get_tools(), browser, playwright


async def other_tools():
    push_tool = push_tool_def # no using () as the @tool decorator StructuredTool object which can be called normally
    # file_tools = file_tools_def()
    search_tool = search_tool_def # no using () as the @tool decorator StructuredTool object which can be called normally
    rag_tool = rag_tool_def
    current_time_tool = get_current_time_for_timezone

    wikipedia = WikipediaAPIWrapper()
    wiki_tool = WikipediaQueryRun(api_wrapper=wikipedia)
    # python_repl = PythonREPLTool()
    
    # return file_tools + [push_tool, search_tool, python_repl,  wiki_tool]
    return [current_time_tool, push_tool, search_tool, rag_tool, wiki_tool]