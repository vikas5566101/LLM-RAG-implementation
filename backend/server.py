from typing import List, Dict
from operator import itemgetter

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# 1. Initialize the App
app = FastAPI(title="Digital Process Engineer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows any local HTML file to talk to the server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Connect to the Local Knowledge Base (The Brain we just built)
print("Loading Vector Database...")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_db = Chroma(
    persist_directory="./chroma_db", 
    embedding_function=embeddings
)
# Create a retriever that pulls the top 3 paragraphs
retriever = vector_db.as_retriever(search_kwargs={"k": 5})

# 3. Connect to Local Llama 3.2 via Ollama (The Engine)
print("Connecting to Llama 3.1...")
llm = OllamaLLM(model="llama3.2")

# 4. Define the AI's Persona and Strict Safety Rules
# 4. Define the AI's Persona and Strict Safety Rules
PROMPT_TEMPLATE = """
You are a Senior Digital Process Engineer.
Answer using ONLY the provided context. If it's not there, say you cannot find it.
Be concise, use bullet points, and cite the document name.

Previous Conversation:
{chat_history}

Context from Engineering Manuals:
{context}

User Question: {question}

Answer:
"""
prompt = PromptTemplate.from_template(PROMPT_TEMPLATE)

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

def format_history(history_list):
    # Converts the React array into a readable text script for the AI
    return "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history_list])

def combine_search_query(inputs):
    # This merges the history and the new question so the database knows what we are talking about
    return f"{inputs['chat_history']} {inputs['question']}"
# We use itemgetter to map the incoming dictionary to the right variables
qa_chain = (
    {
        "context": combine_search_query | retriever | format_docs,
        "question": itemgetter("question"),
        "chat_history": itemgetter("chat_history")
    }
    | prompt
    | llm
    | StrOutputParser()
)

# 6. Define the API Input Format
class Query(BaseModel):
    question: str
    chat_history: List[Dict[str, str]] = []

# 7. Create the API Endpoint
@app.post("/ask")
async def ask_engineer(query: Query):
    print(f"Incoming Question: {query.question}")
    
    async def generate_response():
        # Pass both the question and the formatted history into the chain
        for chunk in qa_chain.stream({
            "question": query.question,
            "chat_history": format_history(query.chat_history)
        }):
            yield chunk
            
    return StreamingResponse(generate_response(), media_type="text/plain")