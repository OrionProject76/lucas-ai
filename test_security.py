# test_security.py — capteurs de sécurité (paquet security/)
#
# Deux propriétés tenues pour non négociables et testées comme telles :
#   1. Observation seule — aucun process tué, aucune connexion coupée.
#   2. Aucun appel réseau sortant — les capteurs ne parlent à personne.
#
# psutil est mocké partout : les tests ne dépendent pas des process
# réellement lancés sur la machine.

from __future__ import annotations

import inspect
import time
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

from security import (
    CRITICAL,
    INFO,
    WARNING,
    Guardian,
    PersistenceWatch,
    PrivacyShield,
    RansomwareWatch,
    format_report,
)
from security.guardian import LOOKALIKE_NAMES
from security.privacy_shield import _is_external, summarize_exposure
from security.types import Finding, sort_findings

# ── Garde-fous structurels ────────────────────────────────────────────

def _security_modules():
    """
    Tous les modules du paquet security/, découverts dynamiquement.

    Une liste écrite en dur aurait dérivé : persistence_watch, history et
    monitor ont été ajoutés après les gardes ci-dessous et échappaient à
    la vérification. Un module ajouté demain est couvert d'office.
    """
    import importlib
    import pkgutil

    import security

    return [
        importlib.import_module(f"security.{info.name}")
        for info in pkgutil.iter_modules(security.__path__)
    ]


def test_the_whole_package_is_covered_by_the_guards() -> None:
    """Garde-fou de la garde-fou : la découverte doit trouver les modules."""
    names = {module.__name__.rsplit(".", 1)[-1] for module in _security_modules()}
    assert {"guardian", "privacy_shield", "ransomware_watch", "persistence_watch",
            "history", "monitor", "types"} <= names


def test_sensors_never_act() -> None:
    """
    Observation seule : aucun capteur ne doit pouvoir tuer un process ni
    fermer une socket. Donner ce pouvoir à Luca's est une décision
    distincte, à valider par Cyril (VISION_LONG_TERME.md §4.1).
    """
    forbidden = ("kill(", "terminate(", "shutdown(", "suspend(", "close()")
    for module in _security_modules():
        source = inspect.getsource(module)
        for call in forbidden:
            assert call not in source, f"{module.__name__} ne doit pas appeler {call}"


def test_sensors_make_no_outbound_call() -> None:
    """
    Envoyer la liste des process, des connexions ou des points de
    démarrage de Cyril à un service tiers serait exactement la fuite
    qu'on cherche à empêcher.
    """
    forbidden = ("requests.", "urllib", "http://", "https://", "socket.create_connection")
    for module in _security_modules():
        source = inspect.getsource(module)
        for call in forbidden:
            assert call not in source, f"{module.__name__} ne doit rien émettre ({call})"


def test_no_module_writes_to_the_registry() -> None:
    """Les capteurs lisent le registre Windows, ils n'y écrivent jamais."""
    for module in _security_modules():
        source = inspect.getsource(module)
        for call in ("SetValue", "CreateKey", "DeleteKey", "DeleteValue"):
            assert call not in source, f"{module.__name__} ne doit pas écrire ({call})"


# ── Guardian : usurpation de nom système ──────────────────────────────

def test_svchost_outside_system32_is_critical() -> None:
    finding = Guardian._check_system_impersonation(
        "svchost.exe", r"C:\Users\PC\AppData\Local\Temp\svchost.exe"
    )
    assert finding is not None
    assert finding.severity == CRITICAL
    assert finding.kind == "process_impersonation"


def test_real_svchost_is_not_flagged() -> None:
    assert Guardian._check_system_impersonation(
        "svchost.exe", r"C:\Windows\System32\svchost.exe"
    ) is None


def test_syswow64_svchost_is_legitimate() -> None:
    """Les binaires 32 bits vivent ailleurs — ne pas générer de faux positif."""
    assert Guardian._check_system_impersonation(
        "svchost.exe", r"C:\Windows\SysWOW64\svchost.exe"
    ) is None


def test_case_differences_do_not_create_false_positives() -> None:
    assert Guardian._check_system_impersonation(
        "SVCHOST.EXE", r"C:\WINDOWS\SYSTEM32\SVCHOST.EXE"
    ) is None


def test_unknown_process_is_not_flagged() -> None:
    assert Guardian._check_system_impersonation(
        "mon_appli.exe", r"C:\Program Files\MonAppli\mon_appli.exe"
    ) is None


def test_process_without_path_is_not_flagged() -> None:
    """
    Un chemin illisible (droits insuffisants) est banal sous Windows.
    En faire une alerte noierait les vrais signaux.
    """
    assert Guardian._check_system_impersonation("svchost.exe", "") is None


# ── Guardian : noms sosies ────────────────────────────────────────────

@pytest.mark.parametrize("fake", sorted(LOOKALIKE_NAMES))
def test_lookalike_names_are_all_detected(fake: str) -> None:
    finding = Guardian._check_lookalike_name(fake, r"C:\Temp\x.exe")
    assert finding is not None
    assert finding.severity == CRITICAL


def test_homoglyph_with_capital_i_is_detected() -> None:
    """
    « expIorer.exe » avec un I majuscule se lit comme « explorer.exe » à
    l'écran. Les clés du dictionnaire doivent donc être en minuscules,
    sinon .lower() détruit le signal qu'on cherche.
    """
    finding = Guardian._check_lookalike_name("expIorer.exe", r"C:\Temp\x.exe")
    assert finding is not None
    assert finding.evidence["imite"] == "explorer.exe"


def test_lookalike_keys_are_all_lowercase() -> None:
    """Garde-fou : une clé avec une majuscule ne matcherait jamais."""
    assert all(key == key.lower() for key in LOOKALIKE_NAMES)


def test_legitimate_name_is_not_a_lookalike() -> None:
    assert Guardian._check_lookalike_name("chrome.exe", r"C:\Program Files\chrome.exe") is None


# ── Guardian : répertoires volatils ───────────────────────────────────

@pytest.mark.parametrize(
    "path",
    [
        r"C:\Users\PC\AppData\Local\Temp\setup.exe",
        r"C:\Users\PC\Downloads\jeu.exe",
        r"C:\$Recycle.Bin\S-1-5-21\truc.exe",
    ],
)
def test_volatile_locations_are_flagged(path: str) -> None:
    finding = Guardian._check_volatile_location("truc.exe", path)
    assert finding is not None
    assert finding.severity == WARNING


def test_program_files_is_not_volatile() -> None:
    assert Guardian._check_volatile_location(
        "app.exe", r"C:\Program Files\App\app.exe"
    ) is None


def test_an_empty_exe_path_is_not_volatile() -> None:
    """Process système sans chemin résolu (droits insuffisants) : pas de faux signal."""
    assert Guardian._check_volatile_location("svchost.exe", "") is None


