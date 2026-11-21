import argparse
import csv
import hashlib
import json
import mmap
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from solver import solve


APP_ID = "2835570"
PORT = 47891
TARGET_SCRIPT = "res://scripts/RoundManager.gd"
DEFAULT_GAME_EXE = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Buckshot Roulette\Buckshot Roulette_windows\Buckshot Roulette.exe"
)


def _u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data, offset):
    return struct.unpack_from("<Q", data, offset)[0]


def _find_pack(data):
    pe_offset = _u32(data, 0x3C)
    section_count = _u16(data, pe_offset + 6)
    optional_size = _u16(data, pe_offset + 20)
    sections = pe_offset + 24 + optional_size
    for index in range(section_count):
        section = sections + index * 40
        name = data[section:section + 8].split(b"\0", 1)[0]
        if name == b"pck":
            raw_size = _u32(data, section + 16)
            raw_offset = _u32(data, section + 20)
            return raw_offset, raw_size
    raise RuntimeError("在游戏 EXE 中找不到 Godot PCK 区段。")


def _find_script_entry(data, pack_start):
    if data[pack_start:pack_start + 4] != b"GDPC":
        raise RuntimeError("PCK 标识不匹配，游戏版本可能已更新。")
    file_base = _u64(data, pack_start + 24)
    file_count = _u32(data, pack_start + 96)
    cursor = pack_start + 100
    for _ in range(file_count):
        path_size = _u32(data, cursor)
        cursor += 4
        path = data[cursor:cursor + path_size].rstrip(b"\0").decode("utf-8")
        cursor += path_size
        fields = cursor
        file_offset = _u64(data, fields)
        file_size = _u64(data, fields + 8)
        cursor += 36
        if path == TARGET_SCRIPT:
            return file_base, fields, file_offset, file_size
    raise RuntimeError(f"PCK 内找不到 {TARGET_SCRIPT}，游戏版本可能已更新。")


def _patched_script(original, bridge):
    ready_marker = "func _ready():\n\tEngine.time_scale = 1\n\tHideDealer()"
    process_marker = "func _process(delta):\n\tLerpScore()\n\tInitialTimer()"
    if "_assistant_start_server" in original or ready_marker not in original or process_marker not in original:
        raise RuntimeError("RoundManager.gd 与已知版本不匹配，未生成派生包。")
    patched = original.replace(ready_marker, ready_marker + "\n\t_assistant_start_server()", 1)
    patched = patched.replace(process_marker, process_marker + "\n\t_assistant_poll()", 1)
    return patched.rstrip() + "\n\n" + bridge.strip() + "\n"


def _verify_pack(path, expected_script):
    with path.open("rb") as pack:
        if pack.read(4) != b"GDPC":
            return False
        pack.seek(24)
        file_base = struct.unpack("<Q", pack.read(8))[0]
        pack.seek(96)
        file_count = struct.unpack("<I", pack.read(4))[0]
        cursor = 100
        for _ in range(file_count):
            pack.seek(cursor)
            path_size = struct.unpack("<I", pack.read(4))[0]
            cursor += 4
            resource_path = pack.read(path_size).rstrip(b"\0").decode("utf-8")
            cursor += path_size
            fields = cursor
            file_offset, file_size = struct.unpack("<QQ", pack.read(16))
            digest = pack.read(16)
            pack.read(4)
            cursor += 36
            if resource_path == TARGET_SCRIPT:
                if file_size != len(expected_script):
                    return False
                pack.seek(file_base + file_offset)
                content = pack.read(file_size)
                return content == expected_script and hashlib.md5(content).digest() == digest
    return False


