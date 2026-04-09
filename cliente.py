import json
import math
import socket
import time
from typing import Dict, Any, List

import pygame


# ==========================================
# Configuração
# ==========================================
SERVER_HOST = "192.168.1.81"
SERVER_PORT = 5550
SERVER_ADDR = (SERVER_HOST, SERVER_PORT)

SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
FPS = 60

PLAYER_SPEED = 250.0
NETWORK_INTERVAL = 0.05
SHOOT_COOLDOWN = 0.2

PLAYER_NAME = "Player1"
PLAYER_IMAGE = "players/player.png"   # mantido por compatibilidade com o servidor


# ==========================================
# Utilidades
# ==========================================
def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        num = float(value)
        if math.isnan(num) or math.isinf(num):
            return default
        return num
    except Exception:
        return default


# ==========================================
# Cliente
# ==========================================
def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Cliente UDP - Multiplayer com Projetéis")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.001)

    local_player = {
        "name": PLAYER_NAME,
        "image": PLAYER_IMAGE,
        "x": SCREEN_WIDTH / 2,
        "y": SCREEN_HEIGHT / 2,
    }

    world_players: List[Dict[str, Any]] = []
    world_projectiles: List[Dict[str, Any]] = []

    running = True
    last_network_time = 0.0
    last_shot_time = 0.0

    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # ------------------------------
        # Entrada do teclado
        # ------------------------------
        keys = pygame.key.get_pressed()
        move_x = 0.0
        move_y = 0.0

        if keys[pygame.K_w]:
            move_y -= 1.0
        if keys[pygame.K_s]:
            move_y += 1.0
        if keys[pygame.K_a]:
            move_x -= 1.0
        if keys[pygame.K_d]:
            move_x += 1.0

        length = math.hypot(move_x, move_y)
        if length > 0.0:
            move_x /= length
            move_y /= length

        local_player["x"] += move_x * PLAYER_SPEED * dt
        local_player["y"] += move_y * PLAYER_SPEED * dt

        local_player["x"] = clamp(local_player["x"], 0, SCREEN_WIDTH)
        local_player["y"] = clamp(local_player["y"], 0, SCREEN_HEIGHT)

        # ------------------------------
        # Disparo com mouse
        # ------------------------------
        mouse_buttons = pygame.mouse.get_pressed()
        mouse_pos = pygame.mouse.get_pos()
        now = time.time()

        if mouse_buttons[0] and (now - last_shot_time >= SHOOT_COOLDOWN):
            dx = mouse_pos[0] - local_player["x"]
            dy = mouse_pos[1] - local_player["y"]
            length = math.hypot(dx, dy)

            if length > 0.0001:
                shoot_payload = {
                    "type": "shoot",
                    "name": local_player["name"],
                    "x": local_player["x"],
                    "y": local_player["y"],
                    "dx": dx / length,
                    "dy": dy / length,
                }

                try:
                    sock.sendto(
                        json.dumps(shoot_payload, separators=(",", ":")).encode("utf-8"),
                        SERVER_ADDR
                    )
                except Exception:
                    pass

                last_shot_time = now

        # ------------------------------
        # Envio de update
        # ------------------------------
        if now - last_network_time >= NETWORK_INTERVAL:
            update_payload = {
                "type": "update",
                "name": local_player["name"],
                "image": local_player["image"],
                "x": local_player["x"],
                "y": local_player["y"],
            }

            try:
                sock.sendto(
                    json.dumps(update_payload, separators=(",", ":")).encode("utf-8"),
                    SERVER_ADDR
                )
            except Exception:
                pass

            last_network_time = now

        # ------------------------------
        # Recebimento de respostas do servidor
        # ------------------------------
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

        # ------------------------------
        # Render
        # ------------------------------
        screen.fill((30, 30, 40))

        # projéteis
        for projectile in world_projectiles:
            px = int(safe_float(projectile.get("x"), 0.0))
            py = int(safe_float(projectile.get("y"), 0.0))
            radius = int(safe_float(projectile.get("radius"), 6.0))
            pygame.draw.circle(screen, (255, 220, 80), (px, py), radius)

        # jogadores
        for player in world_players:
            name = str(player.get("name", ""))
            x = int(safe_float(player.get("x"), 0.0))
            y = int(safe_float(player.get("y"), 0.0))

            color = (80, 200, 255)
            if name == local_player["name"]:
                color = (80, 255, 120)

            pygame.draw.circle(screen, color, (x, y), 18)

            text_surface = font.render(name, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(x, y - 28))
            screen.blit(text_surface, text_rect)

        info = font.render("WASD move | Clique esquerdo atira", True, (220, 220, 220))
        screen.blit(info, (10, 10))

        pygame.display.flip()

    sock.close()
    pygame.quit()


if __name__ == "__main__":
    main()