# ── Guardian : balayage complet ───────────────────────────────────────

def test_scan_skips_inaccessible_processes(monkeypatch) -> None:
    """Un process protégé ne doit ni planter le scan ni générer d'alerte."""

    class _Denied:
        @property
        def info(self):
            raise psutil.AccessDenied(pid=4)

    good = SimpleNamespace(
        info={"name": "svch0st.exe", "exe": r"C:\Temp\svch0st.exe", "pid": 1234}
    )
    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: [_Denied(), good])

    findings = Guardian().scan()
    assert len(findings) == 1
    assert findings[0].evidence["pid"] == 1234


def test_scan_skips_a_process_without_a_name(monkeypatch) -> None:
    """Un process sans nom résolu ne doit déclencher aucun des trois contrôles."""
    procs = [SimpleNamespace(info={"name": "", "exe": r"C:\Temp\x.exe", "pid": 1})]
    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: procs)

    assert Guardian().scan() == []


def test_scan_logs_only_non_trivial_findings(monkeypatch) -> None:
    events: list[tuple[str, str]] = []
    procs = [
        SimpleNamespace(info={"name": "svchost.exe", "exe": r"C:\Temp\svchost.exe", "pid": 1}),
    ]
    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: procs)

    Guardian(log_event=lambda t, d="": events.append((t, d))).scan()
    assert [t for t, _ in events] == ["security_process_impersonation"]


# ── Privacy Shield : classification des adresses ──────────────────────

@pytest.mark.parametrize(
    "ip, external",
    [
        ("8.8.8.8", True),
        ("192.168.1.11", False),
        ("10.0.0.5", False),
        ("127.0.0.1", False),
        ("169.254.1.1", False),
        ("pas-une-ip", False),
    ],
)
def test_external_address_classification(ip: str, external: bool) -> None:
    assert _is_external(ip) is external


# ── Privacy Shield : heuristiques ─────────────────────────────────────

def test_temp_process_talking_outside_is_flagged() -> None:
    finding = PrivacyShield._check_volatile_process_online(
        "x.exe", r"C:\Users\PC\AppData\Local\Temp\x.exe", "8.8.8.8:443"
    )
    assert finding is not None
    assert finding.severity == WARNING


def test_normal_process_talking_outside_is_not_flagged() -> None:
    """Un navigateur qui sort est banal : ne pas crier au loup."""
    assert PrivacyShield._check_volatile_process_online(
        "chrome.exe", r"C:\Program Files\Google\Chrome\chrome.exe", "8.8.8.8:443"
    ) is None


def test_expected_listening_ports_are_silent() -> None:
    """Ollama (11434) et l'API de Luca's (8000) sont ouverts volontairement."""
    laddr = SimpleNamespace(ip="0.0.0.0", port=11434)
    assert PrivacyShield._check_wide_open_listener("ollama.exe", laddr, "") is None


def test_unexpected_wide_open_listener_is_reported() -> None:
    laddr = SimpleNamespace(ip="0.0.0.0", port=4444)
    finding = PrivacyShield._check_wide_open_listener(
        "inconnu.exe", laddr, r"C:\Users\PC\Downloads\inconnu.exe"
    )
    assert finding is not None
    assert finding.severity == INFO


def test_windows_services_are_not_reported() -> None:
    """
    Appris du premier balayage réel : svchost et services.exe écoutent
    légitimement sur 0.0.0.0. Les signaler noyait tout le rapport.
    """
    laddr = SimpleNamespace(ip="0.0.0.0", port=5040)
    assert PrivacyShield._check_wide_open_listener(
        "svchost.exe", laddr, r"C:\Windows\System32\svchost.exe"
    ) is None


def test_ephemeral_ports_are_not_reported() -> None:
    """Un port ≥ 49152 est attribué par Windows, pas choisi par le service."""
    laddr = SimpleNamespace(ip="0.0.0.0", port=49666)
    assert PrivacyShield._check_wide_open_listener(
        "inconnu.exe", laddr, r"C:\Users\PC\Downloads\inconnu.exe"
    ) is None


def test_impersonating_binary_still_reported_despite_system_name() -> None:
    """
    Le filtre « binaire système » repose sur le CHEMIN, pas le nom : un
    faux svchost.exe hors System32 reste signalé.
    """
    laddr = SimpleNamespace(ip="0.0.0.0", port=4444)
    finding = PrivacyShield._check_wide_open_listener(
        "svchost.exe", laddr, r"C:\Users\PC\AppData\Local\Temp\svchost.exe"
    )
    assert finding is not None


def test_kernel_pseudo_process_is_ignored(monkeypatch) -> None:
    """
    « System » PID 4 porte le partage de fichiers Windows (port 445) et
    n'a pas de chemin lisible. L'exclusion exige le nom ET le PID réservé,
    pour qu'un imposteur nommé « System » ne passe pas au travers.
    """
    conn = SimpleNamespace(
        pid=4,
        status=psutil.CONN_LISTEN,
        laddr=SimpleNamespace(ip="0.0.0.0", port=445),
        raddr=None,
    )
    monkeypatch.setattr(psutil, "net_connections", lambda kind=None: [conn])
    monkeypatch.setattr(PrivacyShield, "_describe_process", staticmethod(lambda pid: ("System", "")))
    assert PrivacyShield().scan() == []


def test_impostor_named_system_is_not_ignored(monkeypatch) -> None:
    """Même nom, autre PID : l'exclusion ne doit pas s'appliquer."""
    conn = SimpleNamespace(
        pid=9999,
        status=psutil.CONN_LISTEN,
        laddr=SimpleNamespace(ip="0.0.0.0", port=4444),
        raddr=None,
    )
    monkeypatch.setattr(psutil, "net_connections", lambda kind=None: [conn])
    monkeypatch.setattr(
        PrivacyShield, "_describe_process",
        staticmethod(lambda pid: ("System", r"C:\Temp\System.exe")),
    )
    assert len(PrivacyShield().scan()) == 1


def test_access_denied_is_reported_not_crashed(monkeypatch) -> None:
    def denied(kind=None):
        raise psutil.AccessDenied(pid=None)

    monkeypatch.setattr(psutil, "net_connections", denied)
    findings = PrivacyShield().scan()
    assert len(findings) == 1
    assert findings[0].kind == "scan_unavailable"


def test_duplicate_findings_are_collapsed() -> None:
    """Un process ouvre des dizaines de sockets : une ligne suffit."""
    duplicates = [
        Finding(WARNING, "volatile_process_online", "x", {"process": "x.exe", "port": None}),
        Finding(WARNING, "volatile_process_online", "x", {"process": "x.exe", "port": None}),
    ]
    assert len(PrivacyShield._deduplicate(duplicates)) == 1


