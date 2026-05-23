from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# Initialize the FastAPI engine
app = FastAPI()

# Allow your frontend dashboard to talk to this backend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the exact structure we expect from the frontend
class QuestionRequest(BaseModel):
    question: str

# The route your dashboard will call
@app.post("/api/ask-engineer")
async def ask_engineer(request: QuestionRequest):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "process_engineer", # Your custom local AI
        "prompt": request.question,
        "stream": False
    }
    
    # We use a 300-second timeout to give your local CPU plenty of time to type out the answer
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status() # Check for errors
            
            data = response.json()
            return {"answer": data.get("response")}
            
        except httpx.ReadTimeout:
            raise HTTPException(status_code=504, detail="The AI took too long to respond. Try a shorter question.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to communicate with Ollama: {str(e)}")