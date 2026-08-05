import hashlib
import os
import re

import requests

from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DATE_SEARCH_MAX_CANDIDATES,
    OLLAMA_HOST,
    RAG_CONFIDENT_DISTANCE,
    RAG_MAX_DISTANCE,
    RAG_MAX_DISTANCE_DATED,
)
# ⚠️ core.dates est importé PARESSEUSEMENT dans les méthodes : core/__init__
# charge LucasCore, qui charge ce module — un import en tête d'ici ferme la
# boucle. Même motif que core/router.py avec core.intent.

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

    # Version du format d'indexation. À INCRÉMENTER dès que le découpage
    # ou la mise en forme des morceaux change : elle entre dans l'empreinte
    # de add_text(), donc l'incrémenter suffit à forcer la réindexation de
    # toute la base au prochain passage.
    #   1 — découpage brut tous les 500 caractères
    #   2 — découpage par paragraphes, avec recouvrement
    #   3 — nom du fichier ajouté en tête de chaque morceau (01/08/2026)
    #   4 — métadonnée « periods » pour la recherche hybride (01/08/2026)
    #   5 — PDF extraits en mode « layout » : les documents en colonnes
    #       (bulletins, factures) gardent l'association libellé → valeur
    _FORMAT_VERSION = 5

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
        # ⚠️ "orion_docs" reste tel quel, volontairement, malgré le
        # renommage technique du 02/08/2026 (voir ROADMAP §6) : c'est le nom
        # de la collection ChromaDB PERSISTÉE sur le disque de Cyril. La
        # renommer en "lucas_docs" ferait chercher une collection qui
        # n'existe pas — tous ses documents déjà indexés deviendraient
        # invisibles sans réindexation complète, pour un gain purement
        # cosmétique. Nom de stockage interne, jamais vu par Cyril.
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

        # ⚠️ La version du FORMAT entre dans l'empreinte. Sans elle, un
        # changement de découpage ou de préfixe laisserait la base
        # inchangée : le contenu source est le même, donc add_text()
        # conclurait « inchangé » et personne ne verrait que la base est
        # restée à l'ancien format.
        digest = hashlib.sha256(
            f"{self._FORMAT_VERSION}\n{text}".encode("utf-8")
        ).hexdigest()[:16]

        # ⚠️ Le NOM DU FICHIER est ajouté en tête de chaque morceau.
        #
        # Mesuré sur les documents réels de Cyril : « Résume-moi mon CV »
        # remontait « Demande d'autorisation d'absence » (0,303) et jamais
        # le CV, dont le contenu ne prononce jamais le mot « CV ». Avec le
        # nom en tête, le bon document sort premier (0,282), et les quatre
        # questions testées s'améliorent — « ma demande d'autorisation
        # d'absence » passe de 0,308 à 0,172.
        #
        # C'est l'information que Cyril utilise pour désigner un document,
        # et elle était la seule à ne pas être indexée.
        chunks = [
            f"[Document : {doc_id}]\n{morceau}" for morceau in self._chunk_text(text)
        ]

        # Périodes du document, pour la recherche hybride. Extraites du
        # NOM comme du contenu : chez Cyril, c'est le nom qui porte
        # l'information la plus fiable (« bulletin-de-paie-du-010725 »),
        # le contenu d'un PDF de paie étant souvent en morceaux.
        # Stockées en chaîne : ChromaDB n'accepte pas de liste en
        # métadonnée, et le filtrage se fait donc en Python.
        from core.dates import extract_periods

        periodes = ",".join(sorted(extract_periods(f"{doc_id}\n{text}")))

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
                    # agent_id : hook multi-agents (IDEAS.md #38, CLAUDE.md
                    # règle 12), posé le 03/08/2026 — aucune recherche ne
                    # filtre dessus aujourd'hui, un seul agent existe.
                    {
                        "source": doc_id,
                        "chunk": i,
                        "sha": digest,
                        "periods": periodes,
                        "agent_id": "orion_main",
                    }
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

    def search(self, query, top_k=3, max_distance=RAG_MAX_DISTANCE, with_distances=False):
        """
        Recherche les passages les plus pertinents.

        `with_distances=True` rend des couples `(texte, distance)` au lieu
        des seuls textes. La distance vaut `None` sur le chemin de repli
        textuel, qui n'en produit aucune — `None` veut dire « inconnue »,
        pas « nulle », et l'appelant doit pouvoir faire la différence.

        ⚠️ Ajouté le 05/08/2026 (confiance/provenance étendue au RAG,
        ROADMAP.md §5.35). Le défaut reste `False` : tous les appelants
        existants reçoivent exactement ce qu'ils recevaient avant.

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
            # ── Recherche hybride ─────────────────────────────────────
            #
            # ⚠️ Quand la question nomme une période, le sémantique seul
            # se trompe de document. Mesuré : « salaire net en juillet
            # 2025 » remontait les bulletins de février, avril et janvier
            # 2026, alors que celui de juillet 2025 est bien indexé. Pour
            # un modèle d'embeddings, deux dates de bulletin de paie sont
            # sémantiquement voisines — le mois demandé est exactement
            # l'information qu'il écrase.
            #
            # On élargit donc le filet, puis on filtre sur la date en
            # Python. L'ordre sémantique est conservé à l'intérieur des
            # documents retenus : la date décide QUI est éligible, le
            # sémantique décide de l'ordre.
            from core.dates import extract_query_period
            from core.dates import matches as matches_period

            periode = extract_query_period(query)
            # ⚠️ Quand une période est nommée, on interroge TOUTE la base,
            # pas un top-N élargi. Mesuré : avec 30 candidats sur 275, un
            # seul morceau de juillet 2025 passait le filtre — celui des
            # congés — et le morceau portant « NET SOCIAL 1625.68 »
            # restait invisible alors qu'il est 2e parmi ceux de juillet.
            # Le filtre par date est le critère principal ; le sémantique
            # ne doit pas trancher avant lui.
            demande = (
                min(self.collection.count(), DATE_SEARCH_MAX_CANDIDATES)
                if periode
                else top_k
            )

            results = self.collection.query(
                query_texts=[query],
                n_results=demande,
                include=["documents", "distances", "metadatas"],
            )
            documents = (results.get("documents") or [[]])[0]
            distances = (results.get("distances") or [[]])[0]
            metadatas = (results.get("metadatas") or [[]])[0] or [{}] * len(documents)

            retenus = [
                (doc, distance)
                for doc, distance, meta in zip(documents, distances, metadatas)
                if periode is None or matches_period(periode, meta.get("periods", ""))
            ]

            # ⚠️ Si AUCUN document ne couvre la période, on ne se rabat
            # PAS sur les meilleurs résultats sémantiques : ce serait
            # exactement le bug d'origine, et Luca's répondrait sur un
            # autre mois sans le dire. Mieux vaut « je n'ai rien pour
            # juillet 2025 » qu'une réponse sur février 2026.
            if periode and not retenus:
                return []

            retenus = retenus[:top_k]
            if max_distance is None:
                return retenus if with_distances else [doc for doc, _ in retenus]

            # ⚠️ Le seuil est ASSOUPLI quand une période a filtré.
            #
            # Les deux verrous n'ont pas le même rôle. Le seuil sert à
            # écarter un document hors sujet ; le filtre par date a déjà
            # fait ce travail, et mieux — « juillet 2025 » ne laisse
            # passer que le bulletin de juillet 2025. Lui appliquer en
            # plus un seuil serré revient à jeter la bonne réponse.
            #
            # Mesuré : après passage des PDF en mode « layout », le
            # morceau portant « NET A PAYER ... | 1647.68 » sort 1er des
            # morceaux de juillet 2025, à 0,365 — au-dessus du seuil
            # général de 0,33, donc rejeté. Luca's recevait le bon
            # document, le bon extrait, et n'en voyait rien.
            #
            # Le risque résiduel est d'injecter un extrait peu pertinent
            # DU BON document ; c'est sans commune mesure avec un extrait
            # du mauvais mois, que le filtre continue d'interdire.
            if periode:
                max_distance = RAG_MAX_DISTANCE_DATED

            gardes = [(doc, d) for doc, d in retenus if d <= max_distance]
            return gardes if with_distances else [doc for doc, _ in gardes]

        # Fallback : recherche texte simple. Pas de distance ici — une
        # sous-chaîne trouvée est une correspondance exacte, donc pertinente.
        query_lower = query.lower()
        matches = []
        for doc_id, i, chunk in self.chunks:
            if query_lower in chunk.lower():
                matches.append(chunk)
        matches = matches[:top_k]
        return [(m, None) for m in matches] if with_distances else matches

    def get_context(self, query, top_k=3):
        """
        Retourne le contexte formaté pour le LLM, ou une chaîne VIDE si
        aucun extrait n'est assez proche.

        La chaîne vide est significative : l'appelant
        (LucasCore._build_messages) n'ajoute alors aucun bloc au prompt.
        L'ancienne version renvoyait la phrase « Aucun document pertinent
        trouvé. », qui était injectée telle quelle et occupait un tour de
        contexte pour ne rien dire.
        """
        results = self.search(query, top_k, with_distances=True)
        if not results:
            return ""

        # ⚠️ Confiance/provenance étendue au RAG (05/08/2026, ROADMAP.md
        # §5.35). Aucune migration de schéma : ChromaDB n'a pas de colonne
        # `confidence`, mais la DISTANCE est déjà calculée à chaque
        # recherche — et elle était jetée juste avant d'arriver ici.
        #
        # Pourquoi ça compte : le seuil d'acceptation est ASSOUPLI à 0,50
        # quand une période a filtré (voir search()), contre 0,34 sinon.
        # Un extrait retenu à 0,47 est explicitement « un extrait
        # peut-être peu pertinent DU BON document » — présenté sans
        # nuance, il a exactement la même autorité qu'un extrait à 0,08.
        # C'est la situation que core/memory_weighting.py corrige déjà
        # pour l'historique, et le même remède s'applique : le DIRE, plutôt
        # que pondérer un nombre qui n'existe pas côté LLM.
        #
        # `distance is None` = chemin de repli textuel : une sous-chaîne
        # trouvée est une correspondance exacte, jamais incertaine.
        morceaux = []
        for i, (texte, distance) in enumerate(results):
            incertain = distance is not None and distance > RAG_CONFIDENT_DISTANCE
            marque = " ⚠️ correspondance faible, à confirmer" if incertain else ""
            morceaux.append(f"[Extrait {i+1}{marque}] {texte[:300]}...")

        context = "\n\n".join(morceaux)
        entete = "Contexte trouvé dans les documents:"
        if any(d is not None and d > RAG_CONFIDENT_DISTANCE for _, d in results):
            entete += (
                "\n(Les extraits marqués « correspondance faible » sont les "
                "moins sûrs : ne les présente PAS comme des faits établis, "
                "et dis à Cyril que tu n'es pas certain qu'ils répondent à "
                "sa question.)"
            )
        return f"{entete}\n{context}"


if __name__ == "__main__":
    rm = RAGManager()
    rm.add_document("data/sample_document.txt")
    print(rm.get_context("intelligence artificielle"))