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

**Formats lus** : `.pdf`, `.docx`, `.txt`, `.md`, `.markdown`, `.rst`, `.csv`,
`.json`. Les `.doc` anciens et les `.xlsx` sont signalés — la commande dit
quoi faire.



⚠️ Un PDF **scanné** (photographié, sans couche texte) est refusé avec un
message explicite plutôt qu'indexé à vide : seul un OCR le rendrait
consultable. Piste pour la v1.1.

## Rien ne sort de la machine

Les embeddings sont calculés par Ollama en local (`nomic-embed-text`), et
une question qui déclenche le RAG est forcée en local par `route()`.
Voir `CLAUDE.md` règle 3.

Ce dossier n'est pas versionné (voir `.gitignore`) : ce sont tes
documents, ils n'ont rien à faire sur GitHub.

## Ce qui est refusé d'office

**Les fichiers de secrets** — mots de passe exportés, kits de récupération,
clés privées, codes de secours. En base vectorielle, des identifiants
deviennent récupérables par une simple question, et Luca's les recopierait
dans sa réponse. Le refus se fait sur le **nom** du fichier ; c'est un
filet, pas une garantie. Ne range pas tes secrets dans un dossier indexé.

**Les journaux** — `.log`, mais aussi `log.txt`, `debug_*.txt`, `output.txt`.
Volumineux, répétitifs, sans valeur documentaire : un seul journal de 0,7 Mo
occupait 76 % de la base et rendait 35 vrais documents introuvables.

Un document légitimement volumineux qui écrase la base est **signalé**, pas
retiré : à toi de décider.