def build_patch_pack(game_exe):
    game_exe = game_exe.resolve()
    bridge_path = Path(__file__).with_name("game_bridge.gd")
    bridge = bridge_path.read_text(encoding="utf-8")
    bridge_hash = hashlib.sha256(bridge.encode("utf-8")).hexdigest()
    stat = game_exe.stat()
    cache_dir = Path(tempfile.gettempdir()) / "BuckshotRouletteAssistant"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = f"{stat.st_size:x}-{stat.st_mtime_ns:x}-{bridge_hash[:16]}"
    output = cache_dir / f"main-{cache_key}.pck"
    if output.exists() and _verify_pack(output, _expected_script(game_exe, bridge).encode("utf-8")):
        return output

    with game_exe.open("rb") as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
        pack_start, pack_size = _find_pack(data)
        file_base, entry_fields, file_offset, file_size = _find_script_entry(data, pack_start)
        script_start = file_base + file_offset
        if script_start < pack_start or script_start + file_size > pack_start + pack_size:
            raise RuntimeError("RoundManager.gd 位于 PCK 区段之外。")
        original = data[script_start:script_start + file_size].decode("utf-8")
        patched_script = _patched_script(original, bridge)
        adjusted_base = file_base - pack_start
        if adjusted_base < 0:
            raise RuntimeError("PCK file_base 不符合预期。")
        entry_in_pack = entry_fields - pack_start
        new_data_start = pack_size - 4
        new_file_offset = new_data_start - adjusted_base
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(prefix="main-", suffix=".tmp", dir=cache_dir, delete=False) as packed:
                temporary = Path(packed.name)
                source.seek(pack_start)
                remaining = pack_size
                while remaining:
                    block = source.read(min(16 * 1024 * 1024, remaining))
                    if not block:
                        raise RuntimeError("读取游戏 PCK 时遇到意外 EOF。")
                    packed.write(block)
                    remaining -= len(block)
                packed.seek(new_data_start)
                packed.write(patched_script.encode("utf-8"))
                packed.write(b"GDPC")
                packed.flush()
                os.fsync(packed.fileno())

            with temporary.open("r+b") as packed:
                packed.seek(24)
                packed.write(struct.pack("<Q", adjusted_base))
                packed.seek(entry_in_pack)
                packed.write(struct.pack("<QQ", new_file_offset, len(patched_script.encode("utf-8"))))
                packed.write(hashlib.md5(patched_script.encode("utf-8")).digest())
                packed.flush()
                os.fsync(packed.fileno())

            if not _verify_pack(temporary, patched_script.encode("utf-8")):
                raise RuntimeError("派生 PCK 校验失败。")
            temporary.replace(output)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
    return output


def _expected_script(game_exe, bridge):
    with game_exe.open("rb") as source, mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
        pack_start, _ = _find_pack(data)
        file_base, _, file_offset, file_size = _find_script_entry(data, pack_start)
        start = file_base + file_offset
        original = data[start:start + file_size].decode("utf-8")
    return _patched_script(original, bridge)


def _game_running():
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Buckshot Roulette.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    for row in csv.reader(result.stdout.splitlines()):
        if row and row[0].strip().lower() == "buckshot roulette.exe":
            return True
    return False


def _launch_game(game_exe, patch_pack):
    steam_exe = game_exe.parents[4] / "steam.exe"
    if steam_exe.exists():
        command = [str(steam_exe), "-applaunch", APP_ID, "--main-pack", str(patch_pack)]
    else:
        command = [str(game_exe), "--main-pack", str(patch_pack)]
    subprocess.Popen(command, cwd=str(game_exe.parent))


