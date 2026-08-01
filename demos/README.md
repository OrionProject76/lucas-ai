# demos/

Scripts de démonstration manuelle. **Ce ne sont pas des tests.**

Ils s'exécutent pour de vrai : ouvrir des applications, capturer l'écran,
jouer du son, interroger Ollama. Ils demandent donc un environnement
complet et une intervention humaine pour juger du résultat.

Ils vivaient auparavant à la racine sous des noms en `test_*`, ce qui
avait deux conséquences : pytest les collectait — `test_server.py`
bloquait la suite en lançant uvicorn — et il fallait les exclure à la
main dans le `justfile`.

| Script | Ce qu'il fait réellement | Dépendances |
|---|---|---|
| `demo_avatar.py` | Affiche l'avatar et ses 5 modes, pour juger l'esthétique | aucune |
| `demo_voices.py` | Prononce la même phrase avec les 5 voix, pour comparer | réseau (edge) |
| `demo_vision.py` | Capture l'écran et le fait décrire par le VLM local | Ollama + llava |
| `demo_automation.py` | Ouvre des applications de la liste blanche | aucune |

`demo_avatar.py` répond à une question que les tests ne peuvent pas
trancher : les tests prouvent que les cinq modes diffèrent, que la
respiration avance et que les fondus se terminent — pas que c'est beau,
ni que le rythme est bon.

Les vrais tests correspondants : `test_modules.py`, `test_automation.py`.
