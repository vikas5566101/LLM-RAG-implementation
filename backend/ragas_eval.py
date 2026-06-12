import warnings
warnings.filterwarnings('ignore') # Hides messy deprecation warnings

from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset
from langchain_ollama import ChatOllama
from langchain_community.embeddings import HuggingFaceEmbeddings

print("Booting up the AI Judge (Llama 3.2)...")

# 1. Initialize the "Judge" LLM and Embeddings
# We use your local Ollama instance to grade the pipeline!
judge_llm = ChatOllama(model="llama3.2", base_url="http://host.docker.internal:11434", temperature=0)
judge_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# 2. Prepare the Enterprise Test Data
# We are providing the Question, the AI's Answer, the Database's Chunks, and the "Ground Truth" (Answer Key)
data_samples = {
    "question": [
        "Should a pressure-relief valve be mounted in a horizontal or vertical position?"
    ],
    "answer": [
        "A pressure-relief valve should be mounted in a vertical position to ensure proper operation and safety. According to API Standard 520, Part II-Installation, the vent pipe should be connected to the relief valve at its lowest point..."
    ],
    "contexts": [[
        "PRVs and rupture pin valves should be mounted in a vertical upright position. Installation of a PRV in other than a vertical upright position may adversely affect its operation. The valve manufacturer should be consulted about any other mounting position..."
    ]],
    "ground_truth": [
        "It should be mounted in a vertical upright position."
    ]
}

# Convert dictionary to HuggingFace Dataset format
dataset = Dataset.from_dict(data_samples)

# 3. Run the Automated Grading
print("Grading the RAG Pipeline (This may take a minute as Llama 3.2 reads the test)...")
score = evaluate(
    dataset,
    metrics=[
        faithfulness,       # Did the AI hallucinate?
        answer_relevancy,   # Did the AI actually answer the prompt?
        context_precision,  # Did ChromaDB fetch the exact right chunk?
        context_recall      # Did ChromaDB fetch ALL the necessary info?
    ],
    llm=judge_llm,
    embeddings=judge_embeddings
)

print("\n--- FINAL ENTERPRISE REPORT CARD ---")
print(score)