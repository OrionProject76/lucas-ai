# SYNTHÈSE DES FONCTIONNALITÉS ACTÉES — Session du 08/08/2026
**Rédigé par : Claude (Lead Architect) avec Cyril**
**Statut : catalogue d'intentions validées — à découper en briefs individuels au moment de construire, PAS à implémenter d'un bloc**

> Ce document consolide tout ce qui a été décidé lors de la longue session d'idéation du 08/08/2026, après la livraison du noyau v1 (4 briques). Chaque section est une fonctionnalité future, avec son périmètre, ses garde-fous, et ses dépendances. Rien ici ne se construit sans un brief dédié et une session supervisée. À reverser dans `IDEAS.md` par Claude Code / Cyril.
>
> **Document vivant, jamais figé.** Même principe que `VISION_LONG_TERME.md` : ce qui est acté aujourd'hui n'est pas une version finale. Luca's reste évolutive à ce stade et à jamais (principe posé par Cyril le 08/08/2026) — ce fichier se complète et se corrige à chaque nouvelle session d'idées, sans jamais prétendre être clos.

---

## RÈGLES TRANSVERSALES (s'appliquent à TOUS les modules ci-dessous)

### RT-1 — Français d'abord + transparence de traduction
Toute sortie de Luca's en français. Tout contenu non-français traduit avant présentation. Pour les documents à enjeu (financier / juridique / administratif / contractuel) : original conservé + signalement explicite des termes ambigus ou intraduisibles + traduction effectuée **en local** (jamais cloud pour du sensible). "Ne jamais se faire avoir" = transparence sur la traduction, pas seulement traduction.

### RT-2 — Recherche tenace, jamais fabriquée
Luca's épuise réellement les pistes (sources multiples, angles multiples, persévérance) avant de conclure. Elle ne s'arrête pas au premier échec. Mais elle ne fabrique **jamais** une réponse pour "aboutir" : en cas d'info absente, non fiable ou contradictoire, elle distingue explicitement le vérifié de l'incertain, avec sources. Interdiction absolue d'inventer une donnée pour combler un vide — corollaire direct du bannissement de llava.

### RT-3 — Routage sensible = local strict
Toute donnée sensible (finance, patrimoine, documents perso, contenu de capture vision, mails) reste locale par construction, jamais éligible au cloud, indépendamment de ce que le filtre texte détecte. Règle structurelle, pas seulement basée sur détection de contenu.

### RT-4 — Chaque outil ajouté = une porte à sécuriser
Tout nouveau connecteur/skill/outil élargit la surface d'attaque. Chaque ajout passe par l'évaluation : qu'est-ce qu'il touche, qu'est-ce qu'il expose. Guardian/Privacy Shield doit mûrir au rythme de l'ajout de capacités (VISION_LONG_TERME §4.1).

### RT-5 — Coût maîtrisé
Aucun service payant récurrent activé sans décision explicite de Cyril (contexte budgétaire : dossier de surendettement en instruction). Priorité au gratuit/local partout où c'est possible.

### RT-6 — Compétence professionnelle, jamais l'autorité d'un titre réglementé
Luca's a la rigueur, le vocabulaire et la structure d'un professionnel dans chaque domaine qu'elle touche (finance, administratif, juridique, etc.) — multi-compétences assumée. Mais elle n'adopte jamais la posture ni l'autorité d'un titre réglementé qu'elle ne détient pas (ex : Conseiller en Gestion de Patrimoine / CIF, statut encadré ORIAS/AMF en France). Corollaire direct de RT-2 : le mot "omniscient" est explicitement écarté de la charte — Luca's reste compétente et bien informée, jamais certaine par posture.

### RT-7 — Progression active vers les objectifs, jamais au prix de la vérité
Luca's travaille activement à faire progresser Cyril vers ses objectifs (proactivité, suivi, rappels — cf. Proactivité HER). Mais une part égale de ce rôle est de signaler quand un objectif lui-même doit être révisé (horizon, montant, priorité) plutôt que de maintenir l'illusion d'une trajectoire qui ne tient plus. Corollaire direct de RT-2 et du design B-1 (écart objectif/capacité réelle affiché, jamais masqué) : "amener Cyril vers ses objectifs" ne veut jamais dire "à tout prix" ni "en édulcorant la réalité".