def test_summarize_exposure_survives_access_denied(monkeypatch) -> None:
    def denied(kind=None):
        raise psutil.AccessDenied(pid=None)

    monkeypatch.setattr(psutil, "net_connections", denied)
    assert summarize_exposure() == {"disponible": False}


def test_summarize_exposure_counts_external_connections(monkeypatch) -> None:
    """
    Chemin normal, jamais exercé jusqu'ici (seul l'échec AccessDenied
    l'était) : trouvé via mesure de couverture réelle.
    """
    established = SimpleNamespace(
        raddr=SimpleNamespace(ip="8.8.8.8", port=443),
        status=psutil.CONN_ESTABLISHED,
        pid=123,
    )
    internal = SimpleNamespace(
        raddr=SimpleNamespace(ip="192.168.1.1", port=443),
        status=psutil.CONN_ESTABLISHED,
        pid=124,
    )
    listening = SimpleNamespace(raddr=None, status=psutil.CONN_LISTEN, pid=125)

    monkeypatch.setattr(
        psutil, "net_connections",
        lambda kind=None: [established, internal, listening],
    )

    assert summarize_exposure() == {
        "disponible": True,
        "sockets_total": 3,
        "connexions_externes": 1,
        "processus_concernes": 1,
    }


# ── Privacy Shield : scan() de bout en bout ────────────────────────────
#
# Les tests ci-dessus vérifient les heuristiques unitairement ; ceux-ci
# passent par scan() lui-même — jamais exercé avec une vraie connexion
# externe (conn.pid None, process disparu, _describe_process réel,
# évènements journalisés, history.save()). Trouvé via mesure de
# couverture réelle, même motif que ransomware_watch.py.

def test_scan_skips_a_connection_without_a_pid(monkeypatch) -> None:
    """Une socket sans PID (visible mais non attribuable) est ignorée."""
    conn = SimpleNamespace(pid=None, status=psutil.CONN_ESTABLISHED, raddr=None)
    monkeypatch.setattr(psutil, "net_connections", lambda kind=None: [conn])
    assert PrivacyShield().scan() == []


def test_scan_skips_a_vanished_process(monkeypatch) -> None:
    """_describe_process renvoie (None, '') : le process a disparu entre-temps."""
    conn = SimpleNamespace(
        pid=555,
        status=psutil.CONN_ESTABLISHED,
        raddr=SimpleNamespace(ip="8.8.8.8", port=443),
    )
    monkeypatch.setattr(psutil, "net_connections", lambda kind=None: [conn])
    monkeypatch.setattr(PrivacyShield, "_describe_process", staticmethod(lambda pid: (None, "")))
    assert PrivacyShield().scan() == []


def test_describe_process_reads_the_real_process(monkeypatch) -> None:
    fake_proc = SimpleNamespace(name=lambda: "chrome.exe", exe=lambda: r"C:\Chrome\chrome.exe")
    monkeypatch.setattr(psutil, "Process", lambda pid: fake_proc)
    assert PrivacyShield._describe_process(123) == ("chrome.exe", r"C:\Chrome\chrome.exe")


def test_describe_process_returns_none_for_a_vanished_process(monkeypatch) -> None:
    def _raise(pid):
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(psutil, "Process", _raise)
    assert PrivacyShield._describe_process(123) == (None, "")


def test_describe_process_returns_none_when_access_denied(monkeypatch) -> None:
    def _raise(pid):
        raise psutil.AccessDenied(pid)

    monkeypatch.setattr(psutil, "Process", _raise)
    assert PrivacyShield._describe_process(123) == (None, "")


def test_scan_flags_a_volatile_process_talking_outside(monkeypatch) -> None:
    """Bout en bout : conn externe -> heuristique -> pid ajouté -> findings."""
    conn = SimpleNamespace(
        pid=777,
        status=psutil.CONN_ESTABLISHED,
        raddr=SimpleNamespace(ip="8.8.8.8", port=443),
        laddr=None,
    )
    monkeypatch.setattr(psutil, "net_connections", lambda kind=None: [conn])
    monkeypatch.setattr(
        PrivacyShield, "_describe_process",
        staticmethod(lambda pid: ("x.exe", r"C:\Users\PC\AppData\Local\Temp\x.exe")),
    )

    findings = PrivacyShield().scan()

    assert len(findings) == 1
    assert findings[0].kind == "volatile_process_online"
    assert findings[0].evidence["pid"] == 777


def test_scan_ignores_an_internal_connection(monkeypatch) -> None:
    """Une connexion vers une IP privée n'est jamais un signal réseau."""
    conn = SimpleNamespace(
        pid=888,
        status=psutil.CONN_ESTABLISHED,
        raddr=SimpleNamespace(ip="192.168.1.1", port=443),
        laddr=None,
    )
    monkeypatch.setattr(psutil, "net_connections", lambda kind=None: [conn])
    monkeypatch.setattr(
        PrivacyShield, "_describe_process",
        staticmethod(lambda pid: ("x.exe", r"C:\Users\PC\AppData\Local\Temp\x.exe")),
    )
    assert PrivacyShield().scan() == []


def test_scan_logs_findings_but_never_info_severity(monkeypatch) -> None:
    conn_warning = SimpleNamespace(
        pid=1, status=psutil.CONN_ESTABLISHED,
        raddr=SimpleNamespace(ip="8.8.8.8", port=443), laddr=None,
    )
    conn_info = SimpleNamespace(
        pid=2, status=psutil.CONN_LISTEN,
        laddr=SimpleNamespace(ip="0.0.0.0", port=4444), raddr=None,
    )
    monkeypatch.setattr(psutil, "net_connections", lambda kind=None: [conn_warning, conn_info])

    def _describe(pid):
        if pid == 1:
            return "x.exe", r"C:\Users\PC\AppData\Local\Temp\x.exe"
        return "inconnu.exe", r"C:\Users\PC\Downloads\inconnu.exe"

    monkeypatch.setattr(PrivacyShield, "_describe_process", staticmethod(_describe))

    logged: list[tuple[str, str]] = []
    findings = PrivacyShield(log_event=lambda t, d="": logged.append((t, d))).scan()

    assert len(findings) == 2, "les deux signaux (WARNING et INFO) sont retournés"
    assert len(logged) == 1, "seul le WARNING est journalisé, l'INFO reste silencieux"
    assert "volatile_process_online" in logged[0][0]


def test_scan_saves_the_history_when_injected(monkeypatch, history) -> None:
    """history.save() doit être appelé même quand aucune connexion externe n'existe."""
    monkeypatch.setattr(psutil, "net_connections", lambda kind=None: [])

    saved = []
    monkeypatch.setattr(history, "save", lambda: saved.append(1))

    PrivacyShield(history=history).scan()

    assert saved == [1]


# ── Rançongiciel ──────────────────────────────────────────────────────

