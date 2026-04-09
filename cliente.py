import json
import math
import os
import socket
import threading
import time
import pyray as pr

# ============================================================
# CONFIG
# ============================================================

SERVER_IP = "192.168.1.81"
SERVER_PORT = 5550
SERVER_ADDR = (SERVER_IP, SERVER_PORT)

WINDOW_TITLE = "PvP UDP Client - pyray"

PLAYER_NAME = "player1"
PLAYER_IMAGE = "players/player.png"
MAP_IMAGE = "map.png"

MOVE_SPEED = 220.0
BULLET_SPEED = 520.0
SHOOT_COOLDOWN = 0.18
MAX_HP = 100
UPDATE_INTERVAL = 1.0 / 30.0
SOCKET_TIMEOUT = 0.25

USE_MOUSE_AIM = True
START_FULLSCREEN = True

FALLBACK_MAP_WIDTH = 2000
FALLBACK_MAP_HEIGHT = 2000

# ============================================================
# ESTADO GLOBAL
# ============================================================

running = True
world_lock = threading.Lock()
local_lock = threading.Lock()

remote_players = {}
remote_projectiles = []

local_player = {
    "name": PLAYER_NAME,
    "image": PLAYER_IMAGE,
    "x": 400.0,
    "y": 300.0,
    "hp": MAX_HP,
    "dir_x": 1.0,
    "dir_y": 0.0,
    "w": 32,
    "h": 32,
}

texture_cache = {}
last_shot_time = 0.0
sock = None

map_texture = None
map_width = FALLBACK_MAP_WIDTH
map_height = FALLBACK_MAP_HEIGHT

camera = None
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

# ============================================================
# UDP / THREAD DE RECEBIMENTO
# ============================================================

def send_json(data: dict):
    global sock
    if sock is None:
        return

    try:
        payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
        sock.sendto(payload, SERVER_ADDR)
    except OSError as e:
        print("Erro de socket ao enviar:", e)
    except Exception as e:
        print("Erro ao enviar JSON:", e)

def receiver_loop():
    global running, remote_players, remote_projectiles

    while running:
        try:
            data, _addr = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError:
            break
        except Exception as e:
            print("Erro no recv:", e)
            continue

        try:
            msg = json.loads(data.decode("utf-8"))
        except Exception:
            continue

        if not isinstance(msg, dict):
            continue

        if msg.get("type") == "world":
            players_list = msg.get("players", [])
            projectiles_list = msg.get("projectiles", [])

            new_players = {}
            if isinstance(players_list, list):
                for p in players_list:
                    if not isinstance(p, dict):
                        continue

                    name = str(p.get("name", "unknown"))[:24]
                    new_players[name] = {
                        "name": name,
                        "image": str(p.get("image", "players/player.png")),
                        "x": float(p.get("x", 0.0)),
                        "y": float(p.get("y", 0.0)),
                        "hp": int(p.get("hp", MAX_HP)),
                        "w": int(p.get("w", 32)),
                        "h": int(p.get("h", 32)),
                    }

            new_projectiles = []
            if isinstance(projectiles_list, list):
                for b in projectiles_list:
                    if not isinstance(b, dict):
                        continue

                    new_projectiles.append({
                        "owner": str(b.get("owner", "")),
                        "x": float(b.get("x", 0.0)),
                        "y": float(b.get("y", 0.0)),
                        "radius": float(b.get("radius", 5.0)),
                    })

            with world_lock:
                remote_players = new_players
                remote_projectiles = new_projectiles

            if PLAYER_NAME in new_players:
                server_me = new_players[PLAYER_NAME]
                with local_lock:
                    local_player["hp"] = int(server_me.get("hp", local_player["hp"]))
                    local_player["x"] = float(server_me.get("x", local_player["x"]))
                    local_player["y"] = float(server_me.get("y", local_player["y"]))

# ============================================================
# RECURSOS
# ============================================================

def get_texture(path: str):
    if path in texture_cache:
        return texture_cache[path]

    if os.path.exists(path):
        try:
            tex = pr.load_texture(path)
            texture_cache[path] = tex
            return tex
        except Exception as e:
            print(f"Erro ao carregar textura {path}: {e}")

    texture_cache[path] = None
    return None

def unload_all_textures():
    for tex in texture_cache.values():
        if tex is not None:
            try:
                pr.unload_texture(tex)
            except Exception:
                pass
    texture_cache.clear()

# ============================================================
# UTIL
# ============================================================

def normalize(x, y):
    length = math.hypot(x, y)
    if length <= 0.00001:
        return 0.0, 0.0
    return x / length, y / length

def clamp(v, min_v, max_v):
    return max(min_v, min(v, max_v))

# ============================================================
# CAMERA
# ============================================================