def _read_state(timeout=0.8):
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=timeout) as connection:
            connection.settimeout(timeout)
            connection.sendall(b"STATE\n")
            chunks = []
            size = 0
            while size < 1024 * 1024:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
            if not chunks:
                return None
            return json.loads(b"".join(chunks).decode("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _shell_name(shell):
    return "實彈" if shell == "live" else "空彈"


def _overlay_action_name(action):
    item_names = {
        "adrenaline": "肾上腺素",
        "beer": "啤酒",
        "cigarettes": "香烟",
        "expired medicine": "过期药",
        "handcuffs": "手铐",
        "handsaw": "手锯",
        "inverter": "反转器",
        "magnifying glass": "放大镜",
    }
    if action["type"] == "shoot":
        return "射向自己" if action["target"] == "self" else "射向庄家"
    if action["type"] == "steal_and_use":
        item = item_names.get(action["stolen_item"], action["stolen_item"])
        return f"偷取并使用「{item}」"
    item = item_names.get(action["item"], action["item"])
    return f"使用道具「{item}」"


def _send_advice(action, detail):
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5) as connection:
            connection.settimeout(0.5)
            connection.sendall(f"ADVICE\t{action}\n{detail}\n".encode("utf-8"))
            connection.recv(16)
    except OSError:
        pass


def _action_name(action):
    if action["type"] == "shoot":
        return "向自己開槍" if action["target"] == "self" else "向莊家開槍"
    if action["type"] == "steal_and_use":
        return f"用腎上腺素偷取並使用「{action['stolen_item']}」"
    return f"使用道具「{action['item']}」"


def _show_state(state):
    print("\n" + "=" * 56)
    print(f"批次 {state.get('batch_index', '?')} / 回合 {state.get('round_index', '?') + 1 if isinstance(state.get('round_index'), int) else '?'}")
    print(f"玩家 {state.get('player_hp', '?')}/{state.get('max_hp', '?')}  |  莊家 {state.get('dealer_hp', '?')}/{state.get('max_hp', '?')}")
    known_shell = state.get("current_shell", "") if state.get("current_shell_known") else ""
    current_shell_text = _shell_name(known_shell) if known_shell else "未知"
    print(
        f"剩餘彈：實彈 {state.get('live_shells_remaining', '?')} / "
        f"空彈 {state.get('blank_shells_remaining', '?')} | 當前彈：{current_shell_text}"
    )
    print("玩家道具：" + (", ".join(f"{name} x{count}" for name, count in state.get("player_items", {}).items()) or "無"))

    if not state.get("player_can_act"):
        print(f"遊戲狀態：{state.get('phase', 'busy')}，等待可操作時機。")
        detail = f"實彈 {state.get('live_shells_remaining', '?')} / 空彈 {state.get('blank_shells_remaining', '?')}"
        _send_advice("等待你的回合", detail)
        print("=" * 56)
        return

    _send_advice("正在计算下一步", "正在按当前弹药概率分析局面")
    try:
        result = solve(state)
    except ValueError as error:
        print(f"暫無建議：{error}")
        _send_advice("暂时没有建议", str(error))
        print("=" * 56)
        return
    if result["status"] != "ready":
        print(result.get("message", "等待遊戲狀態"))
        _send_advice("等待游戏更新", result.get("message", "等待游戏状态"))
        print("=" * 56)
        return

    action_name = _action_name(result["best_action"])
    print(f"建議：{action_name}")
    print(f"本彈膛估計勝率：{result['player_win_share']:.1%}")
    for candidate in result["candidates"][1:5]:
        print(f"  其他選擇：{_action_name(candidate['action'])} ({candidate['player_win_share']:.1%})")
    if result["unmodeled_items"]:
        print("未納入求解的道具：" + ", ".join(result["unmodeled_items"]))
    live_shells = state.get("live_shells_remaining", "?")
    blank_shells = state.get("blank_shells_remaining", "?")
    detail = f"本弹膛估计胜率 {result['player_win_share']:.1%}  ·  实弹 {live_shells} / 空弹 {blank_shells}"
    if result["unmodeled_items"]:
        detail += "\n未建模道具：" + ", ".join(result["unmodeled_items"])
    _send_advice(_overlay_action_name(result["best_action"]), detail)
    print("=" * 56)


def main():
    parser = argparse.ArgumentParser(description="Buckshot Roulette internal-state assistant")
    parser.add_argument("--game-exe", type=Path, default=DEFAULT_GAME_EXE)
    parser.add_argument("--no-launch", action="store_true", help="only connect to an already instrumented game")
    parser.add_argument("--once", action="store_true", help="read and print one state snapshot")
    parser.add_argument("--interval", type=float, default=0.35)
    args = parser.parse_args()

    if os.name != "nt":
        parser.error("This tool requires Windows.")
    game_exe = args.game_exe.expanduser().resolve()
    if not game_exe.is_file():
        print(f"找不到游戏 EXE：{game_exe}", file=sys.stderr)
        return 2

    state = _read_state()
    if state is None:
        if _game_running():
            print("检测到未插桩的游戏进程。请正常退出当前游戏，再启动 run.bat；工具不会关闭或修改正在运行的进程。", file=sys.stderr)
            return 2
        if args.no_launch:
            print("没有检测到已插桩的游戏。", file=sys.stderr)
            return 2
        print("正在生成临时派生资源包；Steam 原始文件保持不变。")
        try:
            patch_pack = build_patch_pack(game_exe)
        except (OSError, RuntimeError, UnicodeError) as error:
            print(f"准备游戏状态桥接失败：{error}", file=sys.stderr)
            return 2
        print("通过 Steam 启动带内部状态读取桥接的游戏实例。")
        _launch_game(game_exe, patch_pack)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            state = _read_state()
            if state is not None:
                break
            time.sleep(0.5)
        if state is None:
            print("尚未收到游戏状态。确认游戏启动后重试；游戏窗口保持原样。", file=sys.stderr)
            return 2

    if args.once:
        _show_state(state)
        return 0

    last_state = None
    print("已连接游戏内部状态；按 Ctrl+C 停止建议面板。")
    try:
        while True:
            state = _read_state()
            if state is None:
                print("游戏状态连接暂时中断，正在重试。")
                time.sleep(1)
                continue
            fingerprint = json.dumps(state, sort_keys=True, ensure_ascii=False)
            if fingerprint != last_state:
                _show_state(state)
                last_state = fingerprint
            time.sleep(max(0.1, args.interval))
    except KeyboardInterrupt:
        print("已停止建议面板；游戏继续运行。")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