@pytest.fixture
def watched(tmp_path, monkeypatch):
    """Un répertoire surveillé isolé — on ne touche pas aux dossiers réels."""
    from security import ransomware_watch as rw

    directory = tmp_path / "Documents"
    directory.mkdir()
    monkeypatch.setattr(rw, "_watched_directories", lambda: [directory])
    return directory


def test_ransom_extension_is_critical(watched) -> None:
    (watched / "rapport.docx.locked").write_text("x")
    findings = RansomwareWatch().scan()
    assert any(f.kind == "ransom_extension" and f.severity == CRITICAL for f in findings)


def test_ransom_note_is_detected(watched) -> None:
    (watched / "HOW_TO_DECRYPT.txt").write_text("envoyez des bitcoins")
    findings = RansomwareWatch().scan()
    assert any(f.kind == "ransom_note" for f in findings)


def test_ordinary_files_raise_nothing(watched) -> None:
    (watched / "rapport.docx").write_text("x")
    (watched / "photo.jpg").write_text("x")
    assert RansomwareWatch().scan() == []


def test_a_subdirectory_is_not_scanned_as_a_file(watched) -> None:
    """rglob('*') rend aussi les sous-dossiers : is_file() les écarte, pas un crash."""
    (watched / "sous_dossier").mkdir()
    (watched / "rapport.docx").write_text("x")
    assert RansomwareWatch().scan() == []


def test_a_file_that_disappears_mid_scan_is_skipped(watched, monkeypatch) -> None:
    """Course avec un autre process (fichier supprimé entre rglob et stat) : pas de crash."""
    (watched / "rapport.docx").write_text("x")
    import pathlib

    original_stat = pathlib.Path.stat

    def _flaky_stat(self, *args, **kwargs):
        if self.name == "rapport.docx":
            raise OSError("fichier disparu entre-temps")
        return original_stat(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "stat", _flaky_stat)
    assert RansomwareWatch().scan() == []


def test_burst_of_modifications_is_a_warning_not_critical(watched, monkeypatch) -> None:
    """
    Une sauvegarde produit le même motif qu'un chiffrement. Crier au
    rançongiciel à chaque synchro rendrait le capteur inutile.
    """
    from security import ransomware_watch as rw

    monkeypatch.setattr(rw, "RANSOMWARE_BURST_THRESHOLD", 5)
    for i in range(6):
        (watched / f"fichier_{i}.txt").write_text("x")

    findings = RansomwareWatch().scan()
    burst = [f for f in findings if f.kind == "mass_modification"]
    assert len(burst) == 1
    assert burst[0].severity == WARNING


def test_old_files_do_not_count_as_a_burst(watched, monkeypatch) -> None:
    import os

    from security import ransomware_watch as rw

    monkeypatch.setattr(rw, "RANSOMWARE_BURST_THRESHOLD", 3)
    old = time.time() - 3600
    for i in range(5):
        path = watched / f"vieux_{i}.txt"
        path.write_text("x")
        os.utime(path, (old, old))

    assert not [f for f in RansomwareWatch().scan() if f.kind == "mass_modification"]


# ── Rançongiciel : fichiers-appâts ────────────────────────────────────

def test_canary_deployment_is_idempotent(watched) -> None:
    watch = RansomwareWatch()
    first = watch.deploy_canaries()
    second = watch.deploy_canaries()
    assert first == second
    assert len(list(watched.glob("*"))) == 1


def test_intact_canary_raises_nothing(watched) -> None:
    watch = RansomwareWatch()
    watch.deploy_canaries()
    assert not [f for f in watch.scan() if f.kind.startswith("canary")]


def test_modified_canary_is_critical(watched) -> None:
    from security.ransomware_watch import CANARY_FILENAME

    watch = RansomwareWatch()
    watch.deploy_canaries()
    (watched / CANARY_FILENAME).write_text("contenu chiffre")

    findings = watch.scan()
    assert any(f.kind == "canary_modified" and f.severity == CRITICAL for f in findings)


def test_scan_never_deploys_canaries(watched) -> None:
    """
    Aucun fichier ne doit apparaître dans les dossiers de Cyril sans qu'il
    l'ait décidé : deploy_canaries() est un acte délibéré.
    """
    RansomwareWatch().scan()
    assert list(watched.glob("*")) == []


# ── Rançongiciel : le contenu des fichiers n'est jamais lu ────────────

def test_user_file_contents_are_never_read(watched) -> None:
    """
    Choix de conception : détection sur métadonnées uniquement. L'analyse
    d'entropie serait plus fiable mais obligerait à ouvrir les documents
    personnels — décision qui revient à Cyril.
    """
    secret = "IBAN FR76 3000 4000 0512 3456 7890 123"
    (watched / "releve.txt.locked").write_text(secret)

    findings = RansomwareWatch().scan()
    assert findings, "le fichier doit être signalé par son extension"
    for finding in findings:
        assert secret not in finding.summary
        assert secret not in str(finding.evidence)


def test_metadata_scan_opens_no_user_file() -> None:
    """Garde-fou structurel : aucune lecture de contenu dans _scan_metadata."""
    source = inspect.getsource(RansomwareWatch._scan_metadata)
    for call in ("read_text", "read_bytes", "open(", "entropy"):
        assert call not in source


def test_budget_is_shared_between_directories(tmp_path, monkeypatch) -> None:
    """
    Le plafond de parcours se répartit par répertoire. Sinon un Bureau
    chargé épuiserait le quota et les autres dossiers ne seraient jamais
    regardés — c'est exactement ce qui se passait avant correction.
    """
    from security import ransomware_watch as rw

    gros = tmp_path / "Gros"
    petit = tmp_path / "Petit"
    gros.mkdir()
    petit.mkdir()
    for i in range(40):
        (gros / f"f{i}.txt").write_text("x")
    (petit / "rapport.docx.locked").write_text("x")

    monkeypatch.setattr(rw, "_watched_directories", lambda: [gros, petit])
    monkeypatch.setattr(rw, "RANSOMWARE_MAX_FILES_SCANNED", 20)

    findings = RansomwareWatch().scan()
    assert any(f.kind == "ransom_extension" for f in findings), (
        "le second répertoire doit être examiné malgré le premier"
    )


def test_no_watched_directory_returns_nothing(monkeypatch) -> None:
    from security import ransomware_watch as rw

    monkeypatch.setattr(rw, "_watched_directories", list)
    assert RansomwareWatch().scan() == []


def test_truncated_scan_says_so(watched, monkeypatch) -> None:
    """Un balayage incomplet ne doit pas passer pour un balayage rassurant."""
    from security import ransomware_watch as rw

    monkeypatch.setattr(rw, "RANSOMWARE_MAX_FILES_SCANNED", 3)
    for i in range(10):
        (watched / f"f{i}.txt").write_text("x")

    findings = RansomwareWatch().scan()
    assert any(f.kind == "scan_truncated" for f in findings)


