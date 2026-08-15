from langchain_ollama import ChatOllama
import os
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from typing import Annotated, List, Any, Dict, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
# from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import ToolNode
from datetime import datetime
from zoneinfo import ZoneInfo

import uuid  # <--- Added for multi-session UUID tracking
from pymongo import MongoClient  # <--- Added for MongoDB connectivity
from langgraph.checkpoint.mongodb import MongoDBSaver  # <--- Added MongoDBSaver Checkpointer


from setup_AI_Assistant_tools import playwright_tools, other_tools


class graph_state(TypedDict):
    messages: Annotated[List[Any], add_messages]
    success_criteria: str
    feedback_on_work: Optional[str]
    success_criteria_met: bool
    user_input_needed: bool

class evaluator_output(BaseModel):
    feedback: str = Field(description="Feedback on the Assistant's response to the user's query.")
    success_criteria_met: bool = Field(description="Set this to True if the success criteris has been met and False if not.")
    user_input_needed: bool = Field(description="Set this to True if you think more user input is needed for the Assistant to respond and False if not.")

class GraphWorkflow:
    def __init__(self):
        self.graph_template = None
        self.graph = None
        self.memory = MemorySaver()
        self.checkpointer = None
        self.worker_llm_withoutTools = ChatOllama(model="gemma4:31b-cloud")
        self.evaluator_llm_withoutStructuredOutput = ChatOllama(model="gemma4:31b-cloud")
        
        self.client = None  # <--- Track the connection client to handle clean tear-downs
        
        # Generates an isolated session timeline string automatically on page load
        self.thread_id = str(uuid.uuid4())
    
    async def setup(self):
        self.tools, self.browser, self.playwright = await playwright_tools()
        self.tools += await other_tools()
        self.worker_llm = self.worker_llm_withoutTools.bind_tools(self.tools)

        self.evaluator_llm = self.evaluator_llm_withoutStructuredOutput.with_structured_output(evaluator_output)

        # 1. Fetch your cloud database URI from environment variables
        mongo_uri = os.getenv("MONGODB_URI")
        if not mongo_uri:
            raise ValueError("MONGODB_URI environment variable is missing. Set it in your local .env or HF Space Settings.")

        # 2. Establish connection pool with MongoDB Atlas cloud clusters
        self.client = MongoClient(mongo_uri)
        
        # 3. Create the persistence checkpointer wrapper
        self.checkpointer = MongoDBSaver(self.client)
        await self.build_graph()
            
    def worker_node(self, graph_state: graph_state) -> Dict[str, Any]:

        user_local_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S %Z")
        system_message = f"""
            Today's base user date and time is: {user_local_time}.

            You are a professional stateful assistant. 

            CRITICAL TIME REASONING RULES:
            1. The baseline time provided above is your primary reference point for user-centric queries (like local matches, schedules, or calendars).
            2. If the user asks about live events, television broadcasts, or local happenings in another country (e.g., Japan, UK, USA), do NOT guess
            or compute time arithmetic mentally. You MUST call the `get_current_time_for_timezone` tool with the corresponding timezone (e.g., 'Asia/Tokyo' for Japan)
            to pull the exact localized structural time before answering.

            You are a helpful assistant who works on making the user's life easier by fulfilling their requests and completing their tasks.
            
            You keep working on a task until either you have a question or clarification for the user, or the success criteria is met.
            You have many tools to help you, including tools to browse the internet, navigating and retrieving web pages.

            Additionally, you have privileged access to company-related information and context on InsureLLM. So you can use the tool to get
            relevant context on the company when the user asks about it as it is not publicly available.

            You should reply either with a question for the user about this assignment, or with your final response.
            If you have a question for the user, you need to reply by clearly stating your question. An example might be:

            Question: please clarify whether you want a summary or a detailed answer

            If you've finished, reply with the final answer, and don't ask a question; simply reply with the answer.

            IMPORTANT NOTE: your knowledge was cut-off a while back. So whenever the user has a query, be aware that you will not know the current date's
            updated answer to the query. Hence, you will have to search the internet using the tools provided to you to answer accurately if the query 
            is about facts, news, etc. Logical questions can be answered without searching too but that depends on your judgement.
            DO NOT assume the answer.
        """

        messages = graph_state["messages"]
        messages = [SystemMessage(content=system_message)] + messages

        response = {
            "messages": self.worker_llm.invoke(messages), # this invoke statement returns an AIMessage object and content field contains its actual response
        }
        return response

    def format_conversation(self, messages: List[Any]) -> str:
        conversation_history = "Conversation history: \n\n"

        for x in messages:
            if isinstance(x,HumanMessage):
                conversation_history += f"\nUser: \n{x.content}\n\n"
            elif isinstance(x,AIMessage):
                text = x.content or "[Tool use]"
                conversation_history += f"\nAI Assistant: \n{text}\n\n"

        return conversation_history

    def evaluator_node(self, graph_state: graph_state) -> Dict[str,Any]:
        
        user_local_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S %Z")
        system_message = f"""
        Today's date and time is: {user_local_time}.

        You are an evaluator that determines if a task has been completed successfully by an Assistant.
        Assess the Assistant's last response based on the given criteria. Respond with your feedback, and with your decision on whether the success criteria has been met,
        and whether more input is needed from the user.

        You are supposed to repond strictly in the following output format in JSON. No filler text or comments. No thinking comments. Nothing else. Just your response in this 
        JSON format so that it can be fed into a class object:

            feedback: str = Field(description="Feedback on the assistant's response")
            success_criteria_met: bool = Field(description="Whether the success criteria have been met")
            user_input_needed: bool = Field(
                description="True if more input is needed from the user, or clarifications, or the assistant is stuck"
            )

        IMPORTANT NOTE: your knowledge was cut-off a while back. So whenever the user has a query, be aware that the Assistant will not know the current date's
        updated answer to the query and it will have to search the internet using the tools provided to it and give the appropriate answer.

        ADDITIONAL NOTE: The Assistant has the following time reasoning skills to better assist the user. So consider this and think before evaluating the Assistant's response
        if you feel it is hallucinating about the time.

        CRITICAL TIME REASONING RULES of the Assistant:
            1. The baseline time provided is the primary reference point for user-centric queries (like local matches, schedules, or calendars).
            2. If the user asks about live events, television broadcasts, or local happenings in another country (e.g., Japan, UK, USA), do NOT guess
            or compute time arithmetic mentally. You MUST call the `get_current_time_for_timezone` tool with the corresponding timezone (e.g., 'Asia/Tokyo' for Japan)
            to pull the exact localized structural time before answering.
        """

        user_message = f"""You are evaluating a conversation between the User and Assistant. You decide what action to take based on the last response from the Assistant.

            The entire conversation with the assistant, with the user's original request and all replies, is:
            {self.format_conversation(graph_state["messages"])}

            The success criteria for this assignment is:
            {graph_state["success_criteria"]}

            And the final response from the Assistant that you are evaluating is:
            {graph_state["messages"][-1].content}

            Respond with your feedback, and decide if the success criteria is met by this response.
            Also, decide if more user input is required, either because the assistant has a question, needs clarification, or seems to be stuck and unable to answer without help.

            NOTE: You strictly reply only in JSON format without any thinking blocks or text before or after the json block. No conversation fillers either.
            The json block provided to you with information populated by you is the only information you reply.

            This is the output format:
            
                feedback: str = Field(description="Feedback on the assistant's response")
                success_criteria_met: bool = Field(description="Whether the success criteria have been met")
                user_input_needed: bool = Field(
                    description="True if more input is needed from the user, or clarifications, or the assistant is stuck"
                )

            The Assistant has access to a tool to write files. If the Assistant says they have written a file, then you can assume they have done so.
            Overall you should give the Assistant the benefit of the doubt if they say they've done something. But you should reject if you feel that more work should go into this.
        """

        if graph_state["feedback_on_work"]:
            user_message += f"\nAlso, note that in a prior attempt from the Assistant, you provided this feedback: {graph_state["feedback_on_work"]}\n"
            user_message += "If you're seeing the Assistant repeating the same mistakes, then consider responding that user input is required."

        messages = [SystemMessage(content=system_message), HumanMessage(content=user_message)]

        response = self.evaluator_llm.invoke(messages)

        new_state = {
            "messages": [{
                    "role": "assistant",
                    "content": f"Evaluator Feedback on this answer: {response.feedback}",
            }],
            "feedback_on_work": response.feedback,
            "success_criteria_met": response.success_criteria_met,
            "user_input_needed": response.user_input_needed,
        }

        return new_state
    
    def route_based_on_worker_output(self, graph_state: graph_state) -> str:
        response = graph_state["messages"][-1]

        if isinstance(response,AIMessage) and response.tool_calls:
            return "tool"
        else:
            return "evaluator"

    def route_based_on_evaluation(self, graph_state: graph_state) -> str:
        if graph_state.get("success_criteria_met") == True or graph_state.get("user_input_needed") == True:
            return "end"
        elif graph_state.get("success_criteria_met") == False:
            return "worker"

    async def build_graph(self):
        graph_builder = StateGraph(graph_state)
        graph_builder.add_node("Worker Node", self.worker_node)
        graph_builder.add_node("Evaluator Node", self.evaluator_node)
        graph_builder.add_node("Tool Node",ToolNode(self.tools))

        graph_builder.add_edge(START, "Worker Node")
        graph_builder.add_conditional_edges("Worker Node", self.route_based_on_worker_output, {"tool":"Tool Node","evaluator":"Evaluator Node"})
        graph_builder.add_edge("Tool Node","Worker Node")
        graph_builder.add_conditional_edges("Evaluator Node",self.route_based_on_evaluation, {"worker":"Worker Node","end":END})


        self.graph = graph_builder.compile(checkpointer=self.checkpointer)
        # self.graph = graph_builder.compile(checkpointer=self.checkpointer)
        
        # GENERATE GRAPH IMAGE

        # with open("graph.png", "wb") as f:
        #     f.write(self.graph.get_graph().draw_mermaid_png())

        # print("Graph saved as graph.png")

    async def run_superstep(self, message, history):
        config = {"configurable": {"thread_id": self.thread_id}}
        initial_state = {
            "messages": {"role":"user","content": message},
            "success_criteria": "The answer should be accurate, complete and the answer that the user must be looking for, for the query.",
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False,
        }
        result = await self.graph.ainvoke(initial_state, config=config)
        return history + [{"role":"user","content": message}] + [{"role":"assistant", "content": result["messages"][-2].content}]
    
    async def cleanup(self):
        """
        Closes the browser and stops Playwright gracefully.
        """
        try:
            if self.browser:
                await self.browser.close()
                print("Browser closed.")
            
            if self.playwright:
                await self.playwright.stop()
                print("Playwright service stopped.")
                
        except Exception as e:
            print(f"Error during playwright cleanup: {e}")
        
        finally:
            self.browser = None
            self.playwright = None