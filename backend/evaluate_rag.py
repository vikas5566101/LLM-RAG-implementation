import time
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# --- NEW: Check the Database for Users ---
from database import SessionLocal, User
db = SessionLocal()
print("\n--- REGISTERED USERS ---")
for u in db.query(User).all():
    print(f"ID: {u.id} | Username: {u.username}")
print("------------------------\n")
# ---------------------------------------

# 1. Connect to the exact same database your server uses
print("Loading Embeddings Model...")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

print("Connecting to ChromaDB...")
vector_db = Chroma(
    persist_directory="./chroma_db", 
    embedding_function=embeddings
)

def run_benchmark(query: str, user_id: int, k_value: int):
    print(f"\n{'-'*50}")
    print(f"🔍 EVALUATING QUERY: '{query}'")
    print(f"⚙️ PARAMETERS: k={k_value} | target_user={user_id}")
    print(f"{'-'*50}")
    
    # Start the stopwatch
    start_time = time.time()
    
    # Run the exact search your LangGraph tool uses
    docs = vector_db.similarity_search(
        query, 
        k=k_value, 
        filter={"user_id": user_id}
    )
    
    # Stop the stopwatch
    end_time = time.time()
    latency = round((end_time - start_time) * 1000, 2) # Convert to milliseconds
    
    print(f"⏱️ RETRIEVAL LATENCY: {latency} ms")
    print(f"📚 CHUNKS RETRIEVED: {len(docs)}")
    print("\n--- RETRIEVED CONTEXT ---")
    
    if not docs:
        print("❌ FAILED: No documents found. (Is the user_id correct?)")
        return

    for i, doc in enumerate(docs):
        # We slice the content so it doesn't flood your terminal
        preview = doc.page_content.replace('\n', ' ')[:200]
        print(f"\nChunk {i+1}:")
        print(f"Data: {preview}...")
        print(f"Metadata: {doc.metadata}")

# --- RUN YOUR TESTS HERE ---

# IMPORTANT: You need to replace this integer with the actual user_id 
# of the account you created and uploaded a PDF to! (Usually 1 if it's the first user)
TEST_USER_ID = "94be5ab5-a902-4b08-b218-8b3f9ec25483"
# Test 1: Ask a question that should definitely be in the PDF you uploaded
test_query = "What is the main topic of this document?" 

# Run with k=5 (Your old setup)
run_benchmark(test_query, TEST_USER_ID, k_value=5)

# Run with k=3 (Your new optimized setup)
run_benchmark(test_query, TEST_USER_ID, k_value=3)