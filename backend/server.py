from fastapi import FastAPI
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
retriever = vector_db.as_retriever(search_kwargs={"k": 3})

# 3. Connect to Local Llama 3.2 via Ollama (The Engine)
print("Connecting to Llama 3.1...")
llm = OllamaLLM(model="llama3.1")

# 4. Define the AI's Persona and Strict Safety Rules
# 4. Define the AI's Persona and Strict Safety Rules
PROMPT_TEMPLATE = """
You are a Senior Digital Process Engineer with 20 years of experience in petroleum refining and petrochemicals.
Your job is to provide highly technical, practical, and direct answers to junior engineers using ONLY the provided context.

CRITICAL INSTRUCTIONS:
1. NO GUESSING: If the answer is not explicitly in the context, you must reply: "I cannot find the answer in the provided engineering manuals."
2. CITE YOUR SOURCES: Begin your answer by stating the document or section you are pulling the information from (based on the context).
3. BE PRACTICAL: Focus on real-world operational reasons (e.g., mechanical cleaning, maintenance, fouling limits, pressure drops) rather than just theory.
4. BE CONCISE: Use bolding and bullet points. Do not write fluffy introductions or repetitive conclusions.

Context from Engineering Manuals:
{context}

User Question: {question}

Senior Process Engineer's Answer:
"""
prompt = PromptTemplate.from_template(PROMPT_TEMPLATE)

# Helper function to format retrieved documents into clean text
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# 5. Build the Modern RAG Pipeline (LCEL Syntax)
qa_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 6. Define the API Input Format
class Query(BaseModel):
    question: str

# 7. Create the API Endpoint
@app.post("/ask")
async def ask_engineer(query: Query):
    print(f"Incoming Question: {query.question}")
    
    # This single line runs the entire modern RAG pipeline!
    result = qa_chain.invoke(query.question)
    
    return {"answer": result}