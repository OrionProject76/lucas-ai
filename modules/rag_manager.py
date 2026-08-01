import os
import requests

from config import OLLAMA_HOST, RAG_MAX_DISTANCE

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
                # OLLAMA_HOST, pas « localhost » : ce dernier coûte 2 s de
                # timeout IPv6 par appel sur cette machine (voir config.py).
                # Ici le surcoût était le pire de tous — un document découpé
                # en 40 chunks payait 80 s d'attente pure à l'indexation.
                response = requests.post(
                    f"{OLLAMA_HOST}/api/embeddings",
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
            self.collection = self._open_collection()
            self.use_chroma = True
        except Exception as e:
            print(f"ChromaDB indisponible, bascule en mode fallback : {e}")
            self.use_chroma = False
            self.collection = None

    # Espace de distance de la collection. Cosinus et non L2 (le défaut de
    # ChromaDB) : le cosinus est borné et indépendant de la longueur des
    # textes, ce qui rend RAG_MAX_DISTANCE interprétable. Voir config.py.
    _SPACE = "cosine"

    def _open_collection(self):
        """
        Ouvre la collection, en la recréant si elle utilise encore l'ancien
        espace L2.

        ChromaDB fige l'espace de distance à la création : un
        get_or_create_collection() sur une collection L2 existante la
        rendrait telle quelle, et les distances resteraient dans une
        échelle où RAG_MAX_DISTANCE n'a aucun sens. La migration est sans
        risque — les documents sources restent sur le disque, seuls les
        vecteurs sont recalculés.
        """
        collection = self.chroma_client.get_or_create_collection(
            name="orion_docs",
            embedding_function=OllamaEmbeddingFunction(),
            metadata={"hnsw:space": self._SPACE},
        )

        if (collection.metadata or {}).get("hnsw:space") == self._SPACE:
            return collection

        print(
            "Collection RAG en distance L2 (ancien format) — reconstruction "
            f"en {self._SPACE}, le temps de recalculer les embeddings."
        )
        existing = collection.get(include=["documents", "metadatas"])
        self.chroma_client.delete_collection("orion_docs")
        collection = self.chroma_client.create_collection(
            name="orion_docs",
            embedding_function=OllamaEmbeddingFunction(),
            metadata={"hnsw:space": self._SPACE},
        )
        if existing["ids"]:
            collection.add(
                documents=existing["documents"],
                metadatas=existing["metadatas"] or None,
                ids=existing["ids"],
            )
        return collection

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

    def search(self, query, top_k=3, max_distance=RAG_MAX_DISTANCE):
        """
        Recherche les passages les plus pertinents.

        ⚠️ Le filtrage par distance n'est pas un raffinement, c'est une
        correction. Sans lui, ChromaDB renvoie TOUJOURS ses `top_k`
        meilleurs voisins, aussi mauvais soient-ils — il n'existe pas de
        « aucun résultat » dans une recherche vectorielle. Sur la question
        « une synthèse rapide d'un document sur mon écran », la base
        remontait un extrait de sample_document.txt sur l'intelligence
        artificielle, que get_context() annonçait ensuite comme
        « contexte trouvé dans les documents ». Le LLM l'a suivi et a
        ignoré ce qui avait été réellement lu à l'écran.

        `max_distance=None` désactive le filtre (utile pour diagnostiquer
        ce que la base contient réellement).
        """
        if self.use_chroma and self.collection:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["documents", "distances"],
            )
            documents = (results.get("documents") or [[]])[0]
            distances = (results.get("distances") or [[]])[0]

            if max_distance is None or not distances:
                return list(documents)
            return [
                doc
                for doc, distance in zip(documents, distances)
                if distance <= max_distance
            ]

        # Fallback : recherche texte simple. Pas de distance ici — une
        # sous-chaîne trouvée est une correspondance exacte, donc pertinente.
        query_lower = query.lower()
        matches = []
        for doc_id, i, chunk in self.chunks:
            if query_lower in chunk.lower():
                matches.append(chunk)
        return matches[:top_k]

    def get_context(self, query, top_k=3):
        """
        Retourne le contexte formaté pour le LLM, ou une chaîne VIDE si
        aucun extrait n'est assez proche.

        La chaîne vide est significative : l'appelant
        (OrionCore._build_messages) n'ajoute alors aucun bloc au prompt.
        L'ancienne version renvoyait la phrase « Aucun document pertinent
        trouvé. », qui était injectée telle quelle et occupait un tour de
        contexte pour ne rien dire.
        """
        results = self.search(query, top_k)
        if not results:
            return ""
        context = "\n\n".join([f"[Extrait {i+1}] {r[:300]}..." for i, r in enumerate(results)])
        return f"Contexte trouvé dans les documents:\n{context}"


if __name__ == "__main__":
    rm = RAGManager()
    rm.add_document("data/sample_document.txt")
    print(rm.get_context("intelligence artificielle"))