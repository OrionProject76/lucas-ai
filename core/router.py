# core/router.py — décide si la question part en local (Ollama) ou en cloud
# + décide si le RAG (documents personnels) doit être consulté
# Architecture hybride : local par défaut, cloud pour les questions complexes,
# jamais de donnée sensible vers le cloud (CLAUDE.md règle 3).

from core.text_utils import contains_any

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


def matches_rag_keywords(text: str) -> bool:
    """
    Test mots-clés pur, sans appel au classifieur.

    Réservé aux décisions de SÉCURITÉ, qui doivent rester déterministes
    et ne jamais dépendre de la disponibilité d'un modèle — voir
    route_voice(). Pour décider s'il faut consulter les documents,
    utiliser should_use_rag().
    """
    return contains_any(text, KEYWORDS_RAG)
