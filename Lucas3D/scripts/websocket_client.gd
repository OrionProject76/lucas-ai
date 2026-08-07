extends Node

# Canal unique vers Luca's — l'API FastAPI, et non plus le service
# orion3d_bridge.py supprimé le 01/08/2026.
#
# Ce bridge était un simple écho : il répétait les messages sans jamais
# passer par Ollama. Pire, il ne démarrait plus du tout, son handler
# ayant une signature obsolète depuis websockets 12.
#
# Passer par l'API donne à l'avatar 3D ce que le bridge court-circuitait :
# le routage local/cloud, les gardes de sensibilité, la mémoire
# persistante. Le vocabulaire des messages est défini dans
# api/protocol.py, côté Python.
#
# ⚠️ 127.0.0.1 et non localhost — mesuré le 01/08 : 0,14 s contre 2,2 s,
# Windows résout « localhost » en IPv6 d'abord (voir config.py).
#
# ── wss:// et non ws://, corrigé le 07/08/2026 ──────────────────────
#
# Ce commentaire disait « sans authentification » : FAUX depuis que
# API_TOKEN a une vraie valeur dans .env (02/08) et que le serveur tourne
# en HTTPS (mkcert, 05/08 — voir justfile `serve`, tâche planifiée
# LucasAPIServer / start_server_hidden.vbs). Confirmé le 07/08 en testant
# les deux : https://127.0.0.1:8000/status répond, http:// ne répond pas
# du tout — le serveur ne parle PAS en clair aujourd'hui, quelle que soit
# l'interface. `ws://` ici a toujours été un décalage jamais corrigé
# depuis la bascule HTTPS du 05/08, pas une régression ponctuelle.
#
# Ça peut redevenir vrai un jour : si Godot se connectait un jour à un
# serveur distant en HTTP pur (aucun cas réel aujourd'hui), il faudrait
# alors resservir `ws://`. Tant que Godot tourne sur CE PC contre LE
# serveur local (toujours le cas, voir plus bas dans ce fichier), le
# schéma suit celui du serveur — pas un choix arbitraire par client.
@export var websocket_url: String = "wss://127.0.0.1:8000/ws"
@export var reconnect_interval: float = 3.0

# Même fichier que config.py (python-dotenv) — pas un nouveau système de
# secret. C:\OrionAI est déjà supposé partout ailleurs dans ce projet
# (justfile, demos/*.ps1) : pas moins portable que le reste.
const ENV_PATH := "C:/OrionAI/.env"

# ⚠️ Épinglé sur la CA racine mkcert, PAS sur data/cert.pem -- testé les
# deux, en vrai, le 07/08/2026. Épingler directement sur le certificat
# serveur (data/cert.pem) semblait plus strict sur le papier, mais
# mbedTLS (moteur TLS de Godot) le REFUSE : erreur -0x2700 au handshake,
# reproduite deux fois. mbedTLS valide une CHAÎNE jusqu'à une autorité
# reconnue, pas une correspondance exacte sur la feuille -- lui donner
# la feuille comme "chaîne de confiance" ne fournit aucune autorité
# valide pour vérifier sa propre signature. La CA racine mkcert
# fonctionne (testée, connexion établie -- voir le test de bout en bout).
# Chemin obtenu via `tools\mkcert.exe -CAROOT`, propre à cette machine
# (profil Windows de Cyril) -- à reroute si CAROOT change un jour.
const CERT_PATH := "C:/Users/PC/AppData/Local/mkcert/rootCA.pem"

var socket: WebSocketPeer
var connected: bool = false
var reconnect_timer: float = 0.0

func _ready():
	_connect_to_server()
	Global.main_ready.connect(_on_main_ready)

func _on_main_ready():
	print("WebSocket pret sur ", websocket_url)

func _process(delta: float):
	if socket:
		socket.poll()
		var state = socket.get_ready_state()
		match state:
			WebSocketPeer.STATE_OPEN:
				if not connected:
					connected = true
					print("Connecte a Lucas Backend")
					_send_heartbeat()
				# ⚠️ get_available_packets() N'EXISTE PAS. La méthode est
				# get_available_packet_count(). L'erreur ne se voyait pas à
				# la compilation — GDScript ne vérifie pas les appels
				# dynamiques — mais elle se déclenchait à CHAQUE FRAME dès
				# que la connexion s'ouvrait, remplissant le débogueur.
				# C'est ce texte qui apparaissait en surimpression.
				while socket.get_available_packet_count() > 0:
					_handle_message(socket.get_packet().get_string_from_utf8())
			WebSocketPeer.STATE_CLOSED:
				if connected:
					connected = false
					print("Deconnecte")
				_reconnect_timer(delta)
			WebSocketPeer.STATE_CONNECTING:
				pass

