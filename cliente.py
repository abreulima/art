import pyray as pr
import socket
import threading
import json
import time
import os

# --- Configurações ---
SERVER_IP = "192.168.1.81"
SERVER_PORT = 5550
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# --- Jogador local ---
player = {
    "type": "update",
    "name": "tavares",
    "image": "players/tavares.png",
    "x": 400,
    "y": 300
}

# --- Estado do mundo ---
world = {"players": []}

# --- Texturas ---
map_texture = None
player_texture_cache = {}

# --- Socket UDP ---
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(0.01)

def load_textures():
    global map_texture, player_texture_cache
    if not os.path.exists("map.png"):
        raise FileNotFoundError("map.png não encontrado na pasta do projeto")
    map_texture = pr.load_texture("map.png")
    if os.path.exists(player["image"]):
        player_texture_cache[player["image"]] = pr.load_texture(player["image"])
    else:
        print(f"Atenção: {player['image']} não encontrado")

def udp_receive_thread():
    global world
    while True:
        try:
            data, _ = sock.recvfrom(4096)
            message = json.loads(data.decode())
            if message.get("type") == "world":
                world = message
                # Debug: mostrar jogadores recebidos
                print("Players recebidos:", [p["name"] for p in world.get("players", [])])
                # Pré-carregar texturas dos outros jogadores
                for p in world.get("players", []):
                    img = p.get("image")
                    if img not in player_texture_cache and os.path.exists(img):
                        player_texture_cache[img] = pr.load_texture(img)
        except socket.timeout:
            continue
        except Exception as e:
            print("Erro na thread UDP:", e)

def send_player_update():
    try:
        sock.sendto(json.dumps(player).encode(), (SERVER_IP, SERVER_PORT))
    except Exception as e:
        print("Erro ao enviar:", e)

# --- Inicializar janela ---
pr.init_window(SCREEN_WIDTH, SCREEN_HEIGHT, "Cliente UDP Pyray")
load_textures()
pr.set_target_fps(60)

# --- Iniciar thread UDP ---
threading.Thread(target=udp_receive_thread, daemon=True).start()

# --- Câmera ---
cam_x = player["x"] - SCREEN_WIDTH // 2
cam_y = player["y"] - SCREEN_HEIGHT // 2

# --- Loop principal ---
while not pr.window_should_close():
    dt = pr.get_frame_time()
    speed = 200 * dt

    # --- Input ---
    if pr.is_key_down(pr.KEY_W): player["y"] -= speed
    if pr.is_key_down(pr.KEY_S): player["y"] += speed
    if pr.is_key_down(pr.KEY_A): player["x"] -= speed
    if pr.is_key_down(pr.KEY_D): player["x"] += speed

    # --- Atualizar câmera suavemente ---
    cam_x += (player["x"] - SCREEN_WIDTH/2 - cam_x) * 0.1
    cam_y += (player["y"] - SCREEN_HEIGHT/2 - cam_y) * 0.1

    # --- Enviar atualização ---
    send_player_update()

    # --- Render ---
    pr.begin_drawing()
    pr.clear_background(pr.RAYWHITE)

    # Desenhar mapa
    pr.draw_texture(map_texture, int(-cam_x), int(-cam_y), pr.WHITE)

    # Desenhar todos os jogadores recebidos
    for p in world.get("players", []):
        tex = player_texture_cache.get(p.get("image"))
        draw_x = int(p.get("x",0) - cam_x)
        draw_y = int(p.get("y",0) - cam_y)
        if tex:
            pr.draw_texture(tex, draw_x, draw_y, pr.WHITE)
        else:
            # Se textura não existe, desenha um quadrado vermelho
            pr.draw_rectangle(draw_x, draw_y, 32, 32, pr.RED)

    # Desenhar jogador local por cima
    local_tex = player_texture_cache.get(player["image"])
    draw_x = int(player["x"] - cam_x)
    draw_y = int(player["y"] - cam_y)
    if local_tex:
        pr.draw_texture(local_tex, draw_x, draw_y, pr.WHITE)
    else:
        pr.draw_rectangle(draw_x, draw_y, 32, 32, pr.BLUE)

    pr.end_drawing()

pr.close_window()
