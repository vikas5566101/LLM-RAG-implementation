import fitz  # PyMuPDF
import json
from langchain_ollama import OllamaLLM

# Connect to your local Ollama engine
llm = OllamaLLM(model="llama3.2") 

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def generate_qa_pairs(chunk):
    prompt = f"""
    You are an expert petroleum engineering professor. Read the following text chunk from an engineering manual and generate 2 highly technical question-and-answer pairs based ONLY on the text. 
    
    Output strictly in this JSON format:
    [
      {{"question": "What is...", "answer": "The process involves..."}},
      {{"question": "How does...", "answer": "By utilizing..."}}
    ]

    Text chunk:
    {chunk}
    """
    
    # Call your local Ollama model to generate the questions
    response = llm.invoke(prompt)
    
    try:
        # Extract just the JSON part of the response
        clean_json = response[response.find("["):response.rfind("]")+1]
        return json.loads(clean_json)
    except:
        return [] # Skip if the model formatting fails

print("Reading PDF...")
raw_text = extract_text_from_pdf("data/manual1.pdf")

# Split text into manageable 1500-character chunks
chunk_size = 1500
chunks = [raw_text[i:i+chunk_size] for i in range(0, len(raw_text), chunk_size)]

print(f"Generated {len(chunks)} chunks. Asking Ollama to create Q&A pairs...")
dataset = []

# Processing just the first 10 chunks to test the system
# (Once it works, you can remove '[:10]' to process the whole book)
for i, chunk in enumerate(chunks[:10]):
    print(f"Processing chunk {i+1}...")
    qa_pairs = generate_qa_pairs(chunk)
    
    for qa in qa_pairs:
        chatml_format = {
            "conversations": [
                {"role": "user", "content": qa["question"]},
                {"role": "assistant", "content": qa["answer"]}
            ]
        }
        dataset.append(chatml_format)

with open("training_dataset.json", "w") as f:
    json.dump(dataset, f, indent=4)
    
print("Dataset successfully saved to training_dataset.json!")