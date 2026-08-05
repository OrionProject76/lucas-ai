# core/router.py — décide si la question part en local (Ollama) ou en cloud
# + décide si le RAG (documents personnels) doit être consulté
# Architecture hybride : local par défaut, cloud pour les questions complexes,
# jamais de donnée sensible vers le cloud (CLAUDE.md règle 3).

import re

from core.text_utils import contains_any, fold_separators

KEYWORDS_CLOUD = [
    "analyse", "compare", "projection",
    "20 ans", "stratégie", "optimise",
]

# Mots-clés qui signalent une donnée ultra-sensible (finance personnelle,
# documents privés, identité). Ces questions restent LOCALES même si elles
# contiennent aussi un mot-clé cloud — voir route() et CLAUDE.md règle 3.
# "portfolio" et "risque" étaient dans KEYWORDS_CLOUD : ce sont des termes
# de finance perso, ils ont été déplacés ici le 01/08/2026.
KEYWORDS_SENSITIVE = [
    "portfolio", "risque", "budget", "dépense", "salaire",
    "revenu", "compte bancaire", "banque", "économies",
    "impôt", "relevé", "transaction", "iban", "crédit",
    "emprunt", "mot de passe", "carte bancaire",
    "mon contrat", "ma facture",
]

# Mots-clés qui signalent que la question porte probablement sur des
# documents personnels de Cyril plutôt que sur une connaissance générale.
#
# ⚠️ Cette liste n'est plus le mécanisme principal de déclenchement du RAG.
# Elle sert de REPLI quand core/intent.py est indisponible, et de test
# déterministe pour la décision de sécurité du TTS (route_voice). Mesurée
# sur les formulations réelles de Cyril : 50 % de couverture, et un plafond
# structurel — voir l'en-tête de core/intent.py.
KEYWORDS_RAG = [
    "document", "fichier", "mes notes", "mes docs",
    "dans le pdf", "résume le", "résume mon",
    "d'après le document", "que dit le document",
    "rappelle-moi ce que",
]

# Mots-clés qui signalent une question sur les relevés bancaires importés
# (modules/finance_manager.py) — voir should_use_finance() plus bas.
#
# ⚠️ Déterministe par choix, pas un classifieur LLM comme
# should_use_rag()/should_use_vision(). La question « faut-il consulter
# mes relevés » n'a pas la même ambiguïté que « écran ou documents » —
# domaine plus étroit, formulations plus prévisibles ("mon solde", "mes
# dépenses"...) — et rester déterministe évite de toucher au classifieur
# core/intent.py, déjà calibré et fragile à reformuler (voir son en-tête).
KEYWORDS_FINANCE = [
    "mes finances", "ma situation financière", "mon solde",
    "mes dépenses", "mon budget", "mes revenus",
    "relevé bancaire", "mes transactions", "résume mes finances",
    "combien j'ai dépensé", "combien je dépense",
]


def is_sensitive(text: str) -> bool:
    """
    Décide si la question porte sur des données ultra-sensibles (finance
    personnelle, documents privés, identité).

    ⚠️ Mots-clés, JAMAIS de classification LLM — contrairement à
    should_use_rag() et should_use_vision(), qui ont basculé sur
    core/intent.py. La distinction est le cœur de la conception :

      • se tromper sur « faut-il regarder l'écran ? » coûte une réponse
        un peu moins bonne. Un modèle est le bon outil.
      • se tromper ici envoie un relevé bancaire chez OpenAI. Ça exige un
        test déterministe, reproductible, volontairement trop large, et
        qui fonctionne même Ollama à l'arrêt.

    Voir CLAUDE.md règle 3.
    """
    return contains_any(text, KEYWORDS_SENSITIVE)


