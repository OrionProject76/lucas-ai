import hashlib
import os
import re

import requests

from config import CHUNK_OVERLAP, CHUNK_SIZE, OLLAMA_HOST, RAG_MAX_DISTANCE

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

    # ── Idempotence ───────────────────────────────────────────────────

    def _already_indexed(self, doc_id, digest) -> bool:
        """Ce document est-il déjà en base, avec exactement ce contenu ?"""
        existing = self.collection.get(where={"source": doc_id}, include=["metadatas"])
        metadatas = existing.get("metadatas") or []
        return bool(metadatas) and all(m.get("sha") == digest for m in metadatas)

    def _forget(self, doc_id) -> int:
        """Retire tous les morceaux d'un document. Retourne leur nombre."""
        existing = self.collection.get(where={"source": doc_id})
        ids = existing.get("ids") or []
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)

    def remove_document(self, doc_id) -> int:
        """
        Désindexe un document.

        Nécessaire parce qu'un fichier supprimé du disque reste sinon
        consultable indéfiniment : la base ne le saurait jamais.
        """
        if self.use_chroma and self.collection:
            return self._forget(doc_id)
        before = len(self.chunks)
        self.chunks = [c for c in self.chunks if c[0] != doc_id]
        return before - len(self.chunks)

    def indexed_documents(self) -> set:
        """Noms des documents actuellement en base."""
        if self.use_chroma and self.collection:
            metadatas = self.collection.get(include=["metadatas"]).get("metadatas") or []
            return {m.get("source") for m in metadatas if m.get("source")}
        return {doc_id for doc_id, _, _ in self.chunks}

    # ── Découpage ─────────────────────────────────────────────────────

    def _chunk_text(self, text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
        """
        Découpe le texte en respectant les paragraphes.

        L'ancienne version coupait tous les 500 caractères, sans regarder
        le contenu — au milieu d'un mot, d'une phrase, d'un nombre. Un
        extrait qui commence par « ...ent de 1 250 euros par mois » perd
        de quoi il parle, et l'embedding avec lui : c'est la qualité de
        la recherche entière qui en dépend.

        Le recouvrement existe pour la même raison : une réponse à cheval
        sur deux paragraphes serait sinon coupée en deux moitiés dont
        aucune ne suffit à répondre.
        """
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            # Un paragraphe plus gros que la limite ne peut pas être gardé
            # entier : on le coupe, faute de mieux.
            if len(paragraph) > chunk_size:
                if current:
                    chunks.append(current)
                    current = ""
                for i in range(0, len(paragraph), chunk_size):
                    chunks.append(paragraph[i:i + chunk_size])
                continue

            if not current:
                current = paragraph
            elif len(current) + 2 + len(paragraph) <= chunk_size:
                current = f"{current}\n\n{paragraph}"
            else:
                chunks.append(current)
                # Recouvrement : on repart avec la fin du morceau précédent.
                tail = current[-overlap:] if overlap else ""
                current = f"{tail}\n\n{paragraph}".strip() if tail else paragraph

        if current:
            chunks.append(current)
        return chunks or [text[:chunk_size]] if text.strip() else []

    def add_document(self, filepath):
        """
        Ajoute ou met à jour un document dans la base de connaissances.

        Idempotent : réindexer un fichier inchangé ne fait rien, et
        réindexer un fichier modifié remplace ses anciens morceaux au
        lieu de s'y ajouter. Sans ça, relancer l'indexation doublait
        silencieusement le contenu, et la recherche remontait deux fois
        le même extrait.

        Retourne True si quelque chose a été écrit, False sinon.
        """
        if not os.path.exists(filepath):
            print(f"Fichier introuvable: {filepath}")
            return False

        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()

        return self.add_text(text, os.path.basename(filepath))

    def add_text(self, text, doc_id):
        """
        Indexe un texte déjà lu, sous le nom `doc_id`.

        Séparé de add_document() pour que les formats qui ne se lisent
        pas avec open() — PDF demain — passent par le même chemin
        d'indexation, avec la même idempotence.
        """
        if not text.strip():
            print(f"Document vide, ignoré: {doc_id}")
            return False

        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        chunks = self._chunk_text(text)

        if self.use_chroma and self.collection:
            if self._already_indexed(doc_id, digest):
                return False
            # Le document a changé (ou est nouveau) : ses anciens morceaux
            # partent d'abord. Un document raccourci laisserait sinon
            # derrière lui des morceaux orphelins, toujours consultables.
            self._forget(doc_id)
            # Plus besoin de calculer les embeddings manuellement — la
            # fonction d'embedding déclarée sur la collection (Ollama)
            # est appelée automatiquement par ChromaDB.
            self.collection.add(
                documents=chunks,
                metadatas=[
                    {"source": doc_id, "chunk": i, "sha": digest}
                    for i in range(len(chunks))
                ],
                ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
            )
        else:
            self.chunks = [c for c in self.chunks if c[0] != doc_id]
            self.chunks.extend([(doc_id, i, chunk) for i, chunk in enumerate(chunks)])

        if doc_id not in self.documents:
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