import os
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# 1. Define the files curated for the Digital Process Engineer
FILES_TO_INGEST = [
    "../data/oisd_safety.pdf",             # Use Case 2: Safety Standard 114
    "../data/perrys_shell_and_tube.pdf",   # Use Case 3: Hardware & Troubleshooting
    "../data/perrys_section_5_subset.pdf"  # Use Case 1: Heat Transfer Calculations
]

DB_DIRECTORY = "./chroma_db"

def build_vector_database():
    all_chunks = []
    
    for file_path in FILES_TO_INGEST:
        print(f"Ingesting: {file_path}...")
        
        # Using PyMuPDFLoader to handle the two-column layouts in Perry's
        loader = PyMuPDFLoader(file_path)
        documents = loader.load()
        
        # Chop the manuals into overlapping, searchable paragraphs
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, 
            chunk_overlap=100
        )
        chunks = text_splitter.split_documents(documents)
        all_chunks.extend(chunks)
        print(f" -> Extracted {len(chunks)} chunks from this file.")

    print(f"\nTotal chunks generated across all files: {len(all_chunks)}")
    
    # Download the local AI translator to convert text to vector math
    print("Downloading/Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # Build and save the unified Chroma Vector Database
    print("Building the Chroma Vector Database...")
    db = Chroma.from_documents(
        documents=all_chunks, 
        embedding=embeddings, 
        persist_directory=DB_DIRECTORY
    )
    print(f"✅ Success! Local knowledge base built at {DB_DIRECTORY}")

if __name__ == "__main__":
    build_vector_database()