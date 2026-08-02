# MISSION 07 : memory/memory_palace.py

## Contexte
Couche 2 — Memory Palace 2.0. Système de mémoire à 5 types pour Luca's.

## Objectif
Créer `memory/memory_palace.py` + `tests/test_memory_palace.py`

## Spécifications
- [ ] Classe `MemoryPalace` avec 5 sous-systèmes :
  1. **Épisodique** : événements datés ("Mardi bug CSS 2h")
  2. **Sémantique** : connaissances factuelles ("préfère dark mode")
  3. **Procédurale** : comment faire ("export CSV via Excel")
  4. **Émotionnelle** : états émotionnels passés
  5. **Prospective** : choses à faire (rappels, todo)
- [ ] Stockage SQLite avec tables séparées par type
- [ ] RAG avec ChromaDB pour recherche sémantique
- [ ] API simple : `add_memory(type, content, metadata)`, `search(query, type=None)`
- [ ] Tests pytest

## Schéma SQL
```sql
CREATE TABLE episodic_memories (id, timestamp, event, details, importance);
CREATE TABLE semantic_memories (id, timestamp, fact, category, confidence);
CREATE TABLE procedural_memories (id, timestamp, task, steps, success_rate);
CREATE TABLE emotional_memories (id, timestamp, emotion, trigger, intensity);
CREATE TABLE prospective_memories (id, timestamp, task, deadline, completed);
```

## Dépendances
- `sqlite3`, `chromadb`, `sentence-transformers` (pour embeddings)

## Validation
```bash
pytest tests/test_memory_palace.py -v
```

## Notes
- Embeddings via `bge-m3` (Ollama) ou `sentence-transformers` local
- Chaque mémoire a un score d'importance (1-10)
- Recherche hybride : SQL filtré + ChromaDB sémantique
- Auto-résumé des mémoires anciennes (compression)
