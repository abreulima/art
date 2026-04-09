import json
import math
import socket
import time
from typing import Any, Dict, List

import pyray as rl


# ==========================================
# Configuração
# ==========================================
SERVER_HOST = "192.168.1.81"
SERVER_PORT = 5550
SERVER_ADDR = (SERVER_HOST, SERVER_PORT)

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
TITLE = "Cliente UDP - Multiplayer com Projeteis"

PLAYER_SPEED = 250.0
NETWORK_INTERVAL = 0.05
SHOOT_COOLDOWN = 0.2

PLAYER_RADIUS = 18
PROJECTILE_DEFAULT_RADIUS = 6

PLAYER_NAME = "Player1"
PLAYER_IMAGE = "players/player.png"  # compatibilidade com o servidor


# ==========================================
# Utilidades
# ==========================================
def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return default
        num = float(value)
        if math.isnan(num) or math.isinf(num):
            return default
        return num
    except Exception:
        return default


def normalize_vector(x: float, y: float) -> tuple[float, float]:
    length = math.hypot(x, y)
    if length <= 0.0001:
        return 0.0, 0.0
    return x / length, y / length


def send_json(sock: socket.socket, payload: Dict[str, Any]) -> None:
    try:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        sock.sendto(raw, SERVER_ADDR)
    except Exception:
        pass


# ==========================================
# Cliente principal
# ==========================================
def main() -> None:
    rl.init_window(SCREEN_WIDTH, SCREEN_HEIGHT, TITLE)
    rl.set_target_fps(60)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.001)

    local_player: Dict[str, Any] = {
        "name": PLAYER_NAME,
        "image": PLAYER_IMAGE,
        "x": SCREEN_WIDTH / 2,
        "y": SCREEN_HEIGHT / 2,
    }

    world_players: List[Dict[str, Any]] = []
    world_projectiles: List[Dict[str, Any]] = []

    last_network_time = 0.0
    last_shot_time = 0.0

    while not rl.window_should_close():
        dt = rl.get_frame_time()
        now = time.time()

        # ==========================================
        # Movimento
        # ==========================================
        move_x = 0.0
        move_y = 0.0

        if rl.is_key_down(rl.KeyboardKey.KEY_W):
            move_y -= 1.0
        if rl.is_key_down(rl.KeyboardKey.KEY_S):
            move_y += 1.0
        if rl.is_key_down(rl.KeyboardKey.KEY_A):
            move_x -= 1.0
        if rl.is_key_down(rl.KeyboardKey.KEY_D):
            move_x += 1.0

        move_x, move_y = normalize_vector(move_x, move_y)

        local_player["x"] += move_x * PLAYER_SPEED * dt
        local_player["y"] += move_y * PLAYER_SPEED * dt

        local_player["x"] = clamp(local_player["x"], PLAYER_RADIUS, SCREEN_WIDTH - PLAYER_RADIUS)
        local_player["y"] = clamp(local_player["y"], PLAYER_RADIUS, SCREEN_HEIGHT - PLAYER_RADIUS)

        # ==========================================
        # Disparo
        # ==========================================
        if rl.is_mouse_button_down(rl.MouseButton.MOUSE_BUTTON_LEFT):
            if now - last_shot_time >= SHOOT_COOLDOWN:
                mouse_pos = rl.get_mouse_position()
                dx = mouse_pos.x - float(local_player["x"])
                dy = mouse_pos.y - float(local_player["y"])
                dx, dy = normalize_vector(dx, dy)

                if dx != 0.0 or dy != 0.0:
                    shoot_payload = {
                        "type": "shoot",
                        "name": local_player["name"],
                        "x": local_player["x"],
                        "y": local_player["y"],
                        "dx": dx,
                        "dy": dy,
                    }
                    send_json(sock, shoot_payload)
                    last_shot_time = now

        # ==========================================
        # Update de rede
        # ==========================================
        if now - last_network_time >= NETWORK_INTERVAL:
            update_payload = {
                "type": "update",
                "name": local_player["name"],
                "image": local_player["image"],
                "x": local_player["x"],
                "y": local_player["y"],
            }
            send_json(sock, update_payload)
            last_network_time = now

        # ==========================================
        # Recebimento do estado do mundo
        # ==========================================
        while True:
            try:
                raw_data, _addr = sock.recvfrom(65535)
            except socket.timeout:
                break
            except BlockingIOError:
                break
            except Exception:
                break

            try:
                message = json.loads(raw_data.decode("utf-8"))
            except Exception:
                continue

            if not isinstance(message, dict):
                continue

            if message.get("type") == "world":
                players_data = message.get("players", [])
                projectiles_data = message.get("projectiles", [])

                if isinstance(players_data, list):
                    world_players = players_data

                if isinstance(projectiles_data, list):
                    world_projectiles = projectiles_data

        # ==========================================
        # Render
        # ==========================================
        rl.begin_drawing()
        rl.clear_background(rl.Color(30, 30, 40, 255))

        # projéteis
        for projectile in world_projectiles:
            px = int(safe_float(projectile.get("x"), 0.0))
            py = int(safe_float(projectile.get("y"), 0.0))
            radius = int(safe_float(projectile.get("radius"), PROJECTILE_DEFAULT_RADIUS))
            rl.draw_circle(px, py, float(radius), rl.GOLD)

        # jogadores
        for player in world_players:
            name = str(player.get("name", ""))
            x = int(safe_float(player.get("x"), 0.0))
            y = int(safe_float(player.get("y"), 0.0))

            color = rl.SKYBLUE
            if name == local_player["name"]:
                color = rl.LIME

            rl.draw_circle(x, y, float(PLAYER_RADIUS), color)
            rl.draw_text(name, x - 30, y - 35, 20, rl.WHITE)

        rl.draw_text("WASD move | Botao esquerdo atira", 10, 10, 20, rl.RAYWHITE)
        rl.draw_text(f"Jogador: {PLAYER_NAME}", 10, 35, 20, rl.RAYWHITE)
        rl.draw_fps(SCREEN_WIDTH - 95, 10)

        rl.end_drawing()

    sock.close()
    rl.close_window()


if __name__ == "__main__":
    main()
