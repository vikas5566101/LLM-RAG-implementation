import os
import shutil
from fastapi import File, UploadFile
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

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

# for database
from fastapi import Depends
from sqlalchemy.orm import Session
from database import get_db, ChatSession, ChatMessage,SessionLocal
import uuid

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
llm = ChatOllama(
    base_url="http://host.docker.internal:11434", 
    model="llama3.2", 
    temperature=0
)

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
- NEVER guess theory. You MUST use the search tool.
- The calculator input MUST be raw, executable Python code.
- NEVER ask the user for permission. NEVER ask follow-up questions.
"""

# 6. Build the Agent Executor 
agent_executor = create_react_agent(llm, tools)

# 7. Define the API Input Format
class Query(BaseModel):
    question: str
    session_id: str # NEW: We just need the session ID now!

def format_db_history(db_messages):
    messages = []
    for msg in db_messages:
        if msg.role == "ai":
            messages.append(AIMessage(content=msg.content))
        else:
            messages.append(HumanMessage(content=msg.content))
    return messages

# --- NEW: DATABASE ENDPOINTS ---

@app.post("/sessions")
def create_session(db: Session = Depends(get_db)):
    """Creates a new empty chat session"""
    new_session = ChatSession(title="New Engineering Chat")
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return {"session_id": new_session.id, "title": new_session.title}

@app.get("/sessions")
def get_all_sessions(db: Session = Depends(get_db)):
    """Gets a list of all chat sessions for the UI Sidebar"""
    sessions = db.query(ChatSession).order_by(ChatSession.created_at.desc()).all()
    return [{"session_id": s.id, "title": s.title, "created_at": s.created_at} for s in sessions]

@app.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    """Gets the chat history for a specific session"""
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp.asc()).all()
    return [{"role": m.role, "content": m.content} for m in messages]

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Deletes a chat session and all its associated messages"""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    
    if not session:
        return {"status": "error", "message": "Session not found"}
        
    db.delete(session)
    db.commit()
    
    return {"status": "success", "message": "Session deleted"}

# --- DYNAMIC PDF UPLOAD ENDPOINT (Unchanged) ---
@app.post("/upload")
async def upload_manual(file: UploadFile = File(...)):
    # ... (Keep your exact upload_manual code here) ...
    print(f"\nIncoming File: {file.filename}")
    temp_file_path = f"temp_{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = text_splitter.split_documents(documents)
        vector_db.add_documents(chunks)
        print(f"Successfully injected {len(chunks)} chunks into the database.")
        return {"filename": file.filename, "status": "success", "message": f"Learned {len(chunks)} new pages of data."}
    except Exception as e:
        print(f"Failed to process PDF: {e}")
        return {"filename": file.filename, "status": "error", "message": str(e)}
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


# 8. Create the API Endpoint
@app.post("/ask")
async def ask_engineer(query: Query, db: Session = Depends(get_db)):
    print(f"\nIncoming Question: {query.question} for Session: {query.session_id}")
    
    # 1. Save the User's message to the Database instantly
    user_msg = ChatMessage(session_id=query.session_id, role="user", content=query.question)
    db.add(user_msg)
    db.commit()
    
    # 2. Fetch past history for this session from the Database
    db_history = db.query(ChatMessage).filter(ChatMessage.session_id == query.session_id).order_by(ChatMessage.timestamp.asc()).all()
    
    async def generate_response():
        # Build the LLM Context
        messages = [SystemMessage(content=system_prompt)]
        messages.extend(format_db_history(db_history)) # This now includes the question we just saved
        
        full_ai_response = "" # We need this string to save the final answer to the DB
        
        try:
            async for chunk in agent_executor.astream({"messages": messages}):
                if "agent" in chunk:
                    agent_msg = chunk["agent"]["messages"][-1]
                    
                    if hasattr(agent_msg, 'tool_calls') and agent_msg.tool_calls:
                        for tool_call in agent_msg.tool_calls:
                            args_str = json.dumps(tool_call['args'])
                            yield f"__TOOL_USE__:{tool_call['name']}|{args_str}:::"
                            
                    elif agent_msg.content and '{"name":' in agent_msg.content:
                        try:
                            json_str = agent_msg.content[agent_msg.content.find("{"):agent_msg.content.rfind("}")+1]
                            tool_data = json.loads(json_str)
                            tool_name = tool_data.get("name")
                            
                            if tool_name == "search_engineering_manuals":
                                search_query = tool_data["parameters"]["query"]
                                yield f"__TOOL_USE__:search_engineering_manuals|{json.dumps({'query': search_query})}:::"
                                
                                result = search_engineering_manuals.invoke({"query": search_query})
                                yield f"__TOOL_RESULT__:{result}:::"
                                
                                follow_up = f"System: The search tool returned this excerpt:\n\n{result}\n\nSummarize this to answer the user directly. Do not use JSON."
                                messages.append(AIMessage(content=agent_msg.content))
                                messages.append(HumanMessage(content=follow_up))
                                
                                async for final_chunk in llm.astream(messages):
                                    full_ai_response += final_chunk.content # Catch the text
                                    yield final_chunk.content

                            elif tool_name == "python_calculator":
                                python_code = tool_data["parameters"].get("query", "")
                                if not python_code:
                                    python_code = next(iter(tool_data["parameters"].values()), "")
                                    
                                yield f"__TOOL_USE__:python_calculator|{json.dumps({'status': 'Executing Math...'})}:::"
                                
                                result = python_calculator.invoke(python_code)
                                yield f"__TOOL_RESULT__:{result}:::"
                                
                                follow_up = f"System: The python calculator returned this result:\n{result}\n\nState this answer clearly to the user. Do not use JSON."
                                messages.append(AIMessage(content=agent_msg.content))
                                messages.append(HumanMessage(content=follow_up))
                                
                                async for final_chunk in llm.astream(messages):
                                    full_ai_response += final_chunk.content # Catch the text
                                    yield final_chunk.content
                                
                        except Exception as e:
                            print(f"Failed to parse manual tool call: {e}")
                            full_ai_response += agent_msg.content
                            yield agent_msg.content 
                            
                    elif agent_msg.content:
                        full_ai_response += agent_msg.content # Catch standard text
                        yield agent_msg.content
                        
                elif "tools" in chunk:
                    tool_msg = chunk["tools"]["messages"][-1]
                    yield f"__TOOL_RESULT__:{tool_msg.content}:::"
                    
        except Exception as e:
            error_msg = f"Agent Error: {str(e)}"
            full_ai_response += error_msg
            yield error_msg
            
        finally:
            # 3. SAVE THE AI'S ANSWER TO THE DATABASE ONCE FINISHED
            if full_ai_response:
                # We need a new DB session since the generator context can get detached
                save_db = SessionLocal()
                ai_db_msg = ChatMessage(session_id=query.session_id, role="ai", content=full_ai_response)
                save_db.add(ai_db_msg)
                save_db.commit()
                save_db.close()
            
    return StreamingResponse(generate_response(), media_type="text/plain")