func _read_api_token() -> String:
	var f := FileAccess.open(ENV_PATH, FileAccess.READ)
	if f == null:
		print(".env introuvable (", ENV_PATH, ") -- connexion sans jeton")
		return ""
	while not f.eof_reached():
		var line := f.get_line()
		if line.begins_with("API_TOKEN="):
			return line.substr(len("API_TOKEN=")).strip_edges()
	return ""

# Sous-protocoles ["lucas.v1", "lucas-token.<jeton>"] -- même mécanisme
# que static/js/websocket.js et api/server.py (WS_SUBPROTOCOL,
# WS_TOKEN_SUBPROTOCOL_PREFIX). Le jeton voyage dans l'en-tête
# Sec-WebSocket-Protocol, jamais dans l'URL : il n'atterrit donc jamais
# en clair dans data/logs/server_startup.log (voir api/log_scrub.py).
func _build_supported_protocols() -> PackedStringArray:
	var token := _read_api_token()
	var protocols := PackedStringArray(["lucas.v1"])
	if token != "":
		protocols.append("lucas-token." + token)
	return protocols

# TLSOptions.client(cert) épingle sur la CA racine mkcert (CERT_PATH) :
# la connexion n'aboutit que face à un certificat signé par CETTE CA, pas
# n'importe quelle autorité publique. Si le certificat n'a pas pu être
# chargé (CAROOT déplacé, mkcert jamais lancé sur ce profil), repli sur
# client_unsafe() -- aucune validation, mais la connexion reste possible
# en attendant. Journalisé dans les deux cas, jamais silencieux.
func _build_tls_options() -> TLSOptions:
	if not websocket_url.begins_with("wss://"):
		return null
	var cert := X509Certificate.new()
	if cert.load(CERT_PATH) == OK:
		return TLSOptions.client(cert)
	print("Certificat introuvable ou invalide (", CERT_PATH, ") -- ",
		"validation TLS desactivee, repli client_unsafe")
	return TLSOptions.client_unsafe()

func _connect_to_server():
	socket = WebSocketPeer.new()
	socket.supported_protocols = _build_supported_protocols()
	var err = socket.connect_to_url(websocket_url, _build_tls_options())
	if err != OK:
		print("Erreur connexion : ", err)
	else:
		print("Connexion en cours...")

func _reconnect_timer(delta: float):
	reconnect_timer += delta
	if reconnect_timer >= reconnect_interval:
		reconnect_timer = 0.0
		print("Reconnexion...")
		_connect_to_server()

func _handle_message(msg: String):
	var json = JSON.new()
	var err = json.parse(msg)
	if err != OK:
		return
	var data = json.get_data()
	if data is Dictionary:
		match data.get("type", ""):
			"avatar_state":
				# Horodaté : c'est la preuve qu'un vrai changement d'état
				# backend traverse le pont, pas juste "le socket est ouvert"
				# (voir le test de bout en bout du 07/08/2026).
				print("[", Time.get_time_string_from_system(), "] avatar_state recu : ",
					data.get("state", "idle"))
				_apply_state(data.get("state", "idle"), data.get("text", ""))
			"chat":
				Global.chat_message_received.emit(data.get("text", ""), data.get("from_lucas", true))
			"system":
				Global.system_data_updated.emit(data.get("cpu", 0.0), data.get("ram", 0.0), data.get("gpu", 0.0))
			"error":
				Global.chat_message_received.emit("[Erreur] " + str(data.get("detail", "")), true)
			# « speak » et « idle » étaient le vocabulaire du bridge
			# supprimé. Conservés le temps que d'éventuels clients tiers
			# migrent ; l'API n'émet plus que « avatar_state ».
			"speak":
				_apply_state("speaking", "")
			"idle":
				_apply_state("idle", "")
			"show":
				WindowManager.toggle_visibility()
			"hide":
				WindowManager.toggle_visibility()

# Traduit un état de présence en signaux du bus Global.
#
# Les cinq états sont ceux de l'avatar PySide6 : une seule liste pour les
# deux interfaces, sinon elles divergent (un test Python le vérifie).
# thinking, watching et listening n'ont pas encore d'animation propre au
# visage 3D — ils sont diffusés sur lucas_state_changed pour que
# face_controller puisse s'en saisir, sans forcer la bouche à bouger
# comme si Luca's parlait.
func _apply_state(state: String, text: String):
	Global.lucas_state = state
	Global.lucas_state_changed.emit(state)

	match state:
		"speaking":
			Global.lucas_speaking.emit(0.8)
			if text != "":
				Global.chat_message_received.emit(text, true)
		"idle":
			Global.lucas_idle.emit()
		_:
			# thinking / watching / listening : le visage cesse de parler
			# sans repasser en repos complet.
			Global.lucas_idle.emit()

func send_message(data: Dictionary):
	if connected and socket:
		socket.send_text(JSON.stringify(data))

func _send_heartbeat():
	send_message({"type": "hello", "client": "lucas3d_godot", "version": "1.0"})