def route(text: str, context: str = "") -> str:
    """
    Décide si la question part en local (Ollama) ou en cloud.

    Ordre de priorité — le local est le défaut sûr, le cloud l'exception :
      1. donnée sensible détectée  -> local, même si un mot-clé cloud est
         présent (« analyse mon portfolio » reste local)
      2. question sur les documents personnels (RAG) -> local
      3. question sur le contenu de l'écran -> local
      4. question complexe (mot-clé cloud) -> cloud
      5. tout le reste -> local

    Voir CLAUDE.md règle 3 pour la règle projet correspondante.
    """
    if is_sensitive(text):
        return "local"
    if should_use_rag(text, context):
        return "local"
    # L'image ne part jamais au cloud, mais sa DESCRIPTION en dirait tout
    # autant : « une fenêtre de banque affichant un solde de 3200 € ».
    if should_use_vision(text, context):
        return "local"

    if contains_any(text, KEYWORDS_CLOUD):
        return "cloud"
    return "local"


# Mots-clés qui signalent que la question porte sur ce qui est affiché à
# l'écran.
#
# ⚠️ Repli uniquement, comme KEYWORDS_RAG : le déclenchement passe
# désormais par core/intent.py. Cette liste ne peut structurellement pas
# attraper « c'est écrit quoi ? » ni « montre-moi ce qu'il y a marqué là »,
# qui ne nomment l'écran nulle part.
KEYWORDS_VISION = [
    "à l'écran", "a l'écran", "sur mon écran", "mon écran",
    "que vois-tu", "qu'est-ce que tu vois", "tu vois quoi",
    "regarde mon écran", "regarde ça", "regarde cette",
    "cette erreur", "ce message d'erreur", "cette fenêtre",
    "sous les yeux", "capture d'écran", "screenshot",
]


# Mots-clés qui nomment explicitement le PC — condition pour autoriser la
# capture d'écran PC même depuis un client mobile (voir
# core/lucas_core.py, allow_screen_capture, et api/server.py qui décide
# du client). Volontairement étroit : « mes écrans », « qu'est-ce que tu
# vois » ne nomment aucun appareil précis et ne doivent PAS suffire.
KEYWORDS_EXPLICIT_PC = [
    "mon pc", "sur pc", "mon ordinateur", "mon ordi",
    "l'écran de mon pc", "l'écran de mon ordinateur",
    "l'ecran de mon pc", "l'ecran de mon ordinateur",
    "sur l'ordi", "sur l'ordinateur",
]


def mentions_pc_explicitly(text: str) -> bool:
    """
    Décide si Cyril a nommé le PC sans ambiguïté — condition pour
    autoriser la capture d'écran PC même depuis un client où elle est
    normalement bloquée (PWA mobile, voir core/lucas_core.py).

    ⚠️ Mots-clés déterministes, jamais de classification LLM — même
    raisonnement que is_sensitive() : se tromper ici capturerait l'écran
    du PC sans que Cyril l'ait clairement demandé depuis son téléphone,
    peut-être loin de chez lui. La question « faut-il regarder un écran »
    tolère un classifieur ; « depuis quel appareil Cyril a-t-il vraiment
    demandé à en voir un » est une décision de confidentialité, elle
    reste déterministe.
    """
    return contains_any(text, KEYWORDS_EXPLICIT_PC)


def should_use_vision(text: str, context: str = "") -> bool:
    """
    Décide si Luca's doit regarder l'écran avant de répondre.

    Délègue à core.intent.classify(). Les mots-clés ci-dessus ne servent
    plus que de repli quand le classifieur est indisponible : ils ne
    couvraient que la moitié des formulations réelles, et rataient
    entièrement celles qui ne nomment pas l'écran (« c'est écrit quoi ? »).

    `context` est le dernier échange (voir intent.format_context), pour
    les questions elliptiques qui n'ont de sens que par rapport à lui.
    """
    from core.intent import classify

    return classify(text, context).needs_screen


def route_voice(answer: str, question: str = "") -> str:
    """
    Décide quel moteur TTS prononce la réponse : "local" (Piper) ou
    "cloud" (edge_tts).

    ⚠️ Le défaut est le CLOUD, à l'inverse de route(). Ce n'est pas une
    erreur : edge_tts a la meilleure voix, et le TTS ne transmet que du
    texte déjà affiché à l'écran. Le local est forcé dès qu'un contenu
    sensible est détecté.

    L'analyse porte sur la question ET la réponse : « quel est mon
    salaire ? » → « il est de 3200 euros » ne contient aucun mot-clé
    sensible dans la réponse seule, mais reste une donnée à ne pas
    envoyer chez Microsoft.

    ⚠️ Cette fonction n'utilise PAS le classifieur d'intention, alors que
    should_use_rag() le fait désormais. C'est délibéré : décider si un
    texte part chez Microsoft est une décision de sécurité. Elle doit
    rester déterministe, reproductible, et fonctionner même si Ollama est
    à l'arrêt — un classifieur indisponible ne doit jamais avoir pour
    effet d'autoriser une sortie. D'où matches_rag_keywords().

    Voir CLAUDE.md règle 3, section TTS.
    """
    combined = f"{question} {answer}"
    if is_sensitive(combined) or matches_rag_keywords(combined):
        return "local"
    return "cloud"


