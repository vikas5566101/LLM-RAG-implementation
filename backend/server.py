from typing import List, Dict
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_experimental.tools import PythonREPLTool

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage 

# 1. Initialize the App
app = FastAPI(title="LangGraph Process Engineer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Connect to the Local Knowledge Base
print("Loading Vector Database...")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_db = Chroma(
    persist_directory="./chroma_db", 
    embedding_function=embeddings
)
retriever = vector_db.as_retriever(search_kwargs={"k": 5})

# 3. Connect to Llama 3.2
print("Connecting to Llama 3.2 Agent Engine...")
llm = ChatOllama(model="llama3.2", temperature=0)

# 4. Give the AI its Tools

@tool
def search_engineering_manuals(query: str) -> str:
    """MANDATORY TOOL for any questions about guidelines, safety, OISD, API, or theory. 
    You have NO internal knowledge of these topics. You MUST use this tool to search for the answer before speaking.
    Input must be a single search string."""
    
    print(f"Searching DB for: {query}")
    
    # Query the vector database
    docs = retriever.invoke(query)
    
    # Format the raw Document objects into a single readable string
    if not docs:
        return "No relevant information found in the manuals."
    
    return "\n\n".join([f"--- Excerpt ---\n{doc.page_content}" for doc in docs])

# Initialize the Python Calculator tool
python_calculator = PythonREPLTool(
    name="python_calculator",
    description="Execute Python code for exact math. INPUT MUST BE VALID PYTHON CODE ONLY. NO ENGLISH WORDS. You must use print() to output the final result so you can read it."
)

# Define the tools array for LangGraph
tools = [search_engineering_manuals, python_calculator]

# 5. Define System Prompt
system_prompt = """You are a Senior Digital Process Engineer. 
You have NO internal memory of engineering standards. You cannot answer theory questions from your own head.

You have two tools:
1. search_engineering_manuals: MANDATORY for factual text, safety codes, and theory.
2. python_calculator: MANDATORY for exact math.

CRITICAL RULES:
- NEVER guess math. You MUST use the python_calculator.
- The calculator input MUST be raw, executable Python code (e.g., print(2**3)).
- NEVER guess engineering guidelines, rules, or theory. You MUST use the search_engineering_manuals tool.

EXAMPLE WORKFLOW (Math):
User: How much heat to raise 200g of liquid from 10C to 50C? (c=2.0)
Thought: I need to calculate Delta T first, then use q = mc(Delta T).
Tool Call: python_calculator -> print((200 * 2.0 * 40) / 1000)

EXAMPLE WORKFLOW (Theory/Guidelines):
User: What is the safety spacing between a fired heater and a storage tank?
Thought: I have no internal knowledge of this. I MUST use the search tool.
Tool Call: search_engineering_manuals -> "fired heater storage tank safety spacing guidelines"
"""

# 6. Build the Agent Executor (Removed state_modifier to fix your version error)
agent_executor = create_react_agent(llm, tools)

# 7. Define the API Input Format
class Query(BaseModel):
    question: str
    chat_history: List[Dict[str, str]] = []

def format_history(history_list):
    messages = []
    for msg in history_list:
        if msg["role"] == "ai":
            messages.append(AIMessage(content=msg["content"]))
        else:
            messages.append(HumanMessage(content=msg["content"]))
    return messages

# 8. Create the API Endpoint
@app.post("/ask")
async def ask_engineer(query: Query):
    print(f"\nIncoming Question: {query.question}")
    
    async def generate_response():
        # Inject the System Prompt
        messages = [SystemMessage(content=system_prompt)]
        messages.extend(format_history(query.chat_history))
        messages.append(HumanMessage(content=query.question))
        
        try:
            # We use astream() to catch every step the agent takes
            async for chunk in agent_executor.astream({"messages": messages}):
                
                if "agent" in chunk:
                    agent_msg = chunk["agent"]["messages"][-1]
                    
                    # 1. Check for standard LangGraph Tool Calls
                    if hasattr(agent_msg, 'tool_calls') and agent_msg.tool_calls:
                        for tool_call in agent_msg.tool_calls:
                            args_str = json.dumps(tool_call['args'])
                            yield f"__TOOL_USE__:{tool_call['name']}|{args_str}:::"
                            
                    # 2. Check for Llama 3.2 "Raw JSON" Tool Calls (The Custom Router)
                    elif agent_msg.content and '{"name": "search_engineering_manuals"' in agent_msg.content:
                        try:
                            # Extract the JSON string from the AI's text
                            json_str = agent_msg.content[agent_msg.content.find("{"):agent_msg.content.rfind("}")+1]
                            tool_data = json.loads(json_str)
                            
                            # Run the tool manually
                            search_query = tool_data["parameters"]["query"]
                            yield f"__TOOL_USE__:search_engineering_manuals|{json.dumps({'query': search_query})}:::"
                            
                            # Execute search and send result to UI Sidebar
                            result = search_engineering_manuals.invoke({"query": search_query})
                            yield f"__TOOL_RESULT__:{result}:::"
                            
                            # --- NEW: FORCE THE AI TO SUMMARIZE THE RESULT ---
                            follow_up = f"System: The search tool returned this excerpt from the manual:\n\n{result}\n\nPlease summarize this information to answer the user's question directly. Do not use JSON."
                            messages.append(AIMessage(content=agent_msg.content))
                            messages.append(HumanMessage(content=follow_up))
                            
                            # Stream the final synthesized text to the Main Chat
                            async for final_chunk in llm.astream(messages):
                                yield final_chunk.content
                                
                        except Exception as e:
                            print(f"Failed to parse manual tool call: {e}")
                            yield agent_msg.content 
                            
                    elif agent_msg.content:
                        # Send standard text answer
                        yield agent_msg.content
                        
                elif "tools" in chunk:
                    tool_msg = chunk["tools"]["messages"][-1]
                    yield f"__TOOL_RESULT__:{tool_msg.content}:::"
                    
        except Exception as e:
            yield f"Agent Error: {str(e)}"
            
    return StreamingResponse(generate_response(), media_type="text/plain")