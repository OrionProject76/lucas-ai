# BRIEF DE SESSION — MÉCANISME DE DÉMARRAGE DAEMON (sans faux positif antivirus)
**Pour : Claude Code | Rédigé par : Claude (Lead Architect) avec Cyril | Date : 10/08/2026**

---

## 1. Contexte

Le mécanisme actuel de démarrage silencieux du Daemon (tâche planifiée → `wscript.exe` → script `.vbs` caché → interpréteur Python) a été flagué par Bitdefender comme "ligne de commande malveillante" (Antivirus) et "application potentiellement malveillante" (Advanced Threat Defense). Deux exceptions avaient été ajoutées pour contourner ça — **Cyril les a retirées** par prudence sécurité, ce qui signifie que la tâche va probablement se refaire bloquer au prochain démarrage. Objectif : remplacer le mécanisme par quelque chose qui ne ressemble pas à un motif de persistance malveillante, plutôt que de dépendre d'exceptions antivirus permanentes.

## 2. Étape préalable obligatoire — comprendre pourquoi le VBS existe avant de le remplacer

Avant de changer quoi que ce soit, vérifie précisément **pourquoi** le script `.vbs` a été introduit à l'origine (probablement pour masquer la fenêtre de console qu'ouvrirait `python.exe` au démarrage). Si c'est bien l'unique raison, il existe une solution plus simple et plus propre : `pythonw.exe` (la variante sans fenêtre de Python, déjà incluse dans toute installation Python standard) ne crée **aucune fenêtre de console** par nature — il ne nécessiterait plus l'intermédiaire `wscript.exe`+`.vbs` du tout. Vérifie cette hypothèse dans le code/les scripts existants avant de partir sur cette piste comme acquise.

## 3. Objectif de la session

Remplacer le mécanisme de démarrage du Daemon pour qu'il :
- Ne déclenche plus de faux positif antivirus (objectif principal)
- Reste silencieux (pas de fenêtre visible au démarrage)
- Reste fiable au redémarrage du PC

## 4. Périmètre

- Si l'hypothèse `pythonw.exe` se confirme : remplacer la chaîne tâche planifiée → `wscript.exe` → `.vbs` par une tâche planifiée qui lance directement `pythonw.exe` avec le script du Daemon en argument — plus d'intermédiaire VBS.
- Si ce n'est pas suffisant pour une raison trouvée à l'étape préalable (le VBS fait autre chose que masquer la fenêtre) : documenter précisément ce que fait le VBS, et proposer une alternative qui couvre le même besoin sans le motif suspect (ex. tâche planifiée directe avec les bons paramètres `/rl limited` déjà en place, ou évaluer un Windows Service via `pywin32` si la complexité le justifie — à proposer en mode plan, pas à décider seul si ça implique un changement d'architecture plus large).
- Tester que la nouvelle commande `schtasks /create` ne déclenche pas la même détection "ligne de commande malveillante" — sans garantie à 100%, mais un motif plus simple (pas de `wscript.exe`+`.vbs` imbriqué) est intrinsèquement moins suspect.

## 5. Point à trancher AVEC Cyril, pas seul

Ce même motif (`wscript.exe`+`.vbs` caché) est utilisé par les **4 autres services** du projet (pas seulement le Daemon). Cette session corrige uniquement **LucasDaemon**. Avant de généraliser le correctif aux 4 autres, reviens vers Cyril avec ce que ça a donné sur le Daemon — ne pas toucher aux 4 autres services dans cette session sans validation explicite.

## 6. Contraintes

- Ne pas casser le comportement existant validé (démarrage à la connexion, `/rl limited`, silencieux).
- Si le fichier `.vbs` devient inutile, ne pas le supprimer sans le signaler clairement — le laisser en place si un doute subsiste, le retirer seulement une fois la nouvelle méthode confirmée stable.

## 7. Critères de validation

- Le Daemon démarre silencieusement (aucune fenêtre visible) après un redémarrage réel du PC.
- La commande `schtasks /create` utilisée ne déclenche pas de blocage Bitdefender lors d'un test réel (sans exception active).
- Aucune régression sur le fonctionnement réel du Daemon (mêmes vérifications que la session précédente : `LastTaskResult`, processus réels, journal).

Test réel avec redémarrage effectif du PC si possible, pas seulement une relance de tâche à chaud. Commit, `ROADMAP.md` à jour, `SESSION_LOG.md` en fin de session.