def should_use_rag(text: str, context: str = "") -> bool:
    """
    Décide si on va chercher dans les documents personnels (RAG) avant
    de répondre. Axe de décision indépendant de route() — une question
    peut être locale ET utiliser le RAG, ou cloud sans RAG, etc.

    Délègue à core.intent.classify(), qui rend un label unique : cette
    fonction et should_use_vision() ne peuvent donc plus répondre True
    toutes les deux sur le même message. C'était la cause du bug où le
    bloc RAG, injecté en dernier, noyait ce qui avait été lu à l'écran.
    """
    from core.intent import classify

    return classify(text, context).needs_documents


def should_use_finance(text: str) -> bool:
    """
    Décide si la question porte sur les relevés bancaires importés de
    Cyril (voir modules/finance_manager.py) — donc s'il faut consulter
    data/finance/ avant de répondre.

    Déterministe (voir KEYWORDS_FINANCE) : ne délègue jamais à
    core/intent.py. Indépendant de route() et de should_use_rag() — une
    question peut être locale ET consulter les finances, jamais vers le
    cloud (is_sensitive() force déjà le local sur ces mots-clés, qui
    recoupent largement KEYWORDS_SENSITIVE).
    """
    return contains_any(text, KEYWORDS_FINANCE)


def matches_rag_keywords(text: str) -> bool:
    """
    Test mots-clés pur, sans appel au classifieur.

    Réservé aux décisions de SÉCURITÉ, qui doivent rester déterministes
    et ne jamais dépendre de la disponibilité d'un modèle — voir
    route_voice(). Pour décider s'il faut consulter les documents,
    utiliser should_use_rag().
    """
    return contains_any(text, KEYWORDS_RAG)


# ── Calculatrice (modules/calculator.py) — câblé le 04/08/2026 ──────────
#
# Mots-clés qui signalent une demande de calcul explicite. Ne suffit pas
# seul : la question doit AUSSI contenir une expression extractible
# (extract_calculation()) — un message qui dit juste « calcule » sans
# rien à calculer ne doit déclencher aucun bloc de contexte.
KEYWORDS_CALCULATOR = [
    "combien font", "combien fait", "combien ca fait", "ca fait combien",
    "calcule", "calcul de", "quel est le resultat",
]

# Une expression arithmétique symbolique : chiffres, opérateurs, parenthèses,
# espaces. Volontairement restreint aux SYMBOLES (« 45 + 32 »), pas aux mots
# (« quarante-cinq plus trente-deux ») — portée délibérément réduite, voir
# ROADMAP.md pour la justification.
_EXPRESSION_CHARS = re.compile(r"[0-9+\-*/%().\s]+")


