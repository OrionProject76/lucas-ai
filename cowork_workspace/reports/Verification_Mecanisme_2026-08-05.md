# Vérification du mécanisme — note de test

**Objet** : cette note ne vise pas à produire une analyse utile en
elle-même. Elle vérifie que `cowork_request_runner.ps1` déclenche bien
Claude Code en local, avec accès réel à `C:\OrionAI`, de bout en bout.
Réponses fondées uniquement sur `ROADMAP.md`.

## 1. Nombre de sections `## 5.x`

**50 sections**, de `## 5.1` à `## 5.50`.

## 2. Section la plus récente

**`## 5.50 🔴 Chasse aux dépendances à la FORME — une seconde fuite trouvée`**.

En une phrase : en cherchant systématiquement tout mécanisme du code de
production qui reconnaît une **forme d'écriture** plutôt qu'un sens (à la
demande de Cyril, après le constat de §5.49), le filtre anti-fuite de la
recherche web (`is_identifying()`) s'est révélé appliquer ses motifs IBAN
et numéro de carte à la chaîne brute — un IBAN ou un numéro de carte
recopié avec des espaces insécables ou fines (comme le fait un
copier-coller depuis un relevé bancaire) passait sans être bloqué et
partait chez DuckDuckGo, corrigé en normalisant la chaîne avant
l'application des motifs.

## 3. Deux entrées où une erreur d'instrument de mesure a été trouvée

1. **§5.31 — Fausse confirmation d'action.** Premier test conclu à tort
   « aucun Notepad ouvert » : le filtre `tasklist /FI "IMAGENAME eq
   notepad.exe"` ne voit pas le Bloc-notes du Store (process nommé
   `Notepad`, pas `notepad.exe`), alors qu'un Notepad venait réellement de
   s'ouvrir (horodaté dans `action_log`). Le texte le nomme explicitement :
   « c'était l'instrument qui était faux, pas le code ».
2. **§5.42 — La suite « unitaire » dépendait d'un Ollama vivant.** Première
   tentative de couper Ollama via la variable d'environnement `OLLAMA_HOST`
   pour vérifier l'indépendance de la suite de tests : résultat « 1120
   passés » qui ne mesurait rien, car `OLLAMA_HOST` était codé en dur dans
   `config.py` et ignorait la variable d'environnement. La section relie
   elle-même ce cas au précédent : « c'est la deuxième fois de la nuit
   qu'un instrument est faux ».

---
*Note produite automatiquement le 05/08/2026 pour valider le mécanisme de
traitement des demandes déposées dans `cowork_workspace/requests/`.*
