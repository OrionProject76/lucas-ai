# BRIEF DE SESSION — PONT CAPTEURS TÉLÉPHONE → LUCA'S PC (micro + appareil photo)
**Pour : Claude Code | Rédigé par : Claude (Lead Architect) avec Cyril | Date : 12/08/2026**
**⚠️ À lancer APRÈS le brief BRIEF_RETRAIT_CAPTURE_ECRAN_MOBILE.md — les deux touchent au même code mobile (tiroir Vision, pont audio), ne jamais les faire tourner en parallèle.**

---

## 1. Contexte

Le PC de Cyril n'a pas encore de webcam ni de micro (matériel prévu, pas encore acheté — D-6 au catalogue). En attendant, Cyril veut pouvoir utiliser **les capteurs de son téléphone (micro + appareil photo) comme yeux et oreilles de Luca's côté PC** : il parle dans le téléphone ou montre quelque chose à la caméra, et c'est le Luca's du PC (session desktop PySide6) qui entend, voit et répond — pas seulement la PWA mobile.

**Ce qui existe déjà et doit être réutilisé, pas reconstruit** : le pont audio téléphone→serveur (mode vocal continu, §5.83+), le pipeline caméra→serveur (capture photo mobile), le WebSocket TTS. Tout le trajet téléphone→serveur fonctionne. Ce qui manque : que le **résultat arrive dans la session PC** (l'app PySide6) au lieu de rester dans la boucle PWA mobile.

## 2. Objectif de la session

Quand Cyril utilise le micro ou la caméra depuis son téléphone, la conversation/le résultat doit apparaître et vivre dans l'app desktop PySide6 — le téléphone devient un périphérique de capture pour le PC, pas un assistant autonome séparé.

## 3. Étape préalable obligatoire

Explorer comment les sessions PWA et desktop coexistent aujourd'hui côté serveur : partagent-elles déjà le même historique de conversation (même mémoire SQLite), ou sont-elles deux flux indépendants ? La réponse détermine tout le design — si l'historique est déjà partagé, le chantier est surtout une question de synchronisation d'affichage temps réel côté desktop ; si les flux sont séparés, il faut d'abord décider comment les relier. Proposer le design en mode plan AVANT d'implémenter.

## 4. Périmètre

- Un mode explicite "capteur pour le PC" côté mobile (toggle clair dans l'interface PWA, jamais un comportement par défaut silencieux) : quand il est actif, ce qui est capté par le téléphone (voix transcrite, photo) est traité comme entrée de la session PC.
- L'app desktop PySide6 affiche en temps réel ce qui arrive par ce canal (la question vocale transcrite, la photo, et la réponse de Luca's) — pas un simple enregistrement silencieux en base qu'il faudrait aller chercher.
- La réponse vocale (TTS) peut sortir côté téléphone (le PC n'a pas encore de sortie audio prévue pour ça — à confirmer en exploration : si le PC a des enceintes utilisables, proposer le choix du côté de sortie en mode plan).
- Indicateur visible côté desktop quand le mode est actif ("capteurs mobiles connectés" ou équivalent sobre).

## 5. Hors périmètre explicite

- ❌ Capture d'écran mobile — retirée par le brief précédent, ne pas la réintroduire.
- ❌ D-6 (vrais webcam/micro PC) — ce pont est la solution d'attente, pas le remplacement du plan matériel.
- ❌ D-7 (app Android native) — toujours reporté.
- ❌ Perception continue — le mode reste à activation explicite par Cyril, session par session, conformément à `VISION_LONG_TERME.md` §4.2. Pas d'écoute permanente.
- ❌ Esthétique au-delà du minimum fonctionnel (décision de Cyril du 12/08 : le visuel attend la fin du projet).

## 6. Contraintes

- RT-3 : tout le flux reste local (téléphone→serveur via le réseau local/Tailscale déjà en place, jamais par un service tiers).
- Réutiliser les pipelines existants — si un nouveau canal doit être créé, justifier en mode plan pourquoi l'existant ne suffit pas.
- Bump `CACHE_NAME` si un fichier `SHELL_FILES` est modifié.
- Le mode vocal continu mobile existant doit continuer de fonctionner à l'identique quand le mode "capteur PC" est inactif — aucune régression.

## 7. Critères de validation

- Test réel de bout en bout : Cyril parle dans le téléphone, la question ET la réponse apparaissent dans l'app desktop PC.
- Test réel photo : une photo prise du téléphone arrive dans la session PC avec l'analyse de Luca's.
- Le toggle d'activation/désactivation fonctionne dans les deux sens, testé.
- Mode vocal mobile classique toujours fonctionnel quand le mode capteur PC est éteint.

Test réel PC + mobile, captures à l'appui. Commit, `ROADMAP.md` à jour, `SESSION_LOG.md` en fin de session.