def extract_calculation(text: str) -> str | None:
    """
    Cherche la plus longue sous-chaîne qui ressemble à une expression
    arithmétique réelle (au moins deux nombres et un opérateur) — pas les
    mots qui l'entourent (« combien font », « ? »). None si rien de tel
    n'est trouvé.
    """
    # ⚠️ `fold_separators` : l'expression extraite est ÉVALUÉE ensuite.
    # La typographie française sépare les milliers par une espace fine
    # insécable — « 1 234 + 5 678 » copié depuis un document produisait
    # une expression inévaluable, et un trait d'union insécable faisait
    # disparaître l'opérateur (aucun calcul détecté du tout).
    candidates = _EXPRESSION_CHARS.findall(fold_separators(text))
    best = max(candidates, key=len, default="").strip()
    if not best:
        return None

    # ⚠️ Recolle les milliers séparés par une espace — « 1 234 » -> « 1234 ».
    #
    # La règle est VOLONTAIREMENT étroite : l'espace doit être suivie
    # d'exactement trois chiffres terminant un nombre, ce qui est le
    # groupement français des milliers et rien d'autre. Recoller tous les
    # chiffres séparés par une espace transformerait « 12 34 » en
    # « 1234 » — une lecture inventée, pas une correction de typographie.
    #
    # Sans cette étape, « 1 234 + 5 678 » atteignait la calculatrice sous
    # cette forme et rendait None : Luca disait honnêtement ne pas
    # pouvoir évaluer (§5.39), mais sur une expression parfaitement
    # ordinaire pour un francophone.
    best = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", best)
    if not any(op in best for op in "+-*/%"):
        return None
    if len(re.findall(r"\d+", best)) < 2:
        return None
    return best


def should_use_calculator(text: str) -> bool:
    """
    Décide si la question demande un calcul réel — déterministe, comme
    should_use_finance() : le domaine est étroit et les formulations
    prévisibles, pas besoin du classifieur core/intent.py.

    Exige À LA FOIS un mot-clé de calcul ET une expression extractible :
    « combien font 45 et 32 ? » (pas d'opérateur symbolique) ne doit pas
    déclencher un calcul halluciné faute de vraie expression à évaluer.
    """
    return contains_any(text, KEYWORDS_CALCULATOR) and extract_calculation(text) is not None


# ── Recherche web (modules/web_search.py) — câblé le 04/08/2026 ────────
#
# ⚠️ Volontairement ÉTROIT et EXPLICITE, contrairement au RAG/vision.
# Il n'existe aucun moyen fiable de distinguer par mots-clés une question
# de connaissance générale d'une question ordinaire — toute question sans
# rapport avec les documents de Cyril POURRAIT bénéficier d'une recherche
# web. Plutôt que de sur-déclencher (et envoyer des questions à
# DuckDuckGo sans demande claire, CLAUDE.md règle 3), ne se déclenche que
# sur une demande EXPLICITE de recherche en ligne.
KEYWORDS_WEB_SEARCH = [
    "cherche sur internet", "cherche sur le web", "cherche sur le net",
    "recherche sur internet", "recherche sur le web", "recherche sur le net",
    "cherche en ligne", "recherche en ligne",
]


def should_use_websearch(text: str) -> bool:
    """Déclenchement déterministe et étroit — voir le commentaire ci-dessus."""
    return contains_any(text, KEYWORDS_WEB_SEARCH)


# ── Météo (modules/weather_manager.py) — câblé le 04/08/2026 ───────────

KEYWORDS_WEATHER = [
    "quel temps fait-il", "quel temps fait il", "quel temps fait-il a",
    "quelle est la meteo", "quelle est la météo", "meteo a ", "météo à ",
    "meteo de ", "météo de ", "va-t-il pleuvoir", "va t il pleuvoir",
    "fait-il beau", "fait il beau",
]

# Une ville nommée après une préposition (« à Paris », « météo de Lyon »).
# Majuscule initiale exigée : un nom de ville s'écrit avec, et ça évite de
# capturer un mot ordinaire qui suivrait la même préposition par hasard.
_CITY_PATTERN = re.compile(
    r"(?:à|a|de|d'|pour)\s+([A-ZÀ-Ü][\wÀ-ÿ'-]*(?:[\s-][A-ZÀ-Ü][\wÀ-ÿ'-]*)*)"
)


def extract_city(text: str) -> str | None:
    """
    Cherche un nom de ville dans la question. None si aucune ville n'est
    nommée — le code appelant ne doit JAMAIS deviner une ville par défaut
    (voir core/lucas_core.py) : mieux vaut demander à Cyril de préciser.
    """
    # ⚠️ `fold_separators` et non `normalize` : la valeur extraite part
    # vers le service météo ET s'affiche à Cyril. `normalize()` rendrait
    # « Saint-Étienne » en « saint-etienne » — on abîmerait la donnée pour
    # corriger un problème de séparateur.
    #
    # Mesuré le 05/08/2026 : « Saint‑Étienne » avec un trait d'union
    # insécable (U+2011) rendait « Saint » — donc la météo d'une autre
    # ville, ou aucune.
    match = _CITY_PATTERN.search(fold_separators(text))
    return match.group(1).strip() if match else None


