# security/privacy_shield.py — surveillance des connexions réseau (observation seule)
#
# Répond à la question « qu'est-ce qui parle vers l'extérieur depuis cette
# machine, et est-ce attendu ? ». Ne coupe jamais une connexion.
#
# Aucune résolution DNS inverse, aucune interrogation de service de
# géolocalisation d'IP : ces requêtes révéleraient à un tiers avec qui
# Cyril communique. Tout est déduit localement de l'adresse elle-même.

import ipaddress
from collections.abc import Callable

import psutil

from security.guardian import VOLATILE_DIRECTORIES
from security.types import INFO, WARNING, Finding

# Adresses d'écoute qui exposent un service à tout le réseau, pas seulement
# à la machine elle-même.
WIDE_OPEN_ADDRESSES = {"0.0.0.0", "::"}

# Ports que le projet ouvre volontairement — les signaler serait du bruit.
# 11434 : Ollama. 8000 : l'API FastAPI de Luca's (voir README_INSTALL.md).
EXPECTED_LISTENING_PORTS = {11434, 8000}

# Plage de ports éphémères (IANA/Windows). Windows y attribue dynamiquement
# les points d'accès RPC : un service qui écoute là n'a rien décidé, c'est
# l'OS qui lui a donné ce numéro. En faire des alertes noierait le rapport.
EPHEMERAL_PORT_FLOOR = 49152

# Répertoires des binaires système. Un service Windows qui écoute est le
# fonctionnement normal de la machine, pas un signal. Ce filtre repose sur
# le chemin, donc un binaire qui USURPE un nom système reste détecté :
# il n'est justement pas dans System32 (voir Guardian).
SYSTEM_BINARY_ROOTS = (r"c:\windows\system32", r"c:\windows\syswow64", r"c:\windows\\")

# Pseudo-process du noyau Windows : pas de chemin d'exécutable lisible,
# et c'est lui qui porte le partage de fichiers (port 445). L'exclure par
# le nom seul serait dangereux — on exige aussi son PID réservé.
KERNEL_PROCESS = ("System", 4)


def _is_external(ip: str) -> bool:
    """
    Vrai si l'adresse sort du réseau local. Une IP privée (192.168.x,
    10.x) ou de bouclage reste dans la maison de Cyril ; une IP publique
    signifie que des octets partent sur Internet.
    """
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (address.is_private or address.is_loopback or address.is_link_local)