def test_truncated_scan_info_is_not_logged(watched, monkeypatch) -> None:
    """scan_truncated est INFO : visible dans les findings, jamais dans les événements."""
    from security import ransomware_watch as rw

    monkeypatch.setattr(rw, "RANSOMWARE_MAX_FILES_SCANNED", 3)
    for i in range(10):
        (watched / f"f{i}.txt").write_text("x")

    events: list[tuple[str, str]] = []
    RansomwareWatch(log_event=lambda t, d="": events.append((t, d))).scan()
    assert events == []


def test_findings_reach_the_event_log(watched) -> None:
    events: list[tuple[str, str]] = []
    (watched / "doc.locked").write_text("x")
    RansomwareWatch(log_event=lambda t, d="": events.append((t, d))).scan()
    assert "security_ransom_extension" in [t for t, _ in events]


# ── Rançongiciel : résolution des dossiers réels (04/08/2026) ──────────
#
# Tous les tests ci-dessus remplacent _watched_directories() par une
# fausse fonction entière — nécessaire pour scanner un tmp_path isolé,
# mais ça laisse _resolve_shell_folder() (redirection OneDrive via le
# registre) et le vrai corps de _watched_directories() (repli sur
# Path.home(), déduplication) jamais exécutés. Trouvé via mesure de
# couverture réelle, même motif que security/persistence_watch.py.

def test_resolve_shell_folder_reads_the_redirected_path(monkeypatch, tmp_path) -> None:
    import winreg

    from security.ransomware_watch import _resolve_shell_folder

    class _FakeKey:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    monkeypatch.setattr(winreg, "OpenKey", lambda *a, **k: _FakeKey())
    monkeypatch.setattr(winreg, "QueryValueEx", lambda key, name: (str(tmp_path), None))

    assert _resolve_shell_folder("Documents") == tmp_path


def test_resolve_shell_folder_returns_none_for_an_unknown_name() -> None:
    from security.ransomware_watch import _resolve_shell_folder

    assert _resolve_shell_folder("Vidéos") is None


def test_resolve_shell_folder_returns_none_when_registry_key_missing(monkeypatch) -> None:
    import winreg

    from security.ransomware_watch import _resolve_shell_folder

    def _raise(*a, **k):
        raise OSError("clé absente")

    monkeypatch.setattr(winreg, "OpenKey", _raise)

    assert _resolve_shell_folder("Documents") is None


def test_watched_directories_falls_back_to_home_when_not_redirected(monkeypatch, tmp_path) -> None:
    """Registre muet (pas de redirection OneDrive) : repli sur ~/Documents, etc."""
    from security import ransomware_watch as rw

    home_docs = tmp_path / "Documents"
    home_docs.mkdir()

    monkeypatch.setattr(rw, "RANSOMWARE_WATCH_DIRS", ["Documents"])
    monkeypatch.setattr(rw, "_resolve_shell_folder", lambda name: None)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert rw._watched_directories() == [home_docs]


def test_watched_directories_skips_a_folder_that_does_not_exist(monkeypatch, tmp_path) -> None:
    """Ni redirigé ni présent sous le profil : ignoré, pas une erreur."""
    from security import ransomware_watch as rw

    monkeypatch.setattr(rw, "RANSOMWARE_WATCH_DIRS", ["Documents", "Desktop"])
    monkeypatch.setattr(rw, "_resolve_shell_folder", lambda name: None)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / "Desktop").mkdir()  # Documents n'existe pas

    assert rw._watched_directories() == [tmp_path / "Desktop"]


# ── Rançongiciel : cas d'échec des fichiers-appâts ─────────────────────

def test_deploy_canaries_skips_a_read_only_directory(watched, monkeypatch) -> None:
    """Un répertoire où l'écriture échoue ne doit pas faire échouer le déploiement."""
    real_write_text = Path.write_text

    def _maybe_fail(self, *args, **kwargs):
        if self.parent == watched:
            raise OSError("accès refusé")
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _maybe_fail)

    assert RansomwareWatch().deploy_canaries() == []


def test_unreadable_canary_is_critical(watched) -> None:
    """
    Un appât devenu illisible (encodage cassé — même symptôme qu'un
    chiffrement en cours) doit alerter, pas juste être ignoré.
    """
    from security.ransomware_watch import CANARY_FILENAME

    watch = RansomwareWatch()
    watch.deploy_canaries()
    (watched / CANARY_FILENAME).write_bytes(b"\xff\xfe\x00\xff garbage binaire")

    findings = watch.scan()
    assert any(f.kind == "canary_unreadable" and f.severity == CRITICAL for f in findings)


# ── Surveillance continue : déduplication ─────────────────────────────

@pytest.fixture
def monitor(tmp_path):
    from security.monitor import SecurityMonitor

    events: list[tuple[str, str]] = []
    mon = SecurityMonitor(
        log_event=lambda t, d="": events.append((t, d)),
        state_path=tmp_path / "state.json",
    )
    return mon, events


def _finding(kind="x", pid=1, severity=CRITICAL) -> Finding:
    return Finding(severity, kind, "quelque chose", {"process": "a.exe", "pid": pid})


def test_a_new_finding_is_reported_once(monitor) -> None:
    mon, events = monitor
    assert len(mon._report_new([_finding()])) == 1
    assert len(events) == 1


def test_the_same_finding_is_not_reported_twice(monitor) -> None:
    """
    Le cœur du problème d'une surveillance continue : un signal permanent
    et légitime rapporté toutes les 5 minutes chasserait tout le reste du
    contexte de Luca's, et Cyril cesserait de lire les rapports.
    """
    mon, events = monitor
    mon._report_new([_finding()])
    assert mon._report_new([_finding()]) == []
    assert len(events) == 1


def test_pid_change_does_not_recreate_an_alert(monitor) -> None:
    """Un programme redémarre et change de PID : ce n'est pas un fait nouveau."""
    mon, _events = monitor
    mon._report_new([_finding(pid=100)])
    assert mon._report_new([_finding(pid=999)]) == []


def test_a_genuinely_different_finding_is_reported(monitor) -> None:
    mon, _events = monitor
    mon._report_new([_finding(kind="a")])
    assert len(mon._report_new([_finding(kind="b")])) == 1


def test_state_survives_a_restart(tmp_path) -> None:
    """Sans persistance, chaque redémarrage du daemon rejouerait tout."""
    from security.monitor import SecurityMonitor

    state = tmp_path / "state.json"
    first = SecurityMonitor(state_path=state)
    first._report_new([_finding()])

    second = SecurityMonitor(state_path=state)
    assert second._report_new([_finding()]) == []


