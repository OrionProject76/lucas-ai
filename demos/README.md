# demos/

Scripts de démonstration manuelle. **Ce ne sont pas des tests.**

Ils s'exécutent pour de vrai : ouvrir des applications, capturer l'écran,
jouer du son, interroger Ollama. Ils demandent donc un environnement
complet et une intervention humaine pour juger du résultat.

Ils vivaient auparavant à la racine sous des noms en `test_*`, ce qui
avait deux conséquences : pytest les collectait — `test_server.py`
bloquait la suite en lançant uvicorn — et il fallait les exclure à la
main dans le `justfile`.

| Script | Ce qu'il fait réellement |
|---|---|
| `demo_vision.py` | Capture l'écran et le fait décrire par le VLM local |
| `demo_automation.py` | Ouvre des applications de la liste blanche |

Les vrais tests correspondants : `test_modules.py`, `test_automation.py`.