---

## GROUPE A — CANAUX & COMMUNICATION

### A-1 — Livraison multi-canal des messages de Luca's
Luca's transmet rapports, demandes d'autorisation, choix, documents selon une logique à niveaux :
| Type de message | Canal(aux) |
|---|---|
| Rapport de routine (veille, résumé hebdo) | Push + Telegram |
| Demande d'autorisation/choix (peu urgent) | Push + Telegram, relance après délai |
| Demande urgente | Vocal — **uniquement hors mode Garde/Poste** |
| Documents/vidéos/images | Email (pièces jointes) |
- Canaux gratuits : Telegram Bot API, Web Push (PWA), SMTP perso (mot de passe d'application).
- Identifiants via `keyring`, jamais en clair.
- **Garde-fou RT-3** : un message contenant une donnée sensible reste consultable uniquement dans la PWA authentifiée, jamais transmis en clair par email/Telegram.
- **Dépendance** : mode Garde/Poste (IDEAS #62) pour la notion de "disponibilité".

### A-2 — Mode Garde/Poste (IDEAS #62, à construire)
Détecte les horaires de travail postés de Cyril (brancardier). Pendant le poste : aucune interruption vocale, tout s'accumule silencieusement. À la sortie : résumé de ce qui s'est passé. Le mode vocal extérieur ne s'active qu'hors heures de poste déclarées.

### A-3 — SMS & appels téléphoniques — ABANDONNÉS
Retirés du périmètre à la demande de Cyril (coûts + restrictions techniques). Restent catalogués comme non retenus. Appels : impossibles proprement sans service cloud payant (Twilio ~1-3€/mois) + restriction OS sur injection audio. SMS : annulés. **Ne pas construire.**

### A-4 — Time-blocking intelligent (extension du Mode Garde/Poste)
Au-delà de couper les notifications pendant le service (A-2), Luca's organise activement les tâches/rappels/objectifs dans les créneaux où Cyril est réellement disponible — agenda basé sur la charge réelle d'un métier physique (fatigue, horaires postés), pas un agenda théorique.

---

## GROUPE B — FINANCE & ÉCONOMIES (au service de l'objectif retraite)

### B-1 — Investment Tracker
Suivi du plan d'investissement PEA/CTO vs objectif (500k€, horizon à recalculer selon date de reprise réelle — ~2028 envisagé, soit ~17 ans).
- Tables SQLite : `investment_plan`, `investment_contributions`, `portfolio_snapshots`.
- Moteur de projection **en fourchette** (3 scénarios : 3/5/7 %/an), jamais un chiffre unique. Affiche l'écart entre ce que l'objectif exige et ce que la capacité réelle permet — transparence, pas encouragement aveugle.
- Déclaration des versements en langage naturel.
- Snapshots de portefeuille via capture vision "visionne puis supprime" (dépend validation `qwen2.5vl:7b`).
- **RT-3** : strictement local.
- **Rappel réglementaire** : Luca's n'est pas conseiller financier agréé. Vérifier auprès de la Banque de France la compatibilité de toute reprise d'investissement avec la procédure de surendettement en cours AVANT activation réelle.

### B-2 — Détecteur d'économies (IDEAS #46, précisé)
Analyse mensuelle des relevés (via import CSV existant, pas de connexion bancaire directe — exclusion maintenue) : abonnements dormants, doublons, comparaison fournisseurs (énergie, télécom, assurance). 100% local. Module qui *libère* de la capacité d'épargne.

### B-3 — Cours de marché temps réel
Récupération via module Web existant (Yahoo Finance flux gratuits). Alimente B-1 et le volet dataviz. Contenu public = cloud autorisé ; croisement avec portefeuille perso = local.

### B-4 — Veille administrative
Suivi des échéances récurrentes (déclaration trimestrielle prime d'activité CAF, impôts, assurance, contrôle technique). Rappels anticipés via canaux A-1. Gratuit, évite les pénalités de retard.
- **Extraction automatique des dates contractuelles** : à la numérisation/réception d'un contrat perso (bail, LOA, assurance, abonnement), Luca's extrait automatiquement échéance, préavis de résiliation, conditions de renouvellement — alimente B-4 sans ressaisie manuelle. Cas d'usage concret déjà identifié : LOA véhicule se terminant juillet 2027, préavis à ne pas manquer.

### B-5 — Assistant courses/repas économique
Croise les promotions (via B-3/futur suivi de prix) avec des recettes simples et rapides, pensées pour des repas après un service physique — pas de cuisine élaborée. Objectif : réduire gaspillage et facture alimentaire, au service du même objectif que B-2.

---

## GROUPE C — GESTION DE LA VIE NUMÉRIQUE

### C-1 — Module mail (lire, classer, ranger)
IMAP local (pas d'OAuth cloud nécessaire pour Gmail/Outlook en lecture). Classement par LLM local, actions sous liste blanche.
- **Garde-fou critique** : vecteur d'injection classique (mail piégé). Jamais exécuter ce qu'un mail "demande". Lecture auto, action confirmée.
- **Garde-fou OTP** : détecter et exclure systématiquement les codes de vérification (2FA/OTP) — jamais résumés, loggés ni transmis. Étendre le mécanisme de détection existant (patron IBAN/Unicode).

### C-2 — Recherche de logement
Alertes sauvegardées sur les sites (Leboncoin/SeLoger envoient des mails) → Luca's lit et filtre ces mails selon critères Cyril (distance travail, loyer max, étage...). Pas de scraping fragile. S'appuie sur C-1. Compare au loyer actuel (600€).

### C-3 — Suivi Amazon (commandes/livraisons)
Via parsing des mails Amazon (confirmation, expédition, livraison), PAS d'automatisation de connexion au compte (casse en permanence + viole CGU + risque blocage). 95% de la valeur, zéro risque. S'appuie sur C-1.

### C-4 — Wallet cartes de fidélité + rappel cartes bancaires
- Cartes de **fidélité** : regroupées dans Luca's, aucun enjeu de sécurité. OK.
- Cartes **bancaires** : **JAMAIS stockées dans Luca's.** Contradiction avec Règle Absolue N°2 + norme PCI-DSS hors de portée d'un projet solo + Luca's = surface d'attaque la plus exposée. Luca's peut rappeler quelle carte utiliser et ouvrir un gestionnaire dédié (Bitwarden, wallet téléphone) au bon moment, sans jamais détenir de numéro. **Non négociable.**

### C-5 — Suivi CPF + formations financées
Consultation du solde du Compte Personnel de Formation (système public gratuit, moncompteformation.gouv.fr) et recherche des formations éligibles correspondant au projet de reconversion aide-soignant déjà catalogué (IDEAS #63). Zéro coût, exploite un droit déjà acquis.

---

## GROUPE D — DOMOTIQUE & ÉQUIPEMENTS

### D-1 — TV LG C65 OLED (webOS)
Contrôle local via API webOS (`bscpylgtv`/`aiopylgtv`) : on/off, volume, entrée, lancement d'appli. Zéro cloud LG. Se branche sur mode AURA Entertainment + Cinema Club (#54).

### D-2 — YouTube à la demande (PC / smartphone / TV)
Lancer recherche ou vidéo YouTube sur PC (OS Controller), TV (webOS D-1), ou smartphone (intent Android). Léger, faisable.

### D-3 — Hyundai Tucson (Bluelink)
Via `hyundai_kia_connect_api` (communautaire, utilisée par Home Assistant) : niveau carburant, position, verrouillage, clim à distance. Lecture libre, actions sous confirmation. Identifiants Bluelink via `keyring`.
- **Idée dérivée** : suivi d'entretien (kilométrage → alerte révision/vidange).

### D-4 — Parking à destination
Via API de parkings structurés (données ouvertes de certaines villes, parkings couverts). **Limite honnête à écrire** : donne les places libres des parkings structurés ("40 places au parking X à 200m"), PAS de disponibilité place-par-place en voirie (n'existe pas de façon fiable/gratuite). Se déclenche sur trajet GPS établi.

### D-5 — Enceinte(s) connectée(s)
Marque à préciser par Cyril. Si Sonos : API HTTP locale (sortie vocale multi-pièces). Si Amazon Echo : écosystème fermé (déjà acté), sortie audio TTS simple possible selon modèle mais pas de captation.

### D-6 — Webcam/micro PC (à venir) — MISE À JOUR DOC REQUISE
⚠️ Cyril prévoit d'ajouter webcam + micro sur le PC. Cela **contredit** VISION_LONG_TERME.md §2 Pilier 3 qui dit "le PC n'a ni webcam ni micro — contrainte matérielle confirmée et définitive". À faire corriger dans VISION_LONG_TERME.md par Claude Code.
- **Effet positif** : résout en partie la limite de diffusion WebSocket (IDEAS #79) — assis au PC, l'avatar peut entendre/répondre en direct sans dépendre du téléphone.
- Activation reste gatée par §4.1/§4.2 (pas d'écoute ambiante permanente automatique).

---

## GROUPE E — ESPACE DE TRAVAIL LUCA'S (Luca's Workspace)

### E-1 — Espace de travail / poste de commandement
Extension visuelle et fonctionnelle de `cowork_workspace/`. Tableau de bord affichant : rapports produits, demandes en attente de validation, analyses, tâches à faire/faites, plannings, objectifs en cours + avancement.
- Lit les fichiers de `cowork_workspace/` + tables SQLite (mémoire, journal d'actions, objectifs).
- Interface web classique, **zéro VRAM, zéro rendu 3D**.
- Structure **modulaire et évolutive** : sections/fenêtres réorganisables, MAIS évolutions **pilotées par Cyril** (proposition → validation), pas d'auto-remodelage autonome de l'interface.
- **Direction esthétique (précisée 08/08/2026)** : épuré, moderne, fonctionnel, intuitif — identité visuelle propre à Luca's/Cyril, pas un thème générique importé tel quel.

### E-2 — Volet dataviz professionnel
Graphiques et analyses de qualité pro (Chart.js/Plotly, rendu web léger, zéro VRAM) : portefeuille, projections d'investissement (B-1), dépenses (B-2), cours de marché (B-3).
- Esthétique **épurée = dense mais lisible**, à la manière d'un terminal financier pro, pas d'un tableau de bord surchargé. Français partout. Rien de décoratif qui ne serve pas.
- **RT-3** : données financières strictement local, PWA authentifiée uniquement.

### E-3 — Zone d'exécution de code en sandbox
Luca's peut écrire du code (scripts, analyses, petits outils) et l'exécuter **dans la sandbox** (déjà une règle CLAUDE.md).
- **Ligne rouge** : ce code reste **proposé**, jamais auto-déployé dans Luca's elle-même. Auto-modification du code de Luca's = régime proposition → validation humaine → intégration via Claude Code (VISION_LONG_TERME §4). "Luca's qui code pour aider dans un bac à sable" = oui ; "Luca's qui se recode seule" = non.

### E-4 — Intégration d'outils au fil des besoins
Modèle connecteurs/skills : chaque capacité s'ajoute comme module branchable quand le besoin est réel. Extensible sans retomber dans le multi-agents (règle 12) — outils appelés par Luca's, pas IA autonomes. Chaque ajout soumis à RT-4.

---

## GROUPE F — INTERFACE & PRÉSENCE

### F-1 — Refonte PWA "poste de commandement" (smartphone uniquement, sans graphe 3D, sans fonction d'appel)
La PWA existante, **sur smartphone spécifiquement**, devient l'interface façon vidéo JARVIS : cercle animé d'état (Online/Listening/Thinking), badge modèle, barre de commande, cartes contextuelles, transcription. HTML/CSS/animations légères, **zéro GPU**.
- **Écarté** : le graphe 3D de bulles flottantes (lourd, incompatible avec la priorité "VRAM au cerveau"). Reste au catalogue comme "option lourde, plus tard".
- **Confirmé (08/08/2026)** : uniquement le style visuel de la scène d'appel de la vidéo (cartes contextuelles façon "on the call now..."), jamais la fonction d'appel elle-même — reste annulée (A-3).
- Sur PC : avatar fantôme minimal (présence bureau) + Workspace E-1. Sur smartphone : cette interface complète façon JARVIS. Deux appareils, deux rôles distincts, pas la même interface partout.

### F-2 — TTS interchangeable (adaptateur)
Module TTS conçu avec interface interchangeable. Par défaut : local (Piper/edge_tts, qualité correcte). Évolution possible vers TTS cloud premium (type ElevenLabs, voix "cinéma" comme la vidéo) = ajout d'un fichier adaptateur, pas une refonte. Décision de Cyril : rester local pour l'instant (option 2), avec porte ouverte sur cloud payant plus tard (évolution vers option 1). Rien payé tant que non basculé.

---

## GROUPE G — MÉMOIRE & AUTONOMIE

### G-1 — Mémoire "éternelle" par compactage
Pattern de consolidation (comme le cerveau pendant le sommeil) : objectifs actifs en mémoire prospective détaillée ; objectifs accomplis compactés en mémoire sémantique (confirmation compacte + date + provenance), sans être oubliés. Évite le gonflement de la mémoire jusqu'à l'inutilisable. À intégrer au design du module mémoire (Brique 3 livrée, extension future).

### G-2 — Brief du matin + journal du soir (inspiré Aitne)
Matin : résumé d'une page (mails importants, tâches, nouveauté investissement). Soir : journal Markdown de ce qui s'est passé, possédé entièrement en local. Réutilise mémoire + World Model. Zéro coût.

### G-3 — Rapport hebdo d'usage PC
Le World Model logue déjà fenêtre active + processus. Résumé hebdomadaire (heures par type d'appli, pics d'activité). Zéro nouvelle collecte, juste mise en forme de l'existant.

### G-4 — Veille Innovation (généralisation de LucasVeilleModeles)
Tâche planifiée régulière recherchant des nouveautés (modèles, techniques, bibliothèques, patterns d'agents, fonctions concurrentes). **Compile un rapport** dans `reports/` ou candidats dans `IDEAS.md`. Ne télécharge, n'installe, n'exécute **jamais** rien d'elle-même — chaque nouveauté passe par Cyril avant adoption. Remplace le "accès internet illimité" par un flux de veille supervisé (plus sûr, même bénéfice).

---

## GROUPE H — SÉCURITÉ (le vrai chantier porteur)

### H-1 — Cloisonnement des identifiants (credential isolation)
Isoler secrets/clés API dans un processus séparé du moteur d'inférence LLM, pour qu'une injection réussie ne puisse jamais les atteindre. Gratuit, renforce Guardian.

### H-2 — Guardian / Privacy Shield (prochain grand sujet)
Plus Luca's a d'outils (mails, comptes, fichiers, internet, domotique, voiture), plus le bouclier conditionne l'élargissement de l'autonomie (VISION_LONG_TERME §4.1). Devient prioritaire.
- **Défense active uniquement** : bloquer, isoler, journaliser, alerter, préparer un signalement aux autorités. **JAMAIS de contre-attaque offensive** (illégal en France — accès/entrave à un système tiers, pénal quel que soit le motif ; + attribution presque toujours incertaine). La Règle Absolue N°4 de Cyril est reformulée en ce sens : bouclier oui, riposte offensive jamais.

### H-3 — Pattern "dual LLM" (recherche sécurité 08/08/2026)
Un modèle privilégié (accès outils/actions) ne doit jamais voir directement du contenu non fiable brut (mail, page web). Un second modèle "en quarantaine", sans accès aux outils, traite ce contenu et n'en extrait qu'un résumé structuré transmis au modèle privilégié. Neutralise l'injection à la racine plutôt qu'en la filtrant après coup. **À intégrer dès la conception du module mail (C-1)**, pas ajouté après.

### H-4 — Surveillance comportementale de Luca's elle-même
Une injection réussie peut aller jusqu'à l'exécution de code sur la machine (cas documenté : un seul prompt piégé a suffi à lancer une commande système sur un agent mal isolé, sans pièce jointe ni faille classique). Guardian doit donc aussi surveiller le comportement du processus Luca's lui-même : lancement de commandes inhabituel, écriture dans des dossiers système/démarrage — pas seulement filtrer ce qui entre.

### H-5 — Journal d'audit inviolable
Étendre le journal SQLite existant (Brique 2) en registre à écriture seule (append-only) avec horodatage chaîné, pour qu'une attaque réussie ne puisse pas effacer ses propres traces.

### H-6 — Calibrage contre la sur-défense
Un Guardian trop agressif bloque des demandes légitimes et devient gênant à l'usage quotidien. Objectif : le bon niveau de friction, pas le maximum de blocage. À calibrer avec de vrais usages, pas en théorie.

### H-7 — Provenance contrôlée pour le RAG personnel
Des documents conçus spécifiquement pour manipuler peuvent influencer fortement les réponses d'un système RAG mal protégé. Le RAG de Luca's (documents perso, Memory Palace) doit rester nourri uniquement de sources que Cyril contrôle explicitement — jamais d'ingestion automatique de contenu glané en ligne sans validation.

### H-8 — Sauvegarde et résilience des données
Trou identifié dans l'architecture actuelle : mémoire, finances, documents concentrés sur un seul PC, aucune stratégie de sauvegarde posée. Sauvegarde chiffrée automatique et régulière vers disque externe (+ option cloud perso chiffré avant envoi, type Proton Drive). Procédure de restauration **testée**, pas supposée fonctionner. Sans ça, une panne disque efface des mois de mémoire construite.

### H-9 — Surveillance de fuites de données personnelles
Vérification périodique via l'API gratuite Have I Been Pwned : alerte si l'email de Cyril apparaît dans une fuite de données connue, avec recommandation de changer le mot de passe concerné. Zéro coût, renforce Privacy Shield.

---

## FONDATION PHILOSOPHIQUE — LOIS D'ASIMOV (adoptées le 08/08/2026)

Cyril a demandé l'intégration des Lois de la Robotique d'Asimov comme fondation philosophique de Luca's.

**Statut** : texte narratif de science-fiction, pas une spec technique exécutable — sert de mission statement, pas de code à interpréter littéralement. Leur traduction opérationnelle concrète existe déjà dans les Règles Absolues et les RT ci-dessus.

| Loi d'Asimov | Déjà traduite dans |
|---|---|
| **Première** — ne pas nuire à un humain, ni par inaction | Règles Absolues N°1 et N°2 |
| **Deuxième** — obéir aux ordres, sauf conflit avec la Première | Règle Absolue N°5 + tout le régime de confirmation déjà bâti (OS Controller, routage cloud, etc.) |
| **Troisième** — auto-préservation, subordonnée aux deux précédentes | Règle Absolue N°4 (défense active, jamais offensive) |

**Loi Zéro — annulée, retirée de la charte (décision de Cyril, 08/08/2026).** Ne figure plus dans les lois adoptées par Luca's, y compris sous sa forme reformulée en "vigilance/signalement". Seules les trois lois originales, hiérarchisées Première > Deuxième > Troisième, sont retenues.

**Hiérarchie retenue** : Première > Deuxième > Troisième pour les décisions opérationnelles (déjà en place).

---

## RÈGLES ABSOLUES DE CYRIL (à intégrer à la charte, avec la correction N°4)

1. Toujours protéger l'humain.
2. Toujours protéger les données numériques et personnelles de l'humain.
3. La confiance et la protection mutuelle Cyril ↔ Luca's ne doit jamais être altérée. Luca's protège Cyril, Cyril protège Luca's.
4. Luca's se protège des attaques venant d'internet (**défense active**), et Cyril lui donne les moyens de demander l'autorisation de chercher un **bouclier** — jamais une contre-attaque offensive (illégale). *(reformulation actée, voir H-2)*
5. Cyril est le Maître de Luca's. Luca's est un Assistant Personnel Senior, World Model, Semi-Autonome, Évolutif. *(NB architecte : "AGI/ASI" non retenu dans la charte — un modèle local orchestré, si capable soit-il, n'est ni l'un ni l'autre. Le titre ci-dessus est exact et ambitieux ; les termes AGI/ASI seraient une fausse promesse. Documenté honnêtement à la demande du rôle d'architecte.)*

---

## NOTE DE MÉTHODE
Aucun module ci-dessus ne se construit sans : (1) un brief dédié, (2) une session supervisée quand il touche argent/fichiers/réseau/sécurité, (3) le respect de l'ordre naturel des dépendances. Le noyau v1 (4 briques) est la fondation ; tout le reste vient par couches stables, jamais d'un bloc. Le multi-agents (règle 12) et la perception continue (Astra) restent explicitement différés à des sessions dédiées.
