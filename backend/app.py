import streamlit as st
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# 1. Page Config
st.set_page_config(page_title="Digital Process Engineer", page_icon="⚙️")
st.title("⚙️ Senior Process Engineer")

# 2. Cache the Database Load (so it doesn't reload on every message)
@st.cache_resource
def load_knowledge_base():
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vector_db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    return vector_db.as_retriever(search_kwargs={"k": 3})

retriever = load_knowledge_base()

# 3. Initialize the Fast Quantized LLM
llm = OllamaLLM(model="llama3.1:8b-instruct-q4_0")

# 4. Define the Prompt
PROMPT_TEMPLATE = """
You are a Senior Digital Process Engineer. 
Answer using ONLY the provided context.
If the answer is not in the context, reply: "I cannot find the answer in the provided engineering manuals."
Be concise, use bullet points, and cite the document name.

Context:
{context}

Question: {question}

Answer:
"""
prompt = PromptTemplate.from_template(PROMPT_TEMPLATE)

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# Modern LCEL Chain
qa_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# 5. Initialize Chat History in Streamlit Session State
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Engine initialized. What process scale-up questions can I help you with today?"}
    ]

# Display historical messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 6. Chat Input and Streaming Logic
if user_query := st.chat_input("Ask a detailed engineering question..."):
    # Add user message to UI
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    # Generate and Stream AI response
    with st.chat_message("assistant"):
        # st.write_stream automatically handles the yielding chunks!
        response = st.write_stream(qa_chain.stream(user_query))
    
    # Save the final AI response to history
    st.session_state.messages.append({"role": "assistant", "content": response})