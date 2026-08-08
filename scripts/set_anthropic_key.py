# scripts/set_anthropic_key.py — enregistre la clé API Anthropic
#
# À lancer une fois par machine, manuellement par Cyril :
#   venv\Scripts\python.exe scripts\set_anthropic_key.py
#
# La clé n'est jamais écrite dans .env ni en clair où que ce soit — elle va
# directement dans le Gestionnaire d'identification Windows (module
# `keyring`), lu ensuite par config.ANTHROPIC_API_KEY. Décision explicite
# de Cyril avant la Brique 1 du noyau minimal (08/08/2026).

from __future__ import annotations

import getpass

import keyring

SERVICE = "lucas_ai"
KEY_NAME = "anthropic_api_key"


def main() -> None:
    existing = keyring.get_password(SERVICE, KEY_NAME)
    if existing:
        print("Une clé Anthropic est déjà enregistrée pour Luca's.")
        reponse = input("La remplacer ? (o/N) ").strip().lower()
        if reponse != "o":
            print("Annulé — clé existante conservée.")
            return

    # getpass, jamais input() : la clé ne doit pas s'afficher en clair
    # dans le terminal ni finir dans son historique.
    key = getpass.getpass("Clé API Anthropic (sk-ant-...) : ").strip()
    if not key:
        print("Rien à enregistrer — clé vide.")
        return

    keyring.set_password(SERVICE, KEY_NAME, key)
    print("Clé Anthropic enregistrée dans le Gestionnaire d'identification Windows.")


if __name__ == "__main__":
    main()
