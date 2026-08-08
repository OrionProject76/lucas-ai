# Revue a posteriori — Briques 2 (OS Controller) et 1 (routeur cloud)

**Date** : 08/08/2026
**Objet** : Briques 2 et 1 déjà committées et poussées sous mode Auto (pas
d'approbation diff par diff). Cyril a demandé une vérification a posteriori
sur 4 points précis, en conditions réelles quand c'était possible — pas une
relecture générale du code.

**Résultat : rien d'anormal trouvé sur les 4 points.**

---

## 1. `move_file` vérifie-t-il `allowed_directories` sur source ET destination ?

**Oui, confirmé par le code et par un test réel.**

`core/os_controller.py::move_file()` — `source_path = self._check(source)` et
`dest_path = self._check(destination)` sont deux appels séparés et
inconditionnels, chacun passant par `_resolve_and_check()` (résolution de
chemin + vérification d'appartenance). Aucun chemin de code ne saute l'un ou
l'autre.

Vérifié en plus par un test réel (pas seulement `tmp_path` synthétique) :
fichier créé dans `C:\Users\PC\Documents`, tentative de déplacement vers
`C:\Windows\System32` → `PathNotAllowed` levée, fichier resté en place.
Déplacement légitime vers un sous-dossier de `Documents` → réussi. Dossier
témoin entièrement nettoyé après coup.

## 2. Le pont Qt (confirmation destructive) fonctionne-t-il en conditions réelles ?

**Oui — vérifié avec une VRAIE `QMessageBox` (pas mockée cette fois), au-delà du test unitaire déjà existant.**

Le test automatisé de la suite (`test_confirm_destructive_from_a_background_thread_does_not_deadlock`)
utilise déjà un vrai `QThread` distinct et un vrai `QMetaObject.invokeMethod`
bloquant — seul `QMessageBox.question` y est mocké (limite documentée dans le
test lui-même).

Vérification supplémentaire faite aujourd'hui : script à part avec la vraie
`QMessageBox.question()`, cliquée via l'API Qt légitime
(`QApplication.activeModalWidget()` + `.click()` — introspection sur un
widget de notre propre process, aucun P/Invoke). Deux essais :

- 1er essai : ma boucle de pompage manuelle (`while ...: processEvents()`)
  s'est bloquée — une vraie `QMessageBox.exec()` ouvre sa propre boucle
  d'événements imbriquée, une boucle externe manuelle reste coincée dedans.
  **Défaut de mon script de vérification, pas du code réel.**
- 2e essai, corrigé (vraie boucle `app.exec()` + `QTimer` périodique, qui
  lui est traité par la boucle imbriquée) : la vraie boîte de dialogue
  apparaît, est détectée et cliquée, la valeur `True` revient correctement
  jusqu'au thread appelant après `worker.wait()`. Une lecture faite *avant*
  la jointure complète du thread affichait `None` — artefact du script
  (timing de synchronisation du signal `finished` vs le join explicite),
  pas un défaut de `ui/main_window.py::confirm_destructive()`.

Aucun changement de code nécessaire suite à cette vérification.

## 3. `is_sensitive()` s'exécute-t-il avant toute vérification de budget, sans contournement possible ?

**Oui, confirmé.** `core/router.py::route()` — `is_sensitive(text)` est le
tout premier test de la fonction, retour immédiat en `"local"` si vrai,
avant tout accès à `KEYWORDS_CLOUD`/`cloud_budget_available()`. Aucune
branche alternative dans `route()`.

Vérifié aussi qu'il n'existe **qu'un seul point d'appel** de `ask_cloud()`
dans tout le projet (`core/lucas_core.py:1301`), gardé par
`destination == "cloud"` où `destination = route(...)` — `route()` est donc
le seul et unique passage obligé vers le cloud, pas de chemin parallèle.

## 4. Le plafond de coût déclenche-t-il vraiment la bascule locale à 100 % ?

**Oui, vérifié avec le budget par défaut réel (10€) et des coûts calculés
avec les tarifs réels claude-opus-5, pas seulement le test unitaire à
0,01€.**

Script de vérification : accumulation de coûts réalistes (~0,05€/appel)
jusqu'à la limite, puis test de bord exact — à 9,99€ (`cloud_budget_available()
== True`), à 10,00€ pile (`== False`), à 15,00€ (`== False`). Confirmé aussi
que `route()` elle-même (pas seulement la fonction interne) bascule sur
`"local"` pour une question complexe une fois le budget épuisé. Avertissement
à 80 % vérifié de la même façon (None sous 80%, message au-dessus).

---

## Ce qui n'a pas été retouché

Aucun fichier source modifié suite à cette revue — les 4 points sont
conformes. Seule modification liée à cette session : `pyproject.toml`
(nouveau) rendant explicite la règle ruff B006, demande séparée de Cyril,
sans rapport avec cette revue.