def test_forgotten_findings_are_reported_again(tmp_path, monkeypatch) -> None:
    """
    Un programme suspect qui disparaît puis revient trois jours plus tard
    est une information, pas un doublon.
    """
    from security import monitor as mon_module
    from security.monitor import SecurityMonitor

    state = tmp_path / "state.json"
    first = SecurityMonitor(state_path=state)
    first._report_new([_finding()])

    monkeypatch.setattr(mon_module, "FORGET_AFTER_SECONDS", -1)
    second = SecurityMonitor(state_path=state)
    assert len(second._report_new([_finding()])) == 1


def test_info_findings_are_returned_but_not_logged(monitor) -> None:
    """Un INFO mérite le rapport, pas une ligne en base à chaque fois."""
    mon, events = monitor
    fresh = mon._report_new([_finding(severity=INFO)])
    assert len(fresh) == 1
    assert events == []


def test_corrupted_state_file_does_not_crash(tmp_path) -> None:
    from security.monitor import SecurityMonitor

    state = tmp_path / "state.json"
    state.write_text("ceci n'est pas du json", encoding="utf-8")
    assert SecurityMonitor(state_path=state)._seen == {}


def test_scan_runtime_combines_guardian_and_privacy_shield(monitor, monkeypatch) -> None:
    """scan_runtime() n'était jamais appelé dans aucun test — seul _report_new() l'était directement."""
    mon, _events = monitor
    monkeypatch.setattr(mon.guardian, "scan", lambda: [_finding(kind="guardian_signal")])
    monkeypatch.setattr(mon.privacy_shield, "scan", lambda: [_finding(kind="privacy_signal")])

    kinds = {f.kind for f in mon.scan_runtime()}
    assert kinds == {"guardian_signal", "privacy_signal"}


def test_scan_all_combines_the_four_sensors(monitor, monkeypatch) -> None:
    """scan_all() n'était jamais appelé dans aucun test."""
    mon, _events = monitor
    monkeypatch.setattr(mon.guardian, "scan", lambda: [_finding(kind="guardian_signal")])
    monkeypatch.setattr(mon.privacy_shield, "scan", lambda: [_finding(kind="privacy_signal")])
    monkeypatch.setattr(mon.ransomware_watch, "scan", lambda: [_finding(kind="ransomware_signal")])
    monkeypatch.setattr(mon.persistence_watch, "scan", lambda: [_finding(kind="persistence_signal")])

    kinds = {f.kind for f in mon.scan_all()}
    assert kinds == {
        "guardian_signal", "privacy_signal", "ransomware_signal", "persistence_signal",
    }


def test_save_state_failure_does_not_raise(monitor, monkeypatch) -> None:
    """Un état non sauvegardé fait re-signaler au prochain balayage, ne doit jamais planter celui-ci."""
    from pathlib import Path

    mon, _events = monitor

    def _raise(self, *a, **k):
        raise OSError("disque plein")

    monkeypatch.setattr(Path, "write_text", _raise)

    mon._report_new([_finding()])  # ne doit pas lever


def test_forget_all_makes_everything_reportable(monitor) -> None:
    mon, _events = monitor
    mon._report_new([_finding()])
    mon.forget_all()
    assert len(mon._report_new([_finding()])) == 1


def test_monitor_never_acts() -> None:
    """Le moniteur n'agit pas davantage que les capteurs qu'il orchestre."""
    from security import monitor as mon_module

    source = inspect.getsource(mon_module)
    for call in ("kill(", "terminate(", "shutdown(", "suspend("):
        assert call not in source


# ── Mémoire des comportements ─────────────────────────────────────────

@pytest.fixture
def history(tmp_path, monkeypatch):
    """Historique sur fichier temporaire, apprentissage déjà terminé."""
    from security import history as history_module
    from security.history import BehaviourHistory

    monkeypatch.setattr(history_module, "SECURITY_LEARNING_HOURS", 0)
    return BehaviourHistory(tmp_path / "history.json")


def test_first_observation_is_new(history) -> None:
    assert history.is_new("net|chrome.exe|8.8.8.8")


def test_second_observation_is_not_new(history) -> None:
    """L'ordre compte : répondre puis enregistrer, jamais l'inverse."""
    history.is_new("net|chrome.exe|8.8.8.8")
    assert not history.is_new("net|chrome.exe|8.8.8.8")


def test_learning_period_observes_without_alerting(tmp_path, monkeypatch) -> None:
    """
    Sans période d'apprentissage, le premier balayage signalerait chaque
    programme de la machine. Le rapport serait illisible.
    """
    from security import history as history_module
    from security.history import BehaviourHistory

    monkeypatch.setattr(history_module, "SECURITY_LEARNING_HOURS", 24)
    learning = BehaviourHistory(tmp_path / "h.json")

    assert learning.is_learning
    assert not learning.is_new("net|inconnu.exe|1.1.1.1"), "rien ne doit être signalé"
    assert learning.has_seen("net|inconnu.exe|1.1.1.1"), "mais tout doit être mémorisé"


def test_history_survives_a_restart(tmp_path, monkeypatch) -> None:
    from security import history as history_module
    from security.history import BehaviourHistory

    monkeypatch.setattr(history_module, "SECURITY_LEARNING_HOURS", 0)
    path = tmp_path / "h.json"

    first = BehaviourHistory(path)
    first.is_new("net|a.exe|1.1.1.1")
    first.save()

    assert not BehaviourHistory(path).is_new("net|a.exe|1.1.1.1")


def test_state_paths_are_anchored_to_the_project() -> None:
    """
    Le daemon est prévu en service Windows via NSSM, donc lancé depuis un
    CWD quelconque. Un chemin relatif faisait atterrir l'état ailleurs à
    chaque lancement : la période d'apprentissage repartait de zéro et la
    déduplication aussi — la mémoire devenait inopérante précisément dans
    son déploiement cible.
    """
    from security.history import DEFAULT_HISTORY_PATH
    from security.monitor import DEFAULT_STATE_PATH

    for path in (DEFAULT_HISTORY_PATH, DEFAULT_STATE_PATH):
        assert path.is_absolute(), f"{path} doit être un chemin absolu"
        assert path.parent.name == "data"


def test_corrupted_history_starts_empty(tmp_path) -> None:
    """Perdre la mémoire dégrade la détection ; planter la supprime."""
    from security.history import BehaviourHistory

    path = tmp_path / "h.json"
    path.write_text("ceci n'est pas du json", encoding="utf-8")
    assert len(BehaviourHistory(path)) == 0


def test_old_entries_are_purged(tmp_path, monkeypatch) -> None:
    """Un comportement oublié redevient un signal à son retour."""
    import json
    import time

    from security import history as history_module
    from security.history import BehaviourHistory

    monkeypatch.setattr(history_module, "SECURITY_HISTORY_RETENTION_DAYS", 30)
    ancient = time.time() - 40 * 86400
    path = tmp_path / "h.json"
    path.write_text(
        json.dumps({
            "started_at": ancient,
            "entries": {"net|vieux.exe|1.1.1.1": {"first_seen": ancient, "last_seen": ancient}},
        }),
        encoding="utf-8",
    )

    assert len(BehaviourHistory(path)) == 0


