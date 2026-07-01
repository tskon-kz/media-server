import http.cookiejar
import json
import socket
import struct
import tomllib
import urllib.request
import urllib.parse
import qbittorrentapi
from config import (
    JF_URL, QB_HOST,
    WATCHTOWER_TOKEN, WATCHTOWER_URL,
    REPO_SLUG,
)
from store import get_config, get_creds


# --- Jellyfin ---

def jf(method, path, body=None):
    key = get_config("jellyfin_api_key")
    if not key:
        return None
    req = urllib.request.Request(
        f"{JF_URL}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-Emby-Token": key, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
            return json.loads(raw) if raw else True
    except Exception:
        return None


def jf_add_library(name, path, lib_type):
    params = urllib.parse.urlencode({"name": name, "collectionType": lib_type, "refreshLibrary": "true"})
    jf("POST", f"/Library/VirtualFolders?{params}", {"LibraryOptions": {"PathInfos": [{"Path": path}]}})


def jf_remove_library(name):
    params = urllib.parse.urlencode({"name": name, "refreshLibrary": "true"})
    jf("DELETE", f"/Library/VirtualFolders?{params}")


# --- qBittorrent ---

def qb():
    user, password = get_creds()
    client = qbittorrentapi.Client(host=QB_HOST, username=user, password=password)
    client.auth_log_in()
    return client


def qb_temp_password() -> str | None:
    """Read current session temp password from qBittorrent container logs via Docker socket."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect("/var/run/docker.sock")
        req = b"GET /containers/qbittorrent/logs?stdout=1&stderr=1&tail=100 HTTP/1.0\r\nHost: localhost\r\n\r\n"
        s.sendall(req)
        raw = b""
        while chunk := s.recv(4096):
            raw += chunk
        s.close()
        body = raw.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in raw else raw
        # Docker multiplexed log format: 8-byte header (1 byte stream, 3 zeros, 4-byte big-endian length)
        lines, i = [], 0
        while i + 8 <= len(body):
            size = struct.unpack(">I", body[i+4:i+8])[0]
            lines.append(body[i+8:i+8+size].decode(errors="ignore"))
            i += 8 + size
        for line in reversed("".join(lines).splitlines()):
            if "temporary password" in line:
                return line.split()[-1]
        return None
    except Exception:
        return None


def _qb_login_and_set(current_pass: str, new_pass: str) -> bool:
    """Login to qBittorrent with current_pass, then set new_pass via setPreferences."""
    user, _ = get_creds()
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        login_data = urllib.parse.urlencode({"username": user, "password": current_pass}).encode()
        with opener.open(f"{QB_HOST}/api/v2/auth/login", login_data, timeout=5) as r:
            if r.read().decode().strip() != "Ok.":
                return False
    except Exception:
        return False
    try:
        prefs_data = urllib.parse.urlencode({"json": json.dumps({"web_ui_password": new_pass})}).encode()
        opener.open(f"{QB_HOST}/api/v2/app/setPreferences", prefs_data, timeout=5).close()
        return True
    except Exception:
        return False


def qb_set_password(new_pass: str) -> bool:
    _, current_pass = get_creds()
    # Try to change using stored credentials.
    if _qb_login_and_set(current_pass, new_pass):
        return True
    # Stored credentials stale — check if new_pass already works (resync case).
    user, _ = get_creds()
    try:
        client = qbittorrentapi.Client(host=QB_HOST, username=user, password=new_pass)
        client.auth_log_in()
        return True
    except Exception:
        return False


# --- Updates ---

def remote_version():
    try:
        url = f"https://raw.githubusercontent.com/{REPO_SLUG}/main/pyproject.toml"
        req = urllib.request.Request(url, headers={"User-Agent": "MediaServerBot/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return tomllib.loads(r.read().decode())["project"]["version"]
    except Exception:
        return None


def trigger_update():
    req = urllib.request.Request(
        f"{WATCHTOWER_URL}/v1/update",
        method="POST",
        headers={"Authorization": f"Bearer {WATCHTOWER_TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=10):
        pass
