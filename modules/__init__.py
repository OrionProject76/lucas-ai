# modules/ — modules fonctionnels de Luca's (RAG, vision, voix, web, finance)
#
# Ce fichier rend le dossier un vrai package Python, comme core/, ui/, api/
# et memory/. Sans lui, mypy voyait chaque fichier sous deux noms de module
# ("rag_manager" et "modules.rag_manager") et refusait d'analyser le projet.
