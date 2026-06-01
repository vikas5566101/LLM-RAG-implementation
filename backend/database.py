from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import uuid

# 1. Setup SQLite Engine
SQLALCHEMY_DATABASE_URL = "sqlite:///./chat_history.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. Define the Chat Session Table
class ChatSession(Base):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Link to messages
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

# 3. Define the Messages Table
class ChatMessage(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    role = Column(String) # "user" or "ai"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Link back to session
    session = relationship("ChatSession", back_populates="messages")

# 4. Create the tables in the database
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()