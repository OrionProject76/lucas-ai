#!/usr/bin/env python3
"""Orion3D Bridge - Service Python pour Desktop Pal Godot"""
import asyncio
import websockets
import json
import psutil
import win32gui
import win32con
import time

PORT = 8765
clients = set()

async def register(websocket):
    clients.add(websocket)
    print(f"[+] Client Godot connecte. Total: {len(clients)}")

async def unregister(websocket):
    clients.discard(websocket)
    print(f"[-] Client Godot deconnecte. Total: {len(clients)}")

async def broadcast(message: dict):
    if clients:
        msg = json.dumps(message)
        await asyncio.gather(*[c.send(msg) for c in clients if c.open])

async def system_monitor_loop():
    while True:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        gpu = 0.0
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            gpu = gpus[0].load * 100 if gpus else 0
        except:
            pass
        await broadcast({
            "type": "system",
            "cpu": round(cpu, 1),
            "ram": round(ram, 1),
            "gpu": round(gpu, 1)
        })
        await asyncio.sleep(1)

def is_fullscreen_app_running():
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return False
        rect = win32gui.GetWindowRect(hwnd)
        screen_w = win32gui.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32gui.GetSystemMetrics(win32con.SM_CYSCREEN)
        is_full = (rect[2] - rect[0] >= screen_w and rect[3] - rect[1] >= screen_h)
        title = win32gui.GetWindowText(hwnd)
        is_desktop = title in ["", "Program Manager", "Orion3D Desktop Pal"]
        return is_full and not is_desktop
    except:
        return False

async def auto_hide_loop():
    was_fullscreen = False
    while True:
        is_full = is_fullscreen_app_running()
        if is_full and not was_fullscreen:
            await broadcast({"type": "hide"})
            print("[AutoHide] Plein ecran detecte -> Orion masque")
        elif not is_full and was_fullscreen:
            await broadcast({"type": "show"})
            print("[AutoHide] Plein ecran ferme -> Orion visible")
        was_fullscreen = is_full
        await asyncio.sleep(2)

async def handler(websocket, path):
    await register(websocket)
    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get("type", "")
            if msg_type == "hello":
                print(f"[WS] Client: {data.get('client', 'unknown')}")
                await broadcast({"type": "chat", "text": "Orion3D connecte.", "from_orion": True})
            elif msg_type == "chat":
                user_text = data.get("text", "")
                print(f"[Chat] Utilisateur: {user_text}")
                await asyncio.sleep(0.5)
                await broadcast({"type": "speak", "intensity": 0.8})
                await broadcast({"type": "chat", "text": f"Message recu : {user_text}", "from_orion": True})
                await asyncio.sleep(2)
                await broadcast({"type": "idle"})
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await unregister(websocket)

async def main():
    print(f"Orion3D Bridge demarre sur ws://localhost:{PORT}")
    asyncio.create_task(system_monitor_loop())
    asyncio.create_task(auto_hide_loop())
    async with websockets.serve(handler, "localhost", PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