def init_camera():
    global camera
    camera = pr.Camera2D()
    with local_lock:
        px = local_player["x"]
        py = local_player["y"]
    camera.target = pr.Vector2(px, py)
    camera.offset = pr.Vector2(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
    camera.rotation = 0.0
    camera.zoom = 1.0

def update_camera():
    with local_lock:
        px = local_player["x"]
        py = local_player["y"]

    half_w = SCREEN_WIDTH / 2 / camera.zoom
    half_h = SCREEN_HEIGHT / 2 / camera.zoom

    min_x = half_w
    max_x = max(half_w, map_width - half_w)

    min_y = half_h
    max_y = max(half_h, map_height - half_h)

    target_x = clamp(px, min_x, max_x)
    target_y = clamp(py, min_y, max_y)

    camera.target = pr.Vector2(target_x, target_y)
    camera.offset = pr.Vector2(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)

# ============================================================
# LOGICA
# ============================================================

def handle_input(dt):
    global last_shot_time

    move_x = 0.0
    move_y = 0.0

    if pr.is_key_down(pr.KEY_W):
        move_y -= 1.0
    if pr.is_key_down(pr.KEY_S):
        move_y += 1.0
    if pr.is_key_down(pr.KEY_A):
        move_x -= 1.0
    if pr.is_key_down(pr.KEY_D):
        move_x += 1.0

    move_x, move_y = normalize(move_x, move_y)

    with local_lock:
        local_player["x"] += move_x * MOVE_SPEED * dt
        local_player["y"] += move_y * MOVE_SPEED * dt

        local_player["x"] = clamp(local_player["x"], 0, map_width)
        local_player["y"] = clamp(local_player["y"], 0, map_height)

        if move_x != 0.0 or move_y != 0.0:
            local_player["dir_x"] = move_x
            local_player["dir_y"] = move_y

    shoot_dx, shoot_dy = 0.0, 0.0

    if USE_MOUSE_AIM:
        mouse_screen = pr.get_mouse_position()
        mouse_world = pr.get_screen_to_world_2d(mouse_screen, camera)

        with local_lock:
            px = local_player["x"]
            py = local_player["y"]

        shoot_dx = mouse_world.x - px
        shoot_dy = mouse_world.y - py
        shoot_dx, shoot_dy = normalize(shoot_dx, shoot_dy)

        with local_lock:
            if shoot_dx != 0.0 or shoot_dy != 0.0:
                local_player["dir_x"] = shoot_dx
                local_player["dir_y"] = shoot_dy

        want_shoot = pr.is_mouse_button_down(pr.MOUSE_BUTTON_LEFT)
    else:
        if pr.is_key_down(pr.KEY_UP):
            shoot_dy -= 1.0
        if pr.is_key_down(pr.KEY_DOWN):
            shoot_dy += 1.0
        if pr.is_key_down(pr.KEY_LEFT):
            shoot_dx -= 1.0
        if pr.is_key_down(pr.KEY_RIGHT):
            shoot_dx += 1.0

        shoot_dx, shoot_dy = normalize(shoot_dx, shoot_dy)
        want_shoot = (shoot_dx != 0.0 or shoot_dy != 0.0)

        with local_lock:
            if want_shoot:
                local_player["dir_x"] = shoot_dx
                local_player["dir_y"] = shoot_dy

    now = time.time()
    if want_shoot and (now - last_shot_time) >= SHOOT_COOLDOWN:
        with local_lock:
            dir_x = local_player["dir_x"]
            dir_y = local_player["dir_y"]
            px = local_player["x"]
            py = local_player["y"]
            pname = local_player["name"]
            pimage = local_player["image"]

        if dir_x == 0.0 and dir_y == 0.0:
            dir_x, dir_y = 1.0, 0.0

        send_json({
            "type": "shoot",
            "name": pname,
            "image": pimage,
            "x": px,
            "y": py,
            "vx": dir_x * BULLET_SPEED,
            "vy": dir_y * BULLET_SPEED,
            "radius": 5,
            "damage": 10,
        })

        last_shot_time = now

def send_update():
    with local_lock:
        payload = {
            "type": "update",
            "name": local_player["name"],
            "image": local_player["image"],
            "x": local_player["x"],
            "y": local_player["y"],
            "hp": local_player["hp"],
        }
    send_json(payload)

# ============================================================
# RENDER
# ============================================================

def draw_texture_centered(tex, x, y):
    if tex is None:
        pr.draw_rectangle(int(x - 16), int(y - 16), 32, 32, pr.BLUE)
        return

    pr.draw_texture(tex, int(x - tex.width / 2), int(y - tex.height / 2), pr.WHITE)

def draw_hp_bar(x, y, hp, width=48, height=6):
    hp = max(0, min(MAX_HP, hp))
    filled = int((hp / MAX_HP) * width)

    pr.draw_rectangle(int(x - width // 2), int(y), width, height, pr.DARKGRAY)
    pr.draw_rectangle(int(x - width // 2), int(y), filled, height, pr.RED)
    pr.draw_rectangle_lines(int(x - width // 2), int(y), width, height, pr.BLACK)

def draw_player(player, is_local=False):
    tex = get_texture(player.get("image", PLAYER_IMAGE))

    x = float(player.get("x", 0))
    y = float(player.get("y", 0))
    hp = int(player.get("hp", MAX_HP))
    name = str(player.get("name", "unknown"))

    draw_texture_centered(tex, x, y)
    draw_hp_bar(x, y - 34, hp)

    color = pr.YELLOW if is_local else pr.WHITE
    font_size = 18
    text_w = pr.measure_text(name, font_size)
    pr.draw_text(name, int(x - text_w / 2), int(y - 56), font_size, color)

def draw_projectile(projectile):
    x = float(projectile.get("x", 0))
    y = float(projectile.get("y", 0))
    r = float(projectile.get("radius", 5))
    owner = str(projectile.get("owner", ""))

    color = pr.ORANGE if owner == PLAYER_NAME else pr.MAROON
    pr.draw_circle(int(x), int(y), r, color)

def draw_fallback_map():
    tile = 64
    for y in range(0, int(map_height), tile):
        for x in range(0, int(map_width), tile):
            color = pr.DARKGREEN if ((x // tile) + (y // tile)) % 2 == 0 else pr.GREEN
            pr.draw_rectangle(x, y, tile, tile, color)

# ============================================================
# MAIN
# ============================================================

def main():
    global sock, running, map_texture, map_width, map_height, SCREEN_WIDTH, SCREEN_HEIGHT

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(SOCKET_TIMEOUT)

    pr.init_window(SCREEN_WIDTH, SCREEN_HEIGHT, WINDOW_TITLE)

    if START_FULLSCREEN:
        monitor_w = pr.get_monitor_width(pr.get_current_monitor())
        monitor_h = pr.get_monitor_height(pr.get_current_monitor())
        SCREEN_WIDTH = monitor_w
        SCREEN_HEIGHT = monitor_h
        pr.toggle_fullscreen()
    else:
        SCREEN_WIDTH = pr.get_screen_width()
        SCREEN_HEIGHT = pr.get_screen_height()

    pr.set_target_fps(60)

    map_texture = get_texture(MAP_IMAGE)
    if map_texture is not None:
        map_width = map_texture.width
        map_height = map_texture.height

    init_camera()

    recv_thread = threading.Thread(target=receiver_loop, daemon=True)
    recv_thread.start()

    send_update()
    last_update_sent = 0.0

    while not pr.window_should_close():
        if pr.is_key_pressed(pr.KEY_F11):
            pr.toggle_fullscreen()
            SCREEN_WIDTH = pr.get_screen_width()
            SCREEN_HEIGHT = pr.get_screen_height()

        dt = pr.get_frame_time()

        handle_input(dt)
        update_camera()

        now = time.time()
        if (now - last_update_sent) >= UPDATE_INTERVAL:
            send_update()
            last_update_sent = now

        with world_lock:
            players_snapshot = dict(remote_players)
            projectiles_snapshot = list(remote_projectiles)

        with local_lock:
            local_snapshot = dict(local_player)

        pr.begin_drawing()
        pr.clear_background(pr.BLACK)

        pr.begin_mode_2d(camera)

        if map_texture is not None:
            pr.draw_texture(map_texture, 0, 0, pr.WHITE)
        else:
            draw_fallback_map()

        for name, player in players_snapshot.items():
            if name == PLAYER_NAME:
                continue
            draw_player(player, is_local=False)

        for projectile in projectiles_snapshot:
            draw_projectile(projectile)

        draw_player(local_snapshot, is_local=True)

        if USE_MOUSE_AIM:
            mouse_screen = pr.get_mouse_position()
            mouse_world = pr.get_screen_to_world_2d(mouse_screen, camera)
            pr.draw_circle_lines(int(mouse_world.x), int(mouse_world.y), 8, pr.YELLOW)

        pr.end_mode_2d()

        hud = f"HP: {local_snapshot['hp']}   X: {int(local_snapshot['x'])}   Y: {int(local_snapshot['y'])}"
        pr.draw_rectangle(10, 10, 320, 36, pr.fade(pr.BLACK, 0.5))
        pr.draw_text(hud, 20, 20, 20, pr.RAYWHITE)

        controls = "Mover: W A S D | Atirar: Mouse Esq | F11 Fullscreen"
        if not USE_MOUSE_AIM:
            controls = "Mover: W A S D | Atirar: Setas | F11 Fullscreen"

        pr.draw_rectangle(10, SCREEN_HEIGHT - 36, 430, 26, pr.fade(pr.BLACK, 0.45))
        pr.draw_text(controls, 20, SCREEN_HEIGHT - 30, 18, pr.RAYWHITE)

        pr.end_drawing()

    running = False

    try:
        sock.close()
    except Exception:
        pass

    unload_all_textures()
    pr.close_window()

if __name__ == "__main__":
    main()
