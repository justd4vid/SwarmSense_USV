import os
import json
import pandas as pd
import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, pipeline
from sentence_transformers import SentenceTransformer
import torch
from dotenv import load_dotenv
from typing import List, Dict

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
        print("Initializing Local SwarmRAG with Qwen2.5-7B-Instruct (4-bit)...")
        
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
            
            # 3. Initialize Local LLM (4-bit quantization)
            model_id = "Qwen/Qwen2.5-7B-Instruct"
            
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True
            )
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_id)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True
            )
            
            self.pipe = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                max_new_tokens=512,
                temperature=0.1,
                top_p=0.95,
                repetition_penalty=1.15
            )

            print("SwarmRAG initialized successfully with Local LLM.")
        except Exception as e:
            print(f"Failed to initialize Local SwarmRAG components: {e}")
            self.collection = None
            self.pipe = None

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
            status = row['status']
            timestamp = row['timestamp']
            
            is_significant = False
            
            # Rule 1: Errors
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
                    f"Boat {boat_id} is {status}. "
                    f"Position: ({row['lat']}, {row['lon']}). "
                    f"Battery: {row['battery']}%. "
                    f"Speed: {row['speed_knots']} kn. "
                    f"Course: {row['course_deg']} deg. "
                )
                if row['error_details']:
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
        3. Call Local LLM.
        """
        if not self.pipe or not self.collection:
            return "Local RAG is not initialized check logs for errors."

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
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query_text}"}
            ]
            
            prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            
            outputs = self.pipe(prompt)
            generated_text = outputs[0]["generated_text"]
            
            # Extract only the assistant's response (remove the prompt)
            # Different models have different raw output formats, but generation usually appends.
            # Qwen chat template handles this, but pipeline returns full text usually.
            
            # Basic parsing: look for where the prompt ends
            if prompt in generated_text:
                response = generated_text.replace(prompt, "").strip()
            else:
                response = generated_text # Fallback
            
            return response
        except Exception as e:
            return f"Error during query: {str(e)}"
