import json
import socket
import struct
import tomllib
import urllib.request
import urllib.parse
import qbittorrentapi
from config import (
    JF_URL, QB_HOST,
    JACKETT_URL,
    SEARCH_RESULTS_LIMIT,
    WATCHTOWER_TOKEN, WATCHTOWER_URL,
    REPO_SLUG,
)
from store import get_config, get_creds, set_config


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

_qb_client: qbittorrentapi.Client | None = None


def qb() -> qbittorrentapi.Client:
    global _qb_client
    if _qb_client is None:
        _qb_client = _qb_login()
    return _qb_client


def _qb_login() -> qbittorrentapi.Client:
    user, password = get_creds()
    client = qbittorrentapi.Client(host=QB_HOST, username=user, password=password)
    client.auth_log_in()
    return client


def invalidate_qb():
    """Call after credential changes or auth failures to force re-login on next use."""
    global _qb_client
    _qb_client = None


def qb_temp_password() -> str | None:
    """Read current session temp password from qBittorrent container logs via Docker socket."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect("/var/run/docker.sock")
        req = b"GET /containers/media-server-qbittorrent/logs?stdout=1&stderr=1&tail=100 HTTP/1.0\r\nHost: localhost\r\n\r\n"
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


def qb_restart() -> bool:
    """Send POST /containers/media-server-qbittorrent/restart to Docker socket. Returns True on success."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect("/var/run/docker.sock")
        s.sendall(b"POST /containers/media-server-qbittorrent/restart HTTP/1.0\r\nHost: localhost\r\nContent-Length: 0\r\n\r\n")
        resp = b""
        while chunk := s.recv(4096):
            resp += chunk
        s.close()
        status_line = resp.split(b"\r\n", 1)[0]
        code = int(status_line.split()[1])
        return code in (204, 200)
    except Exception:
        return False


def qb_set_password(new_pass: str) -> bool | str:
    """Returns True on success, error string on failure."""
    try:
        client = qb()
    except Exception:
        temp = qb_temp_password()
        if not temp:
            return "auth error: cannot connect and no temp password in logs"
        set_config("qb_pass", temp)
        invalidate_qb()
        try:
            client = qb()
        except Exception as e:
            return f"auth error after temp fetch: {e}"
    try:
        resp = client._http_session.post(
            f"{QB_HOST}/api/v2/app/setPreferences",
            data={"json": json.dumps({"web_ui_password": new_pass})},
            timeout=5,
        )
        return True if resp.ok else f"HTTP {resp.status_code}: {resp.text[:120]}"
    except Exception as e:
        return f"setPreferences error: {e}"


# --- Jackett ---

def jackett_search(query: str) -> list[dict] | None:
    """Search via Jackett aggregate endpoint.

    Returns sorted list of dicts or None on connection error.
    Returns [] if API key not configured or no results found.
    Each item: title, seeders, size (bytes), magnet (str|None), link (str|None).
    """
    key = get_config("jackett_api_key")
    if not key:
        return []
    params = urllib.parse.urlencode({"apikey": key, "Query": query})
    url = f"{JACKETT_URL}/api/v2.0/indexers/all/results?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read())
    except Exception:
        return None
    results = data.get("Results") or []
    results.sort(key=lambda r: r.get("Seeders") or 0, reverse=True)
    out = []
    for r in results[:SEARCH_RESULTS_LIMIT]:
        out.append({
            "title":   r.get("Title") or "",
            "seeders": r.get("Seeders") or 0,
            "size":    r.get("Size") or 0,
            "magnet":  r.get("MagnetUri") or None,
            "link":    r.get("Link") or None,
        })
    return out


def jackett_download_torrent(link: str) -> bytes | None:
    """Download .torrent bytes from a Jackett proxy link. Returns None on error."""
    req = urllib.request.Request(link, headers={"Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()
    except Exception:
        return None


# --- Updates ---

def remote_version():
    try:
        url = f"https://raw.githubusercontent.com/{REPO_SLUG}/main/pyproject.toml"
        req = urllib.request.Request(url, headers={"User-Agent": "MediaServerBot/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return tomllib.loads(r.read().decode())["project"]["version"]
    except Exception:
        return None


def trigger_update() -> bool:
    """Returns True if Watchtower received the request, False if unreachable."""
    req = urllib.request.Request(
        f"{WATCHTOWER_URL}/v1/update",
        method="POST",
        headers={"Authorization": f"Bearer {WATCHTOWER_TOKEN}"},
    )
    try:
        urllib.request.urlopen(req, timeout=90)
        return True
    except urllib.error.HTTPError:
        return True  # got a response — Watchtower received and processed the request
    except urllib.error.URLError:
        return False  # connection refused — Watchtower not reachable
    except Exception:
        return True  # timeout means Watchtower is processing (pulling image)
