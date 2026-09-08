# Backend: FastAPI + LangGraph agents
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for layer caching.
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY config.yaml .
COPY src/ src/
COPY mcp_server/ mcp_server/
COPY knowledge_base/ knowledge_base/

# Pre-build the FAISS index at image build time so the first request is fast
# (downloads the ~90MB embedding model once, baked into the image).
RUN python -m src.rag.vector_store

EXPOSE 8000

CMD ["uvicorn", "src.web_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