class PrivacyShield:
    """
    Capteur réseau. `scan()` retourne des signaux, jamais une action.

    `log_event` est injecté : security/ ne doit pas importer OrionCore.
    """

    def __init__(
        self,
        log_event: Callable[[str, str], None] | None = None,
        history=None,
    ) -> None:
        self.log_event = log_event
        # Mémoire des comportements, injectée : security/ n'a pas à savoir
        # où elle est stockée. Absente, le capteur garde son comportement
        # de niveau 0 — il détecte, mais sans notion de « nouveau ».
        self.history = history

    # ── Heuristiques unitaires ────────────────────────────────────────

    @staticmethod
    def _check_volatile_process_online(name: str, exe: str, remote: str) -> Finding | None:
        """
        Un binaire lancé depuis un répertoire temporaire qui parle à
        Internet. Chaque moitié prise isolément est banale ; la
        combinaison l'est beaucoup moins.
        """
        if not exe:
            return None
        lowered = exe.lower()
        if not any(directory in lowered for directory in VOLATILE_DIRECTORIES):
            return None
        return Finding(
            severity=WARNING,
            kind="volatile_process_online",
            summary=(
                f"« {name} », lancé depuis un répertoire temporaire, "
                "communique avec une adresse publique."
            ),
            evidence={"process": name, "chemin": exe, "distant": remote},
        )

    @staticmethod
    def _is_system_binary(exe: str) -> bool:
        lowered = (exe or "").lower()
        return any(lowered.startswith(root.rstrip("\\")) for root in SYSTEM_BINARY_ROOTS)

    @staticmethod
    def _check_wide_open_listener(name: str, laddr, exe: str) -> Finding | None:
        """
        Service exposé à tout le réseau plutôt qu'à la machine seule.

        Trois filtres, tous appris du premier balayage réel qui remontait
        des dizaines de faux positifs sur des services Windows :
        port attendu du projet, port éphémère attribué par l'OS, binaire
        système. Un capteur qui crie sur svchost.exe ne sera jamais lu.
        """
        if laddr.ip not in WIDE_OPEN_ADDRESSES:
            return None
        if laddr.port in EXPECTED_LISTENING_PORTS:
            return None
        if laddr.port >= EPHEMERAL_PORT_FLOOR:
            return None
        if PrivacyShield._is_system_binary(exe):
            return None
        return Finding(
            severity=INFO,
            kind="wide_open_listener",
            summary=(
                f"« {name} » écoute sur toutes les interfaces (port {laddr.port}). "
                "Accessible depuis le réseau local, pas seulement depuis ce PC."
            ),
            evidence={"process": name, "port": laddr.port, "chemin": exe or "inconnu"},
        )

    def _check_first_external_contact(self, name: str, exe: str, ip: str) -> Finding | None:
        """
        Premier contact d'un programme avec une adresse publique.

        La clé retenue est (programme, IP) SANS le port : les ports
        source changent à chaque connexion, les inclure ferait paraître
        tout nouveau à chaque balayage et noierait le signal.

        Sans historique injecté, ce contrôle ne s'applique pas.
        """
        if self.history is None:
            return None

        if not self.history.is_new(f"net|{name.lower()}|{ip}"):
            return None

        return Finding(
            severity=WARNING,
            kind="first_external_contact",
            summary=(
                f"« {name} » contacte {ip} pour la première fois. "
                "Nouveau comportement réseau pour ce programme."
            ),
            evidence={"process": name, "distant": ip, "chemin": exe or "inconnu"},
        )

    # ── Balayage ──────────────────────────────────────────────────────

    def scan(self) -> list[Finding]:
        """Parcourt les sockets et retourne les signaux relevés."""
        findings: list[Finding] = []

        try:
            connections = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, PermissionError):
            return [
                Finding(
                    severity=INFO,
                    kind="scan_unavailable",
                    summary=(
                        "Connexions réseau non lisibles : droits insuffisants. "
                        "Relancer en administrateur pour un balayage complet."
                    ),
                    evidence={},
                )
            ]

        for conn in connections:
            if conn.pid is None:
                continue

            name, exe = self._describe_process(conn.pid)
            if name is None:
                continue

            if (name, conn.pid) == KERNEL_PROCESS:
                continue

            if conn.status == psutil.CONN_LISTEN and conn.laddr:
                finding = self._check_wide_open_listener(name, conn.laddr, exe)
                if finding is not None:
                    finding.evidence["pid"] = conn.pid
                    findings.append(finding)
                continue

            if conn.raddr and _is_external(conn.raddr.ip):
                remote = f"{conn.raddr.ip}:{conn.raddr.port}"
                for check in (
                    self._check_volatile_process_online(name, exe, remote),
                    self._check_first_external_contact(name, exe, conn.raddr.ip),
                ):
                    if check is not None:
                        check.evidence["pid"] = conn.pid
                        findings.append(check)

        if self.history is not None:
            self.history.save()

        findings = self._deduplicate(findings)
        self._log(findings)
        return findings

    @staticmethod
    def _describe_process(pid: int) -> tuple[str | None, str]:
        """Nom et chemin d'un PID, ou (None, '') s'il a disparu ou est protégé."""
        try:
            proc = psutil.Process(pid)
            return proc.name(), (proc.exe() or "")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None, ""

    @staticmethod
    def _deduplicate(findings: list[Finding]) -> list[Finding]:
        """
        Un même process ouvre souvent des dizaines de sockets. Sans
        déduplication, un seul programme suspect produirait cinquante
        lignes identiques et noierait le reste.
        """
        seen: set[tuple] = set()
        unique: list[Finding] = []
        for finding in findings:
            # « distant » entre dans la clé : deux nouvelles IP pour le
            # même programme sont deux faits distincts, les fondre en
            # ferait disparaître un.
            key = (
                finding.kind,
                finding.evidence.get("process"),
                finding.evidence.get("port"),
                finding.evidence.get("distant"),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(finding)
        return unique

    def _log(self, findings: list[Finding]) -> None:
        if self.log_event is None:
            return
        for finding in findings:
            if finding.severity == INFO:
                continue
            event_type, details = finding.as_event()
            self.log_event(event_type, details)


def summarize_exposure() -> dict:
    """
    Inventaire brut, sans jugement : combien de connexions sortent vers
    l'extérieur, et depuis combien de programmes distincts. Utile pour
    donner une mesure à Cyril avant même toute heuristique.
    """
    try:
        connections = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, PermissionError):
        return {"disponible": False}

    external = [
        c for c in connections
        if c.raddr and c.status == psutil.CONN_ESTABLISHED and _is_external(c.raddr.ip)
    ]
    return {
        "disponible": True,
        "sockets_total": len(connections),
        "connexions_externes": len(external),
        "processus_concernes": len({c.pid for c in external if c.pid}),
    }
