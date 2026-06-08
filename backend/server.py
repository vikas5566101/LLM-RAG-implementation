import os
import shutil
import json
import uuid
from typing import List, Dict

# --- FastAPI Core & Security ---
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

# --- Database & Authentication ---
from sqlalchemy.orm import Session
from database import get_db, ChatSession, ChatMessage, SessionLocal, User
from auth import get_current_user, create_access_token, get_password_hash, verify_password

# --- LangChain & AI Agents ---
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_experimental.tools import PythonREPLTool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

# 1. Initialize the App
app = FastAPI(title="LangGraph Process Engineer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserCreate(BaseModel):
    username: str
    password: str

@app.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # Check if username exists
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Hash password and save
    hashed_pw = get_password_hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()
    return {"status": "success", "message": "User created successfully"}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    # Generate the JWT Badge
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# 2. Connect to the Local Knowledge Base
print("Loading Vector Database...")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_db = Chroma(
    persist_directory="./chroma_db", 
    embedding_function=embeddings
)
retriever = vector_db.as_retriever(search_kwargs={"k": 3})

# 3. Connect to Llama 3.2
print("Connecting to Llama 3.2 Agent Engine...")
llm = ChatOllama(
    base_url="http://host.docker.internal:11434", 
    model="llama3.2", 
    temperature=0
)

# 4. Give the AI its Tools

@tool
def search_engineering_manuals(query: str, config: RunnableConfig) -> str:
    """MANDATORY TOOL for questions about guidelines, safety, codes, or theory. 
    You MUST use this tool to search the database. 
    The argument MUST be passed using the 'query' parameter key.
    CRITICAL: The 'query' MUST be 2 to 4 highly dense keywords, NOT full sentences. 
    (Example: Use 'flutter chatter difference' instead of 'What is the difference between flutter and chatter?')"""
    
    active_user = config.get("configurable", {}).get("user_id")
    print(f"Searching DB for: '{query}' (Secured to User: {active_user})")
    
    docs = vector_db.similarity_search(
        query, 
        k=3, # <-- Let's bump this to 5 so it has a slightly wider net to catch the answer
        filter={"user_id": active_user}
    )
    
    if not docs:
        return "No relevant information found in the manuals."
    
    return "\n\n".join([f"--- Excerpt ---\n{doc.page_content}" for doc in docs])

# Initialize the Python Calculator tool
python_calculator = PythonREPLTool(
    name="python_calculator",
    description="Execute Python code for exact math. The argument MUST be passed using the 'query' parameter key. INPUT MUST BE VALID PYTHON CODE ONLY."
)

@tool
def engineering_unit_converter(query: str) -> str:
    """MANDATORY TOOL for converting process engineering and energy units.
    The argument MUST be passed using the 'query' parameter key.
    Format the query EXACTLY as a comma-separated string: "VALUE,FROM_UNIT,TO_UNIT" 
    Example 1: "450,psi,bar"
    Example 2: "100,celsius,fahrenheit"
    Example 3: "50,kw,hp"
    Supported Pressure: psi, bar, atm, pa, kpa. 
    Supported Temperature: celsius, fahrenheit, kelvin.
    Supported Power: kw, mw, hp, w.
    """
    try:
        parts = [p.strip().lower() for p in query.split(',')]
        if len(parts) != 3:
            return "Error: Query must be exactly 'VALUE,FROM_UNIT,TO_UNIT'."
        
        value = float(parts[0])
        from_unit = parts[1]
        to_unit = parts[2]
        
        # --- Temperature Conversions ---
        if from_unit in ['celsius', 'c'] and to_unit in ['fahrenheit', 'f']:
            return f"{value} Celsius = {(value * 9/5) + 32:.2f} Fahrenheit"
        elif from_unit in ['fahrenheit', 'f'] and to_unit in ['celsius', 'c']:
            return f"{value} Fahrenheit = {(value - 32) * 5/9:.2f} Celsius"
        elif from_unit in ['celsius', 'c'] and to_unit in ['kelvin', 'k']:
            return f"{value} Celsius = {value + 273.15:.2f} Kelvin"
            
        # --- Pressure Conversions (Base: 1 atm) ---
        pressure_to_atm = {'atm': 1.0, 'psi': 14.6959, 'bar': 1.01325, 'pa': 101325, 'kpa': 101.325}
        if from_unit in pressure_to_atm and to_unit in pressure_to_atm:
            atm_val = value / pressure_to_atm[from_unit]
            result = atm_val * pressure_to_atm[to_unit]
            return f"{value} {from_unit.upper()} = {result:.4f} {to_unit.upper()}"
            
        # --- Power Conversions (Base: 1 Watt) ---
        power_to_watts = {'w': 1.0, 'kw': 1000.0, 'mw': 1000000.0, 'hp': 745.7}
        if from_unit in power_to_watts and to_unit in power_to_watts:
            watt_val = value * power_to_watts[from_unit]
            result = watt_val / power_to_watts[to_unit]
            return f"{value} {from_unit.upper()} = {result:.4f} {to_unit.upper()}"
            
        return f"Error: Conversion from {from_unit} to {to_unit} is not supported."
    except ValueError:
        return "Error: The VALUE must be a valid number."
    except Exception as e:
        return f"Error executing conversion: {str(e)}"

# Define the tools array for LangGraph
tools = [search_engineering_manuals, python_calculator, engineering_unit_converter]



# 5. Define System Prompt
system_prompt = """You are a Senior Digital Process Engineer. 
You have NO internal memory of engineering standards. You cannot answer theory questions from your own head.

You have two tools:
1. search_engineering_manuals: Use this to search PDFs for theory and text.
2. engineering_unit_converter: Use this to convert Pressure, Temperature, or Power units.
3. python_calculator: Use this ONLY for doing math equations.

CRITICAL RULES:
- NEVER guess math. You MUST use the python_calculator.
- NEVER guess theory. You MUST use the search tool.
- NEVER guess unit conversions. You MUST use the engineering_unit_converter tool.
- The calculator input MUST be raw, executable Python code.
- NEVER ask the user for permission. NEVER ask follow-up questions.
- TOOL FORMATTING: When calling ANY tool, the argument key MUST be exactly "query". NEVER use the word "input".
  Example: {"name": "python_calculator", "parameters": {"query": "250 * 4.5"}}
- FINAL ANSWER FORMATTING: When speaking to the user, you MUST use plain, professional English. NEVER output JSON, dictionaries, or raw tool-call formats.
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
def create_session(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Creates a new session locked to the active user"""
    new_session = ChatSession(user_id=current_user.id) # Linked to user
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return {"session_id": new_session.id}

@app.get("/sessions")
def get_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetches ONLY the sessions owned by the active user"""
    sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).order_by(ChatSession.created_at.desc()).all()
    return [{"session_id": s.id, "title": s.title} for s in sessions]

@app.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Validates ownership before returning messages"""
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")
        
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.timestamp.asc()).all()
    return [{"role": m.role, "content": m.content} for m in messages]

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Validates ownership before deleting"""
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")
        
    db.delete(session)
    db.commit()
    return {"status": "success", "message": "Session deleted"}

# --- DYNAMIC PDF UPLOAD ENDPOINT (Unchanged) ---
@app.post("/upload")
async def upload_document(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    print(f"\nIncoming File: {file.filename} (Uploaded by: {current_user.username})")
    temp_file_path = f"temp_{file.filename}"
    
    # 1. Save the file temporarily
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # 2. Parse and split the PDF
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)
        chunks = text_splitter.split_documents(documents)
        
        # 3. --- NEW SECURITY LOGIC ---
        # Stamp every single chunk with the active user's ID
        for chunk in chunks:
            chunk.metadata["user_id"] = current_user.id 
            
        # 4. Save to ChromaDB
        vector_db.add_documents(chunks)
        print(f"Successfully injected {len(chunks)} chunks into the database securely.")
        
        return {
            "filename": file.filename, 
            "status": "success", 
            "message": f"Document securely memorized ({len(chunks)} chunks)."
        }
        
    except Exception as e:
        print(f"Failed to process PDF: {e}")
        return {"filename": file.filename, "status": "error", "message": str(e)}
        
    finally:
        # 5. Clean up the temp file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# 8. Create the API Endpoint
# 8. Create the Secure API Endpoint
@app.post("/ask")
async def ask_engineer(query: Query, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    print(f"\nIncoming Question: {query.question} for Session: {query.session_id}")
    
    # --- 1. SECURITY CHECK ---
    # Verify the user actually owns the session they are trying to post to
    session = db.query(ChatSession).filter(ChatSession.id == query.session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or unauthorized")

    # 2. Save the User's message to the Database instantly
    user_msg = ChatMessage(session_id=query.session_id, role="user", content=query.question)
    db.add(user_msg)
    db.commit()
    
    # 3. Fetch past history for this session from the Database
    db_history = db.query(ChatMessage).filter(ChatMessage.session_id == query.session_id).order_by(ChatMessage.timestamp.asc()).all()
    
    async def generate_response():
        messages = [SystemMessage(content=system_prompt)]
        messages.extend(format_db_history(db_history))
        full_ai_response = "" 
        
        # --- NEW: We package the user_id into a config object ---
        graph_config = {"configurable": {"user_id": current_user.id}}
        
        try:
            # We pass the config into the agent here!
            async for chunk in agent_executor.astream({"messages": messages}, config=graph_config):
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
                                
                                # Manually invoking the tool with the secure config
                                result = search_engineering_manuals.invoke(
                                    {"query": search_query}, 
                                    config=graph_config
                                )
                                yield f"__TOOL_RESULT__:{result}:::"
                                
                                follow_up = f"System: The search tool returned this excerpt:\n\n{result}\n\nSummarize this to answer the user directly. Do not use JSON."
                                messages.append(AIMessage(content=agent_msg.content))
                                messages.append(HumanMessage(content=follow_up))
                                
                                async for final_chunk in llm.astream(messages):
                                    full_ai_response += final_chunk.content
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
                                    full_ai_response += final_chunk.content 
                                    yield final_chunk.content
                        
                        except Exception as e:
                            print(f"Failed to parse manual tool call: {e}")
                            full_ai_response += agent_msg.content
                            yield agent_msg.content 
                            
                    elif agent_msg.content:
                        full_ai_response += agent_msg.content 
                        yield agent_msg.content
                        
                elif "tools" in chunk:
                    tool_msg = chunk["tools"]["messages"][-1]
                    yield f"__TOOL_RESULT__:{tool_msg.content}:::"
                    
        except Exception as e:
            error_msg = f"Agent Error: {str(e)}"
            full_ai_response += error_msg
            yield error_msg
            
        finally:
            # 4. Save the AI's answer securely
            if full_ai_response:
                save_db = SessionLocal()
                ai_db_msg = ChatMessage(session_id=query.session_id, role="ai", content=full_ai_response)
                save_db.add(ai_db_msg)
                save_db.commit()
                save_db.close()
            
    return StreamingResponse(generate_response(), media_type="text/plain")