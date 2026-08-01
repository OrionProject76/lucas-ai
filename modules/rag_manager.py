import os
import requests

try:
    from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
except ImportError:
    from chromadb import EmbeddingFunction, Documents, Embeddings


class OllamaEmbeddingFunction(EmbeddingFunction):
    """
    Fonction d'embedding personnalisée pour ChromaDB, basée sur Ollama
    (nomic-embed-text, 768 dimensions).

    Pourquoi cette approche plutôt que calculer les embeddings nous-mêmes
    et les transmettre manuellement : on a rencontré des incohérences de
    dimension entre l'ajout et la recherche (ChromaDB traite l'ajout et
    la recherche différemment selon qu'une "fonction d'embedding" est
    déclarée sur la collection ou non). En déléguant entièrement le calcul
    à ChromaDB via cette classe, c'est exactement la même fonction qui est
    appelée à l'ajout ET à la recherche — aucune divergence possible.
    """

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            try:
                response = requests.post(
                    "http://localhost:11434/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": text},
                )
                embeddings.append(response.json()["embedding"])
            except Exception as e:
                raise RuntimeError(
                    f"Échec de l'embedding Ollama (nomic-embed-text) — "
                    f"vérifier qu'Ollama tourne (ollama serve). Détail : {e}"
                )
        return embeddings


class RAGManager:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.documents = []
        self.chunks = []
        try:
            import chromadb
            self.chroma_client = chromadb.PersistentClient(path=os.path.join(data_dir, "chromadb"))
            self.collection = self.chroma_client.get_or_create_collection(
                name="orion_docs",
                embedding_function=OllamaEmbeddingFunction(),
            )
            self.use_chroma = True
        except Exception as e:
            print(f"ChromaDB indisponible, bascule en mode fallback : {e}")
            self.use_chroma = False
            self.collection = None

    def _chunk_text(self, text, chunk_size=500):
        """Découpe le texte en morceaux de chunk_size caractères"""
        return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

    def add_document(self, filepath):
        """Ajoute un document à la base de connaissances"""
        if not os.path.exists(filepath):
            print(f"Fichier introuvable: {filepath}")
            return False

        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        chunks = self._chunk_text(text)
        doc_id = os.path.basename(filepath)

        if self.use_chroma and self.collection:
            # Plus besoin de calculer les embeddings manuellement — la
            # fonction d'embedding déclarée sur la collection (Ollama)
            # est appelée automatiquement par ChromaDB.
            self.collection.add(
                documents=chunks,
                metadatas=[{"source": doc_id, "chunk": i} for i in range(len(chunks))],
                ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
            )
        else:
            self.chunks.extend([(doc_id, i, chunk) for i, chunk in enumerate(chunks)])

        self.documents.append(doc_id)
        print(f"Document ajouté: {doc_id} ({len(chunks)} chunks)")
        return True

    def search(self, query, top_k=3):
        """Recherche les passages les plus pertinents"""
        if self.use_chroma and self.collection:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
            )
            return results["documents"][0] if results["documents"] else []
        # Fallback : recherche texte simple
        query_lower = query.lower()
        matches = []
        for doc_id, i, chunk in self.chunks:
            if query_lower in chunk.lower():
                matches.append(chunk)
        return matches[:top_k]

    def get_context(self, query, top_k=3):
        """Retourne le contexte formaté pour le LLM"""
        results = self.search(query, top_k)
        if not results:
            return "Aucun document pertinent trouvé."
        context = "\n\n".join([f"[Extrait {i+1}] {r[:300]}..." for i, r in enumerate(results)])
        return f"Contexte trouvé dans les documents:\n{context}"


if __name__ == "__main__":
    rm = RAGManager()
    rm.add_document("data/sample_document.txt")
    print(rm.get_context("intelligence artificielle"))