def test_history_starts_empty_when_the_json_is_not_an_object(tmp_path) -> None:
    """Un JSON valide mais qui n'est pas un objet (liste, nombre...) doit aussi repartir à vide."""
    from security.history import BehaviourHistory

    path = tmp_path / "h.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert len(BehaviourHistory(path)) == 0


def test_save_failure_does_not_raise(monkeypatch, tmp_path) -> None:
    """Un historique non sauvegardé dégrade le prochain balayage, ne doit jamais planter celui-ci."""
    from pathlib import Path

    from security.history import BehaviourHistory

    history = BehaviourHistory(tmp_path / "h.json")
    history.remember("net|chrome.exe|8.8.8.8")

    def _raise(self, *a, **k):
        raise OSError("disque plein")

    monkeypatch.setattr(Path, "write_text", _raise)

    history.save()  # ne doit pas lever


def test_learning_remaining_hours_counts_down(tmp_path, monkeypatch) -> None:
    import time

    from security import history as history_module
    from security.history import BehaviourHistory

    monkeypatch.setattr(history_module, "SECURITY_LEARNING_HOURS", 24)
    learning = BehaviourHistory(tmp_path / "h.json")
    learning._started_at = time.time() - 3600  # une heure déjà écoulée

    remaining = learning.learning_remaining_hours()
    assert 22.9 < remaining < 23.1


def test_learning_remaining_hours_never_negative(history) -> None:
    """La période est déjà terminée (fixture history) : jamais un compte à rebours négatif."""
    assert history.learning_remaining_hours() == 0.0


# ── Premier contact externe ───────────────────────────────────────────

def test_first_external_contact_is_flagged(history) -> None:
    finding = PrivacyShield(history=history)._check_first_external_contact(
        "inconnu.exe", r"C:\App\inconnu.exe", "8.8.8.8"
    )
    assert finding is not None
    assert finding.severity == WARNING


def test_known_contact_is_silent(history) -> None:
    shield = PrivacyShield(history=history)
    shield._check_first_external_contact("chrome.exe", "", "8.8.8.8")
    assert shield._check_first_external_contact("chrome.exe", "", "8.8.8.8") is None


def test_source_port_changes_do_not_create_noise(history) -> None:
    """
    La clé ne retient que (programme, IP). Inclure le port source ferait
    paraître tout nouveau à chaque connexion.
    """
    shield = PrivacyShield(history=history)
    assert shield._check_first_external_contact("a.exe", "", "8.8.8.8") is not None
    assert shield._check_first_external_contact("a.exe", "", "8.8.8.8") is None


def test_two_different_ips_are_two_facts(history) -> None:
    shield = PrivacyShield(history=history)
    first = shield._check_first_external_contact("a.exe", "", "8.8.8.8")
    second = shield._check_first_external_contact("a.exe", "", "1.1.1.1")
    assert first is not None and second is not None

    kept = PrivacyShield._deduplicate([first, second])
    assert len(kept) == 2, "deux IP nouvelles ne doivent pas être fondues en une"


def test_without_history_the_sensor_keeps_level_0_behaviour() -> None:
    assert PrivacyShield()._check_first_external_contact("a.exe", "", "8.8.8.8") is None


# ── Persistance au démarrage ──────────────────────────────────────────

def test_autostart_from_a_temp_directory_is_critical(history) -> None:
    watch = PersistenceWatch(history=history)
    assert watch._is_volatile(r"C:\Users\PC\AppData\Local\Temp\x.exe")


def test_autostart_from_program_files_is_normal(history) -> None:
    watch = PersistenceWatch(history=history)
    assert not watch._is_volatile(r"C:\Program Files\App\app.exe")


def test_volatile_autostart_is_reported(monkeypatch, history) -> None:
    from security import persistence_watch as pw

    monkeypatch.setattr(
        pw, "_read_registry_autostarts",
        lambda: [("HKCU\\Run", "truc", r"C:\Users\PC\AppData\Local\Temp\truc.exe")],
    )
    monkeypatch.setattr(pw, "_read_startup_folder", list)

    findings = PersistenceWatch(history=history).scan()
    assert any(f.kind == "autostart_volatile" and f.severity == CRITICAL for f in findings)


def test_new_autostart_entry_is_reported_once(monkeypatch, history) -> None:
    from security import persistence_watch as pw

    monkeypatch.setattr(
        pw, "_read_registry_autostarts",
        lambda: [("HKCU\\Run", "MonApp", r"C:\Program Files\MonApp\app.exe")],
    )
    monkeypatch.setattr(pw, "_read_startup_folder", list)

    watch = PersistenceWatch(history=history)
    first = [f.kind for f in watch.scan()]
    second = [f.kind for f in watch.scan()]

    assert "autostart_new" in first
    assert "autostart_new" not in second, "une entrée connue ne doit plus alerter"


def test_inventory_is_reported_as_info(monkeypatch, history) -> None:
    from security import persistence_watch as pw

    monkeypatch.setattr(
        pw, "_read_registry_autostarts",
        lambda: [("HKCU\\Run", "A", r"C:\Program Files\a.exe")],
    )
    monkeypatch.setattr(pw, "_read_startup_folder", list)

    findings = PersistenceWatch(history=history).scan()
    inventory = [f for f in findings if f.kind == "autostart_inventory"]
    assert inventory and inventory[0].severity == INFO


def test_persistence_watch_never_writes_to_the_registry() -> None:
    """Observation seule : le module lit le registre, il n'y écrit jamais."""
    import inspect

    from security import persistence_watch

    source = inspect.getsource(persistence_watch)
    for forbidden in ("SetValue", "CreateKey", "DeleteKey", "DeleteValue"):
        assert forbidden not in source


def test_unreadable_registry_degrades_instead_of_raising(monkeypatch, history) -> None:
    """
    Le moniteur enchaîne ce capteur avec celui du rançongiciel dans
    scan_filesystem() : une exception ici ferait perdre les résultats de
    l'autre. Le capteur signale son indisponibilité et rend la main.
    """
    from security import persistence_watch as pw

    def denied():
        raise OSError("accès refusé")

    monkeypatch.setattr(pw, "_read_registry_autostarts", denied)
    monkeypatch.setattr(pw, "_read_startup_folder", list)

    findings = PersistenceWatch(history=history).scan()
    assert [f.kind for f in findings] == ["autostart_scan_unavailable"]


