# MISSION 08 : memory/rag_engine.py

## Contexte
Couche 2 — Retrieval Augmented Generation. Permet à Orion de récupérer des infos pertinentes avant de répondre.

## Objectif
Créer `memory/rag_engine.py` + `tests/test_rag_engine.py`

## Spécifications
- [ ] Classe `RAGEngine`
- [ ] Indexation documents (txt, pdf, md, json) dans ChromaDB
- [ ] Chunking intelligent (par paragraphes, taille max 500 tokens)
- [ ] Embeddings via `bge-m3` (Ollama local) ou fallback `sentence-transformers`
- [ ] Recherche hybride : sémantique + keyword (BM25)
- [ ] Métadonnées par chunk (source, date, type)
- [ ] API : `index_document(path)`, `search(query, top_k=5)`, `query_with_context(query)`
- [ ] Tests pytest

## Dépendances
- `chromadb`, `sentence-transformers`, `PyPDF2`, `python-markdown`

## Validation
```bash
pytest tests/test_rag_engine.py -v
```

## Notes
- ChromaDB persistant dans `data/chromadb/`
- Chunk overlap de 50 tokens pour ne pas couper les idées
- Métadonnées : source_file, page_num, created_at, doc_type
- `query_with_context` retourne les chunks + prompt formaté pour le LLM
