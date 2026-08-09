# SESSION LOG — Style oral pour les réponses parlées (speak=true)

**Date** : 10/08/2026
**Détail technique complet** : `ROADMAP.md` §5.86

## Contexte

Cyril signale que la voix de Luca sonne trop littéraire pour être
naturelle à l'oral.

## Exploration (demandée explicitement avant de coder)

`speak` n'était threadé nulle part dans `core/lucas_core.py` — utilisé
uniquement côté `api/server.py`, APRÈS la génération, pour décider de
synthétiser le texte déjà produit. Aucune distinction "sera parlé / sera
affiché" n'existait dans le prompt système.

## Décision (ambiguïté posée par la demande, tranchée sans plan complet)

Une seule génération sert le texte affiché ET la voix — pas un second
appel séparé. Conséquence acceptée : en mode conversation (speak toujours
vrai), le texte affiché suit donc, lui aussi, le style oral.

## Construit

- `config.py` : `ORAL_STYLE_INSTRUCTION` (phrases courtes, pas de liste à
  puces/markdown, connecteurs oraux).
- `core/lucas_core.py` : `speak` threadé jusqu'à `_build_messages()`,
  répété au point de ré-ancrage (même logique que la règle de
  tutoiement).
- `api/server.py` : le drapeau est lu une seule fois, réutilisé pour le
  prompt ET la synthèse.
- Tests : 5 nouveaux (`test_oral_style_prompt.py`) + 2 tests serveur +
  correctif de 3 doublures de `ask()` qui ne connaissaient pas le nouveau
  paramètre (37 régressions trouvées et corrigées).

## Testé sur de vraies réponses générées

3 questions réelles comparées speak=False/speak=True via un client
WebSocket direct contre le serveur réel. Différence la plus nette : les
listes à puces disparaissent en mode oral (remplacées par des phrases
enchaînées), les phrases sont plus courtes, quelques connecteurs oraux
réels apparaissent ("mais", "donc", "faut").

**Verdict honnête** : amélioration réelle sur la structure. Le
vocabulaire reste par endroits technique/écrit sur des sujets techniques
— le modèle local suit mieux une consigne de structure qu'une consigne de
registre fin. Pas présenté comme totalement réglé.

## Deux leçons de méthode trouvées en testant

1. Des questions de test tirées à quelques secondes d'intervalle ont
   confondu le modèle (réponse dupliquée sur une question sans rapport)
   — corrigé en espaçant les questions de test, sans rapport avec le
   style oral lui-même.
2. **Chaque message de test envoyé via le vrai WebSocket s'enregistre
   dans la vraie mémoire de Cyril.** 26 lignes de test ont été identifiées
   précisément (par correspondance exacte du texte envoyé) et supprimées
   de `memory/lucas_memory.db` — sa conversation réelle juste avant
   ("salut", 16h07) n'a pas été touchée. Signalé à lui explicitement,
   pas seulement corrigé en silence.

Son téléphone était connecté et actif pendant une partie de ce test (vu
dans les logs serveur) — aucun redémarrage n'a eu lieu pendant cette
fenêtre, seule sa mémoire de conversation a été temporairement partagée
avec mes questions de test le temps de les retirer.
