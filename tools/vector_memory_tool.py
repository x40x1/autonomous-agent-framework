import logging
import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import uuid
import os

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

# Requires chromadb and sentence-transformers
# pip install chromadb sentence-transformers

# --- NEW GLOBAL PATCH ---
# Ensure that transformers.modeling_utils provides init_empty_weights
try:
    from transformers.modeling_utils import init_empty_weights
except ImportError:
    import transformers.modeling_utils
    transformers.modeling_utils.init_empty_weights = lambda *args, **kwargs: None
# --- END PATCH ---

class VectorMemoryTool(BaseTool):
    name = "vector_memory"
    description = (
        "Manages a persistent vector-based memory for semantic storage and retrieval. "
        "Input: {'action': '...', 'params': {...}}. Actions: "
        "'store': {'text': '...', 'metadata': {'source': '...', ... (optional)}} -> Stores text chunk. "
        "'query': {'query_text': '...', 'n_results': 5} -> Retrieves relevant text chunks. "
        "'list_collections': {} -> Lists available memory collections. "
        "'delete_collection': {'collection_name': '...'} -> Deletes a collection. "
        # Add 'delete_item' later if needed
    )

    def __init__(self, persist_directory: str = "workspace/.memory/vector_db", collection_name: str = "agent_knowledge", embedding_model_name: str = "all-MiniLM-L6-v2"):
        self.persist_directory = persist_directory
        self.default_collection_name = collection_name
        self.embedding_model_name = embedding_model_name

        try:
            # Ensure persist directory exists
            os.makedirs(self.persist_directory, exist_ok=True)

            self.client = chromadb.PersistentClient(path=self.persist_directory)
            logger.info(f"VectorMemoryTool initialized. DB Path: '{self.persist_directory}'. Default Collection: '{self.default_collection_name}'.")

            # The previous local patch is removed in favor of the global patch above.
            logger.info(f"Loading embedding model: {self.embedding_model_name}...")
            self.embedding_model = SentenceTransformer(self.embedding_model_name, device="cpu")
            logger.info("Embedding model loaded successfully.")

            # Ensure default collection exists
            self._get_or_create_collection(self.default_collection_name)

        except ImportError:
             logger.error("chromadb or sentence-transformers not installed. Run 'pip install chromadb sentence-transformers'")
             raise ImportError("chromadb or sentence-transformers not installed.")
        except Exception as e:
             logger.error(f"Error initializing VectorMemoryTool or loading embedding model: {e}", exc_info=True)
             raise RuntimeError(f"Failed to initialize vector memory: {e}")

    def _get_or_create_collection(self, collection_name: str):
        """Gets or creates a ChromaDB collection."""
        try:
            # Use the embedding function directly with the model
            collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(model_name=self.embedding_model_name)
                 # metadata={"hnsw:space": "cosine"} # Optional: specify distance metric
            )
            logger.info(f"Accessed or created vector collection: '{collection_name}'")
            return collection
        except Exception as e:
            logger.error(f"Failed to get or create collection '{collection_name}': {e}", exc_info=True)
            raise RuntimeError(f"Failed to access vector collection '{collection_name}': {e}")


    def execute(self, **kwargs) -> str:
        action = kwargs.get('action')
        params = kwargs.get('params', {})
        collection_name = params.get('collection_name', self.default_collection_name)

        if not action: return "Error: No action specified for vector_memory tool."
        action = action.lower()
        logger.info(f"Executing Vector Memory action: {action} on collection '{collection_name}' with params: {params}")

        try:
            if action == 'store':
                text = params.get('text')
                metadata = params.get('metadata', {})
                if not text: return "Error: 'text' parameter missing for 'store' action."

                collection = self._get_or_create_collection(collection_name)
                # Generate a unique ID for the document
                doc_id = str(uuid.uuid4())
                # Embedding happens automatically if embedding_function is set on collection
                collection.add(
                    documents=[text],
                    metadatas=[metadata or {}], # Ensure metadata is at least an empty dict
                    ids=[doc_id]
                )
                return f"Successfully stored text in collection '{collection_name}' with ID {doc_id}."

            elif action == 'query':
                query_text = params.get('query_text')
                n_results = params.get('n_results', 5)
                if not query_text: return "Error: 'query_text' parameter missing for 'query' action."

                collection = self._get_or_create_collection(collection_name)
                results = collection.query(
                    query_texts=[query_text],
                    n_results=n_results,
                    include=['documents', 'metadatas', 'distances'] # Include distance for relevance
                )

                if not results or not results.get('ids') or not results['ids'][0]:
                    return f"No relevant information found in collection '{collection_name}' for query: '{query_text}'"

                output = f"Found {len(results['ids'][0])} relevant result(s) for '{query_text}' in '{collection_name}':\n"
                # results structure: {'ids': [[]], 'distances': [[]], 'metadatas': [[]], 'embeddings': None, 'documents': [[]]}
                for i in range(len(results['ids'][0])):
                     doc_id = results['ids'][0][i]
                     distance = results['distances'][0][i]
                     meta = results['metadatas'][0][i]
                     doc = results['documents'][0][i]
                     # Limit doc length in output
                     max_len=500
                     if len(doc) > max_len: doc = doc[:max_len]+"..."

                     output += f"- ID: {doc_id} (Distance: {distance:.4f})\n"
                     if meta: output += f"  Metadata: {meta}\n"
                     output += f"  Content: {doc}\n"

                return output.strip()

            elif action == 'list_collections':
                 collections = self.client.list_collections()
                 if not collections: return "No vector memory collections found."
                 output = "Available vector memory collections:\n"
                 for col in collections:
                     output += f"- {col.name} (Count: {col.count()})\n" # count() might be expensive
                 return output.strip()

            elif action == 'delete_collection':
                 col_name_to_delete = params.get('collection_name')
                 if not col_name_to_delete: return "Error: 'collection_name' parameter missing for 'delete_collection'."
                 if col_name_to_delete == self.default_collection_name:
                      return f"Error: Cannot delete the default collection ('{self.default_collection_name}') via this tool for safety."

                 try:
                      self.client.delete_collection(name=col_name_to_delete)
                      return f"Successfully deleted collection '{col_name_to_delete}'."
                 except ValueError: # Chroma raises ValueError if collection doesn't exist
                      return f"Error: Collection '{col_name_to_delete}' not found."
                 except Exception as e:
                      logger.error(f"Error deleting collection '{col_name_to_delete}': {e}", exc_info=True)
                      return f"Error deleting collection '{col_name_to_delete}': {e}"

            else:
                 return f"Error: Unknown vector_memory action '{action}'."

        except Exception as e:
            logger.error(f"An error occurred during Vector Memory action '{action}': {e}", exc_info=True)
            return f"Error during vector_memory action '{action}': {e}"