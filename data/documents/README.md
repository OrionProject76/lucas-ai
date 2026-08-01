# data/documents/

Dépose ici les documents que Luca's doit pouvoir consulter — notes,
contrats, relevés, comptes rendus.

Puis lance l'indexation :

```
venv\Scripts\python.exe -m memory.index_documents
```

La commande est **relançable sans risque** : un fichier inchangé est
ignoré, un fichier modifié est réindexé, un fichier supprimé du dossier
est retiré de la base.

**Formats lus** : `.pdf`, `.txt`, `.md`, `.markdown`, `.rst`, `.csv`, `.json`,
`.log`. Les `.docx` sont signalés mais pas encore lus — la
commande dit quoi installer.

⚠️ Un PDF **scanné** (photographié, sans couche texte) est refusé avec un
message explicite plutôt qu'indexé à vide : seul un OCR le rendrait
consultable. Piste pour la v1.1.

## Rien ne sort de la machine

Les embeddings sont calculés par Ollama en local (`nomic-embed-text`), et
une question qui déclenche le RAG est forcée en local par `route()`.
Voir `CLAUDE.md` règle 3.

Ce dossier n'est pas versionné (voir `.gitignore`) : ce sont tes
documents, ils n'ont rien à faire sur GitHub.