def test_one_broken_sensor_does_not_hide_the_others(monkeypatch, tmp_path) -> None:
    """
    Garde d'intégration : un capteur en échec ne doit pas emporter le
    résultat des autres dans le même balayage.
    """
    from security import persistence_watch as pw
    from security.monitor import SecurityMonitor

    def denied():
        raise OSError("registre illisible")

    monkeypatch.setattr(pw, "_read_registry_autostarts", denied)
    monkeypatch.setattr(pw, "_read_startup_folder", list)

    monitor = SecurityMonitor(state_path=tmp_path / "state.json")
    monkeypatch.setattr(
        monitor.ransomware_watch, "scan",
        lambda: [Finding(CRITICAL, "ransom_extension", "fichier chiffré", {"exemple": "x"})],
    )

    kinds = [f.kind for f in monitor.scan_filesystem()]
    assert "ransom_extension" in kinds, "le signal du rançongiciel doit survivre"


# ── Persistance : internes du registre (04/08/2026) ────────────────────
#
# Tous les tests ci-dessus remplacent _read_registry_autostarts() et
# _read_startup_folder() par de FAUSSES fonctions entières — utile pour
# tester scan(), mais ça laisse leur vrai contenu (parcours des ruches,
# arrêt sur OSError, résolution du dossier Démarrage) jamais exécuté.
# Trouvé via mesure de couverture réelle (pytest-cov) : ces deux
# fonctions étaient les moins couvertes de tout le paquet security/.
# winreg est un vrai module Windows ici (pas un stub) — ses fonctions
# sont mockées individuellement pour exercer le vrai corps des fonctions.

class _FakeRegistryKey:
    """Imite un handle winreg utilisable en `with ... as key:`."""

    def __init__(self, entries: list[tuple[str, str]] | None = None) -> None:
        self.entries = entries or []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> bool:
        return False


def test_read_registry_autostarts_parses_multiple_hives(monkeypatch) -> None:
    import winreg

    from security.persistence_watch import _read_registry_autostarts

    run_key_hkcu = _FakeRegistryKey([("AppA", r"C:\Program Files\a.exe")])
    run_key_hklm = _FakeRegistryKey([("AppB", r"C:\Windows\b.exe")])

    monkeypatch.setattr(winreg, "HKEY_CURRENT_USER", "HKCU_SENTINEL")
    monkeypatch.setattr(winreg, "HKEY_LOCAL_MACHINE", "HKLM_SENTINEL")

    def fake_open_key(hive, subkey):
        if hive == "HKCU_SENTINEL" and subkey.endswith(r"\Run"):
            return run_key_hkcu
        if hive == "HKLM_SENTINEL" and subkey.endswith(r"\Run"):
            return run_key_hklm
        raise OSError("clé absente (RunOnce, non peuplée dans ce test)")

    def fake_enum_value(key, index):
        if index >= len(key.entries):
            raise OSError("plus d'entrées")
        name, value = key.entries[index]
        return name, value, 1  # REG_SZ

    monkeypatch.setattr(winreg, "OpenKey", fake_open_key)
    monkeypatch.setattr(winreg, "EnumValue", fake_enum_value)

    entries = _read_registry_autostarts()

    names = {name for _source, name, _command in entries}
    assert names == {"AppA", "AppB"}, (
        "les deux ruches (HKCU et HKLM) doivent être parcourues, "
        "RunOnce absent doit être ignoré sans faire échouer le reste"
    )


def test_read_registry_autostarts_returns_empty_without_winreg(monkeypatch) -> None:
    """Hors Windows (ou winreg indisponible), un capteur muet plutôt qu'une exception."""
    import builtins

    from security import persistence_watch as pw

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "winreg":
            raise ImportError("pas de winreg ici")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    assert pw._read_registry_autostarts() == []
    assert pw._read_startup_folder() == []


def test_read_startup_folder_lists_files_but_not_subdirectories(monkeypatch, tmp_path) -> None:
    import winreg

    from security.persistence_watch import _read_startup_folder

    (tmp_path / "raccourci.lnk").write_text("contenu")
    (tmp_path / "sous_dossier").mkdir()

    monkeypatch.setattr(winreg, "OpenKey", lambda *a, **k: _FakeRegistryKey())
    monkeypatch.setattr(winreg, "QueryValueEx", lambda key, name: (str(tmp_path), None))

    names = {name for _source, name, _command in _read_startup_folder()}
    assert names == {"raccourci.lnk"}, "un sous-dossier n'est pas un raccourci de démarrage"


def test_read_startup_folder_empty_when_registry_key_missing(monkeypatch) -> None:
    import winreg

    from security.persistence_watch import _read_startup_folder

    def _raise(*a, **k):
        raise OSError("clé absente")

    monkeypatch.setattr(winreg, "OpenKey", _raise)

    assert _read_startup_folder() == []


def test_read_startup_folder_empty_when_path_does_not_exist(monkeypatch, tmp_path) -> None:
    import winreg

    from security.persistence_watch import _read_startup_folder

    missing = tmp_path / "n_existe_pas"
    monkeypatch.setattr(winreg, "OpenKey", lambda *a, **k: _FakeRegistryKey())
    monkeypatch.setattr(winreg, "QueryValueEx", lambda key, name: (str(missing), None))

    assert _read_startup_folder() == []


def test_persistence_watch_logs_non_info_findings_only(history) -> None:
    logged: list[tuple[str, str]] = []
    watch = PersistenceWatch(
        log_event=lambda t, d="": logged.append((t, d)), history=history
    )
    findings = [
        Finding(CRITICAL, "autostart_volatile", "danger", {"entree": "x"}),
        Finding(INFO, "autostart_inventory", "juste un inventaire", {"total": 1}),
    ]

    watch._log(findings)

    assert len(logged) == 1 and "autostart_volatile" in logged[0][0], (
        "un INFO ne doit jamais atteindre system_events — trop bruyant pour un simple inventaire"
    )


# ── Rapport ───────────────────────────────────────────────────────────

def test_empty_report_is_reassuring_not_empty() -> None:
    assert "Aucun signal" in format_report([])


def test_report_states_that_nothing_was_done() -> None:
    """Cyril doit toujours savoir qu'aucune action n'a été prise."""
    report = format_report([Finding(CRITICAL, "x", "quelque chose", {"pid": 1})])
    assert "Observation seule" in report


def test_findings_are_sorted_most_severe_first() -> None:
    findings = [
        Finding(INFO, "a", "info"),
        Finding(CRITICAL, "b", "critique"),
        Finding(WARNING, "c", "attention"),
    ]
    assert [f.severity for f in sort_findings(findings)] == [CRITICAL, WARNING, INFO]


def test_event_details_are_truncated() -> None:
    """La table system_events ne doit pas devenir un dépotoir."""
    finding = Finding(CRITICAL, "x", "y" * 500, {"chemin": "z" * 500})
    _, details = finding.as_event()
    assert len(details) <= 200


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