def should_use_weather(text: str) -> bool:
    """Déclenchement déterministe — même raisonnement que should_use_finance()."""
    return contains_any(text, KEYWORDS_WEATHER)


# ── Automation (modules/automation_manager.py) — câblé le 04/08/2026 ───
#
# Premier câblage réel de core/decision_engine.py, accord explicite de
# Cyril (une seule action : lancement d'appli, sans confirmation, comme
# aujourd'hui). ⚠️ Vérifié avant d'écrire quoi que ce soit : il n'existait
# aucun « chemin direct » chat → automation_manager à migrer — le module
# n'était appelé nulle part dans core/lucas_core.py, core/router.py ni
# api/server.py, uniquement depuis demos/demo_automation.py (script
# manuel). Ce câblage est donc le PREMIER chemin réel, pas un
# remplacement — signalé à Cyril, voir ROADMAP.md §5.25.
# ⚠️ Le nom d'application doit suivre le verbe DE PRÈS (au plus un mot
# d'écart — un article « le »/« la »/« l' », typiquement), pas n'importe
# où dans la phrase. Trouvé en écrivant le test de non-déclenchement :
# « lance une réflexion sur Chrome » contient à la fois un verbe et
# « chrome » — un vrai risque de faux positif ici, contrairement au
# calcul ou à la météo, puisque l'effet de bord est réel (un programme
# démarre). Même famille de correctif que les modes AURA (§5.20) :
# un mot déclencheur seul ne suffit pas, la proximité si.
_AUTOMATION_VERB_PATTERN = r"(?:ouvre|ouvrir|lance|lancer|demarre|demarrer)"

# Noms français courants pour une entrée de la liste blanche — même
# application, même liste blanche, juste une meilleure reconnaissance de
# la façon dont Cyril la nomme réellement. "notepad" est le nom du
# programme (clé technique de WHITELISTED_APPS), mais un francophone dit
# "bloc-notes" — sans cet alias, la phrase de validation suggérée par
# Cyril lui-même ("ouvre le bloc-notes") ne déclencherait rien.
_APP_NAME_ALIASES = {
    "bloc-notes": "notepad",
    "bloc notes": "notepad",
    "explorateur": "explorer",
    "explorateur de fichiers": "explorer",
}


def _spoken_name_pattern(spoken_name: str) -> str:
    """
    Motif tolérant aux variantes d'écriture d'un même nom d'application.

    ⚠️ Bug réel trouvé le 05/08/2026 (Cyril, PWA mobile) : il a écrit
    « ouvre le bloc note » — singulier, sans trait d'union. Les deux alias
    existants étaient « bloc-notes » et « bloc notes », tous deux au
    PLURIEL : aucun ne correspondait, `extract_app_name` a rendu None, et
    l'action n'a jamais été tentée. Voir ROADMAP.md §5.31.

    Ajouter « bloc note » à la liste aurait corrigé ce cas précis et laissé
    passer le suivant (« bloc-note », « blocnotes »...). Le motif traite
    donc la CLASSE de variantes :
    - trait d'union, espace ou rien entre les mots (`[-\\s]*`)
    - « s » final optionnel sur chaque mot (singulier/pluriel)

    Le nombre de mots, lui, reste exigé : « bloc » seul ne déclenche rien.
    """
    mots = [mot for mot in re.split(r"[-\s]+", spoken_name) if mot]
    return r"[-\s]*".join(rf"{re.escape(mot.rstrip('s'))}s?" for mot in mots)


