# ⚙️ Senior Process Engineer AI Dashboard

A full-stack, locally hosted AI web application designed to answer complex chemical engineering scale-up questions. 

This project demonstrates a complete end-to-end Machine Learning and Web Development pipeline: fine-tuning a Large Language Model (LLM) on custom engineering manuals, serving it entirely offline via local hardware, and building an asynchronous web dashboard to interact with the engine.

## 🏗️ Architecture Stack
* **AI Model:** LLaMA-3.2 (8-Billion Parameters), fine-tuned using Unsloth & exported to GGUF.
* **Inference Engine:** [Ollama](https://ollama.com/) (Local API & Model Management).
* **Backend:** Python + FastAPI + Uvicorn (Asynchronous API routing).
* **Frontend:** Vanilla HTML5, CSS3, and JavaScript (Fetch API).

---

## 🚀 How to Run This Project Locally

*Note: Due to GitHub's 100MB file limit, the custom 4.6 GB fine-tuned `.gguf` model is not included in this repository. The instructions below will guide you to boot the architecture using a standard LLaMA 3 model to test the full-stack routing.*

### Prerequisites
1. **[Python 3.9+](https://www.python.org/downloads/)** installed.
2. **[Ollama](https://ollama.com/)** installed and running in the background.

### Step 1: Clone the Repository
```bash
git clone [https://github.com/vikas5566101/process-engineer-ai-single-dataset.git](https://github.com/vikas5566101/process-engineer-ai-single-dataset.git)
cd process-engineer-ai-single-dataset