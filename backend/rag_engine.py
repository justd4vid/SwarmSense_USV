import os
import json
import pandas as pd
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from sentence_transformers import SentenceTransformer
import requests
from dotenv import load_dotenv

load_dotenv()

# Custom Embedding Function for ChromaDB using SentenceTransformers
class SentenceTransformerEmbeddingFunction(EmbeddingFunction[Documents]):
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = self.model.encode(input, convert_to_numpy=True)
        return embeddings.tolist()

class SwarmRAG:
    def __init__(self):
        print("Initializing Local SwarmRAG with Ollama (Qwen3 8B)...")
        
        try:
            # 1. Initialize Embeddings (Local)
            self.embedding_function = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            
            # 2. Initialize ChromaDB
            # Use absolute path to ensure consistency regardless of working directory
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chroma_db")
            chroma_client = chromadb.PersistentClient(path=db_path)
            self.collection = chroma_client.get_or_create_collection(
                name="swarm_logs",
                embedding_function=self.embedding_function
            )
            
            # 3. Configure Ollama connection
            self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
            self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
            
            # Test connection to Ollama
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code != 200:
                raise ConnectionError(f"Cannot connect to Ollama at {self.ollama_url}")
            
            # Check if model is available
            available_models = [m['name'] for m in response.json().get('models', [])]
            if not any(self.ollama_model in m for m in available_models):
                print(f"Warning: Model '{self.ollama_model}' not found. Available: {available_models}")
            
            self.llm_ready = True
            print(f"SwarmRAG initialized successfully with Ollama ({self.ollama_model}).")
        except Exception as e:
            print(f"Failed to initialize Local SwarmRAG components: {e}")
            self.collection = None
            self.llm_ready = False

    def ingest_logs(self, file_path: str):
        """
        Reads the simulated log file.
        If RAG is active, filters significant events and stores them in ChromaDB.
        Always returns the raw data for visualization.
        """
        print(f"Ingesting logs from {file_path}...")
        
        # Read JSONL
        data = []
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    if line.strip():
                        data.append(json.loads(line))
        except Exception as e:
            print(f"Error reading log file: {e}")
            return []
        
        # If no RAG, just return data for viz
        if not self.collection:
            print("Skipping Vector Store ingestion (RAG disabled/failed).")
            return data

        df = pd.DataFrame(data)
        
        # Filter Logic:
        # 1. Keep ALL rows where status == 'ERROR'
        # 2. Keep ALL rows where status changes (e.g., IDLE -> MOVING)
        # 3. For the rest, sample every 200th row per boat to avoid spam.
        
        documents = []
        metadatas = []
        ids = []
        
        # Helper to track previous status per boat
        prev_status = {} # boat_id -> status
        
        for idx, row in df.iterrows():
            boat_id = row['boat_id']
            # Handle potentially missing fields from new simulator format
            status = row.get('status')
            if not status:
                # Synthesize status
                speed = row.get('speed_knots', 0)
                status = "MOVING" if speed > 0.1 else "IDLE"
            
            # Additional fields
            boat_type = row.get('type', 'unknown')
            target_id = row.get('target_id')
            
            timestamp = row['timestamp']
            
            is_significant = False
            
            # Rule 1: Errors (if field exists and is "ERROR")
            if status == "ERROR":
                is_significant = True
            
            # Rule 2: Status Change
            old_status = prev_status.get(boat_id)
            if old_status != status:
                is_significant = True
            prev_status[boat_id] = status
            
            # Rule 3: Periodic Sampling
            if not is_significant and idx % 200 == 0: 
                is_significant = True
            
            if is_significant:
                # Construct text description
                text = (
                    f"Timestamp: {timestamp}. "
                    f"Boat {boat_id} ({boat_type}) is {status}. "
                    f"Position: ({row['lat']}, {row['lon']}). "
                )
                
                # Add optional fields if present
                if 'battery' in row:
                    text += f"Battery: {row['battery']}%. "
                if 'speed_knots' in row:
                    text += f"Speed: {row['speed_knots']} kn. "
                if 'course_deg' in row:
                    text += f"Course: {row['course_deg']} deg. "
                if target_id:
                     text += f"Target: {target_id}. "
                
                if row.get('error_details'):
                    text += f"Error: {row['error_details']}."
                
                documents.append(text)
                metadatas.append({
                    "boat_id": boat_id, 
                    "timestamp": timestamp,
                    "status": status,
                    "type": "log_entry"
                })
                ids.append(f"log_{idx}")

        if documents:
            print(f"Adding {len(documents)} significant entries to Vector Store...")
            try:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                print("Ingestion complete.")
            except Exception as e:
                print(f"Vector Store add failed: {e}")
        else:
            print("No significant logs found to ingest.")
        
        return data

    def query_swarm(self, query_text: str) -> str:
        """
        RAG Pipeline:
        1. Retrieve relevant logs from Chroma.
        2. Construct Prompt.
        3. Call Ollama LLM.
        """
        if not self.llm_ready or not self.collection:
            return "Local RAG is not initialized - check logs for errors."

        try:
            # Retrieve
            results = self.collection.query(
                query_texts=[query_text],
                n_results=15
            )
            
            retrieved_docs = results['documents'][0]
            context = "\n".join(retrieved_docs)
            
            # System Prompt
            system_prompt = (
                "You are a Swarm Intelligence Assistant for USV operators. "
                "You have access to a stream of log fragments from the swarm. "
                "Analyze the retrieved context to answer the user's question accurately. "
                "The Context contains timestamped log entries. "
                "If the logs show specific errors for a boat, mention the boat ID and the error. "
                "If the status is normal, say so. "
                "Be concise and professional."
            )
            
            # Call Ollama chat API
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query_text}"}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.95,
                        "num_predict": 512
                    }
                },
                timeout=120
            )
            
            if response.status_code != 200:
                return f"Ollama error: {response.text}"
            
            result = response.json()
            return result.get("message", {}).get("content", "No response generated.")
        except Exception as e:
            return f"Error during query: {str(e)}"