def extract_app_name(text: str) -> str | None:
    """
    Cherche un nom d'application DE LA LISTE BLANCHE réelle (ou un alias
    français courant du même nom), immédiatement précédé d'un verbe
    d'ouverture — jamais un nom arbitraire : seul
    modules.automation_manager.WHITELISTED_APPS peut être lancé, extraire
    autre chose n'aurait aucun effet utile et ne ferait que remonter un
    ActionDenied. Import paresseux, même motif que core.dates ailleurs
    dans ce fichier (éviter la boucle d'import via core/lucas_core.py).
    """
    from core.text_utils import normalize
    from modules.automation_manager import WHITELISTED_APPS

    normalized = normalize(text)
    candidates = {name: name for name in WHITELISTED_APPS}
    candidates.update(
        {alias: real for alias, real in _APP_NAME_ALIASES.items() if real in WHITELISTED_APPS}
    )
    for spoken_name, real_name in candidates.items():
        # `\s*'?\s*` après l'article optionnel : sans lui, « ouvre
        # l'explorateur » ne correspondait à rien — l'article élidé « l' »
        # n'est pas suivi d'un espace, donc `\s+nom` échouait. Même famille
        # que le bug « bloc note » ci-dessus (une variante d'écriture
        # naturelle qui ne déclenche rien), trouvée en vérifiant ce
        # correctif-ci plutôt qu'en usage réel.
        pattern = (
            rf"\b{_AUTOMATION_VERB_PATTERN}\b(?:\s+\w+)?\s*'?\s*"
            rf"{_spoken_name_pattern(spoken_name)}\b"
        )
        if re.search(pattern, normalized):
            return real_name
    return None


def should_use_automation(text: str) -> bool:
    """
    Déterministe, comme should_use_calculator() : le verbe et le nom
    d'application sont déjà liés par la proximité exigée dans
    extract_app_name(), pas besoin d'un second test de mot-clé séparé.
    """
    return extract_app_name(text) is not None


# Objets abstraits qui suivent naturellement un verbe d'ouverture sans
# désigner un programme — « lance une réflexion sur Chrome », « ouvre la
# discussion ». Le commentaire de _AUTOMATION_VERB_PATTERN signalait déjà
# ce risque de faux positif ; cette liste le neutralise pour la détection
# large ci-dessous, qui n'exige justement PAS un nom connu.
_ABSTRACT_ACTION_OBJECTS = (
    "reflexion",
    "recherche",
    "analyse",
    "discussion",
    "conversation",
    "debat",
    "idee",
    "projet",
    "sujet",
    "piste",
    # Pas abstraits, mais pas des applications non plus : Luca's ne sait
    # pas les ouvrir, et injecter « aucune application reconnue » pour
    # « ouvre le fichier X » enverrait la réponse à côté de la question.
    "fichier",
    "dossier",
    "document",
    "lien",
    "page",
    "onglet",
)


def looks_like_app_request(text: str) -> bool:
    """
    Cyril demande-t-il d'ouvrir QUELQUE CHOSE — même chose inconnue ?

    ⚠️ Ne sert JAMAIS à exécuter : seul `extract_app_name()` autorise une
    exécution, et seulement pour la liste blanche réelle. Cette fonction-ci
    répond à une autre question, qui n'était posée nulle part : « une action
    a-t-elle été demandée ? », indépendamment de « sait-on la faire ? ».

    Sans cette distinction, une demande non reconnue produisait un silence
    total dans le prompt — et le modèle, n'ayant reçu aucune information sur
    l'action, répondait « Le Bloc-notes est lancé » alors que rien n'avait
    été tenté (cas réel du 05/08/2026, ROADMAP.md §5.31). Un silence laisse
    le modèle deviner ; ici deviner produit un mensonge sur l'état réel de
    la machine de Cyril.

    Volontairement plus large que `extract_app_name` : mieux vaut expliquer
    une fois de trop qu'on n'a rien fait, que confirmer une fois de trop
    qu'on l'a fait.
    """
    from core.text_utils import normalize

    normalized = normalize(text)
    # « comment ouvrir un fichier ? » demande une explication, pas une
    # action — répondre « je n'ai rien lancé » serait hors sujet.
    pattern = (
        rf"(?<!comment )\b{_AUTOMATION_VERB_PATTERN}\b"
        r"(?:\s+(?:le|la|l'|les|un|une|des|moi|nous|mon|ma|mes)){0,2}"
        r"\s+([a-z0-9][\w-]*)"
    )
    match = re.search(pattern, normalized)
    if match is None:
        return False
    return match.group(1).rstrip("s") not in _ABSTRACT_ACTION_OBJECTS
