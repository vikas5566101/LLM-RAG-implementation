from typing import List, Dict
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_ollama import ChatOllama
from langchain_core.tools import Tool
from langchain_experimental.tools import PythonREPLTool

from langgraph.prebuilt import create_react_agent
# NEW: Imported SystemMessage
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
retriever_tool = Tool(
    name="search_engineering_manuals",
    description="Search for safety rules, spacing guidelines, and engineering text.",
    func=retriever.invoke
)

# 4. Give the AI its Tools
python_tool = PythonREPLTool(
    name="python_calculator",
    description="Execute Python code. INPUT MUST BE VALID PYTHON CODE ONLY. NO ENGLISH WORDS. You must use print() to output the final result so you can read it."
)

tools = [retriever_tool, python_tool]

# 5. Define System Prompt
# 5. Define System Prompt
# 5. Define System Prompt
system_prompt = """You are a Senior Digital Process Engineer. 
You have two tools:
1. search_engineering_manuals: For factual text.
2. python_calculator: For exact math.

CRITICAL RULES FOR MATH:
- NEVER guess math.
- You MUST use the python_calculator.
- The input to the calculator MUST be raw, executable Python code.
- Example valid input: print((2.5 * 0.4) / 1.004e-6)
- Example INVALID input: Calculate the reynolds number..."""

# 6. Build the Agent Executor (No contested variables!)
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
        # INJECT THE SYSTEM PROMPT HERE AS A MESSAGE
        messages = [SystemMessage(content=system_prompt)]
        
        # Add the rest of the conversation history
        messages.extend(format_history(query.chat_history))
        messages.append(HumanMessage(content=query.question))
        
        try:
            # Run the LangGraph agent
            result = await agent_executor.ainvoke({"messages": messages})
            
            # Yield the final AI message back to the frontend
            yield result["messages"][-1].content
            
        except Exception as e:
            yield f"Agent Error: {str(e)}"
            
    return StreamingResponse(generate_response(), media_type="text/plain")