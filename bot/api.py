import json
import os
import re
import secrets
import socket
import struct
import urllib.request
import urllib.parse
import qbittorrentapi
from config import (
    JF_URL, QB_HOST,
    JACKETT_URL,
    SEARCH_RESULTS_LIMIT, SEARCH_CATEGORIES,
    REPO_SLUG, CLOUDFLARED_CONTAINER,
    DATA_DIR, UPDATER_IMAGE, UPDATER_CONTAINER,
    INCOMING_DIR,
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
    try:
        client.auth_log_in()
        return client
    except qbittorrentapi.LoginFailed:
        # Stored password no longer works — most likely it was a per-session temp
        # password and qBittorrent restarted (fresh install default). Recover once
        # by logging in with the current temp password from the container logs and
        # promoting it to a permanent one, so future restarts don't re-break login
        # (and don't get the IP banned by repeated failures).
        temp = qb_temp_password()
        if not temp or temp == password:
            raise
        client = qbittorrentapi.Client(host=QB_HOST, username=user, password=temp)
        client.auth_log_in()  # let this raise if the temp password is also wrong
        perm = secrets.token_urlsafe(12)
        try:
            client._http_session.post(
                f"{QB_HOST}/api/v2/app/setPreferences",
                data={"json": json.dumps({"web_ui_password": perm})},
                timeout=5,
            )
            set_config("qb_pass", perm)
        except Exception:
            # Couldn't persist a permanent password; keep using the temp one for now.
            set_config("qb_pass", temp)
        return client


def invalidate_qb():
    """Call after credential changes or auth failures to force re-login on next use."""
    global _qb_client
    _qb_client = None


def ensure_qb_save_path():
    """Point qBittorrent's default save path under /media if it isn't already.

    The hotio image defaults to `/app/qBittorrent/downloads`, which is on the
    container's ephemeral fs — not the mounted media disk. That makes qB report
    `free_space_on_disk = -1` (unknown) and would silently drop any download that
    used the default path. Downloads added via the bot always pass an explicit
    per-category path under /media, so this only corrects the default; run once at
    startup. Best-effort — never raise into the caller.
    """
    try:
        client = qb()
        current = client.app_preferences().get("save_path") or ""
        if not current.startswith("/media"):
            client.app_set_preferences({"save_path": INCOMING_DIR})
    except Exception:
        pass


def _dechunk(body: bytes) -> bytes:
    """Decode HTTP/1.1 chunked transfer-encoding into the raw payload.

    Modern Docker daemons answer the /logs endpoint with chunked encoding even
    for an HTTP/1.0 request; older ones send the body verbatim. If the body
    doesn't parse as chunked, return it unchanged.
    """
    out, i = b"", 0
    while i < len(body):
        nl = body.find(b"\r\n", i)
        if nl == -1:
            break
        try:
            size = int(body[i:nl].split(b";", 1)[0], 16)
        except ValueError:
            return body  # not chunked — treat as raw
        if size == 0:
            return out
        start = nl + 2
        out += body[start:start + size]
        i = start + size + 2  # skip data + trailing CRLF
    return out or body


def _docker_logs(container: str, tail: int = 100) -> str:
    """Fetch a container's recent logs via the Docker socket, demultiplexed.

    Returns the decoded log text (stdout+stderr interleaved), or "" on error.
    Tolerant of the daemon holding the connection open (streams don't always
    send Connection: close): a read timeout is expected, and whatever has been
    received by then is parsed rather than discarded.
    """
    raw = b""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect("/var/run/docker.sock")
        req = (
            f"GET /containers/{container}/logs?stdout=1&stderr=1&tail={tail} "
            "HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        ).encode()
        s.sendall(req)
        while chunk := s.recv(4096):
            raw += chunk
    except socket.timeout:
        pass  # keep whatever streamed in before the timeout
    except Exception:
        return ""
    finally:
        try:
            s.close()
        except Exception:
            pass

    if b"\r\n\r\n" not in raw:
        return ""
    headers, body = raw.split(b"\r\n\r\n", 1)
    if b"transfer-encoding: chunked" in headers.lower():
        body = _dechunk(body)
    # Docker multiplexed log format: 8-byte header (1 byte stream, 3 zeros, 4-byte big-endian length)
    parts, i = [], 0
    while i + 8 <= len(body):
        size = struct.unpack(">I", body[i+4:i+8])[0]
        if size == 0 or i + 8 + size > len(body):
            break
        parts.append(body[i+8:i+8+size].decode(errors="ignore"))
        i += 8 + size
    # Fall back to a raw decode if the stream wasn't multiplexed (TTY mode).
    return "".join(parts) if parts else body.decode(errors="ignore")


def qb_temp_password() -> str | None:
    """Read current session temp password from qBittorrent container logs via Docker socket."""
    for line in reversed(_docker_logs("media-server-qbittorrent").splitlines()):
        if "temporary password" in line:
            return line.split()[-1]
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

def jackett_get_api_key() -> str:
    try:
        with open(_JACKETT_CFG) as f:
            return json.load(f).get("APIKey", "")
    except Exception:
        return ""


def jackett_search(query: str) -> list[dict] | None:
    """Search via Jackett aggregate endpoint.

    Returns sorted list of dicts or None on connection error.
    Returns [] if API key not configured or no results found.
    Each item: title, seeders, size (bytes), tracker, date (ISO publish date),
    details (source page URL), magnet (str|None), link (str|None).
    """
    key = jackett_get_api_key()
    if not key:
        return []
    params = urllib.parse.urlencode(
        [("apikey", key), ("Query", query)]
        + [("Category[]", c) for c in SEARCH_CATEGORIES]
    )
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
            "tracker": r.get("Tracker") or "",
            "date":    r.get("PublishDate") or "",
            "details": r.get("Details") or r.get("Guid") or "",
            "magnet":  r.get("MagnetUri") or None,
            "link":    r.get("Link") or None,
        })
    return out


_JACKETT_CFG = "/jackett-config/Jackett/ServerConfig.json"


def jackett_has_password() -> bool:
    try:
        with open(_JACKETT_CFG) as f:
            return bool(json.load(f).get("AdminPassword"))
    except Exception:
        return False


def jackett_set_password(new_pass: str) -> bool | str:
    import hashlib
    try:
        with open(_JACKETT_CFG) as f:
            d = json.load(f)
        if new_pass:
            api_key = d.get("APIKey", "")
            d["AdminPassword"] = hashlib.sha512((new_pass + api_key).encode("utf-16-le")).hexdigest()
        else:
            d["AdminPassword"] = ""
        with open(_JACKETT_CFG, "w") as f:
            json.dump(d, f, indent=2)
    except Exception as e:
        return str(e)
    if not _jackett_restart():
        return "restart failed"
    return True


def _jackett_restart() -> bool:
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect("/var/run/docker.sock")
        s.sendall(b"POST /containers/media-server-jackett/restart HTTP/1.0\r\nHost: localhost\r\nContent-Length: 0\r\n\r\n")
        resp = b""
        while chunk := s.recv(4096):
            resp += chunk
        s.close()
        return int(resp.split(b"\r\n", 1)[0].split()[1]) in (204, 200)
    except Exception:
        return False


def jackett_download_torrent(link: str) -> bytes | None:
    """Download .torrent bytes from a Jackett proxy link. Returns None on error."""
    req = urllib.request.Request(link, headers={"Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()
    except Exception:
        return None


# --- Cloudflare Tunnel ---

_TRYCLOUDFLARE_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def get_cloudflared_url() -> str | None:
    """Scrape the assigned quick-tunnel URL from cloudflared's container logs.

    On start, `cloudflared tunnel --url ...` prints a banner containing the
    randomly-assigned `https://<random>.trycloudflare.com` address. The URL is
    ephemeral — it changes on every container restart — so callers must re-read
    it rather than caching it across restarts. Returns None until the banner
    appears (or if the container is unreachable).
    """
    m = _TRYCLOUDFLARE_RE.search(_docker_logs(CLOUDFLARED_CONTAINER, tail=200))
    return m.group(0) if m else None


# --- Updates ---

def gh_latest_release_tag() -> str | None:
    """Latest published GitHub Release tag (e.g. 'v1.5.0'), or None on error.

    Unauthenticated call against the public repo — the tag on the Release IS
    the version, replacing the old pyproject.toml-on-GitHub poll.
    """
    url = f"https://api.github.com/repos/{REPO_SLUG}/releases/latest"
    req = urllib.request.Request(url, headers={
        "User-Agent": "MediaServerBot/1.0",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read()).get("tag_name") or None
    except Exception:
        return None


def _project_dir_from_mounts(me) -> str | None:
    """Derive the host compose project directory for the updater's bind mount.

    Prefer the compose-set label `com.docker.compose.project.working_dir`, which
    records the true absolute host project dir. It is immune to bind-path
    corruption — unlike deriving it from our own `/app/data` mount, which a prior
    buggy updater run could have rewritten to `/project/bot-data` (making every
    later update mount the wrong dir and pick the wrong project name).

    Fall back to the `/app/data` bind heuristic only if the label is absent.
    """
    workdir = (me.labels or {}).get("com.docker.compose.project.working_dir")
    if workdir:
        return workdir
    for bind in (me.attrs.get("HostConfig", {}) or {}).get("Binds") or []:
        parts = bind.split(":")
        if len(parts) >= 2 and parts[1] == DATA_DIR:
            return os.path.dirname(parts[0])
    return None


def stack_update(tag: str):
    """Launch an ephemeral updater container that reconciles the whole compose
    stack (mirrors update.sh) and recreates the bot with `tag`.

    The updater runs OUTSIDE the compose project, so it survives `docker compose
    up -d` recreating this bot. Returns the updater container name on a
    successful launch, or an error string if the update could not even start (in
    which case the old bot keeps running untouched). Success/failure once the
    updater is running is reported by whichever bot process is alive afterwards —
    see handlers/_utils._do_stack_update and main._post_init. Runs via
    asyncio.to_thread. See docs/self-update.md.
    """
    try:
        import docker
    except Exception as e:
        return f"docker SDK unavailable: {e}"
    try:
        client = docker.from_env()
    except Exception as e:
        return f"cannot reach Docker socket: {e}"

    # Our own container ID is the hostname inside the container.
    try:
        me = client.containers.get(socket.gethostname())
    except Exception as e:
        return f"self-inspect failed: {e}"

    project_dir = _project_dir_from_mounts(me)
    if not project_dir:
        return "could not locate the host project directory; run update.sh on the host once"
    # Use the compose-assigned project name so `docker compose up` reconciles the
    # EXISTING containers (which have hardcoded container_names) instead of trying
    # to create duplicates under a mismatched project → name conflicts.
    project_name = (me.labels or {}).get("com.docker.compose.project") \
        or os.path.basename(project_dir) or "media-server"

    # The updater script is baked into the bot image; pass it inline so there is
    # a single source of truth and nothing to deliver to the host separately.
    try:
        with open(os.path.join(os.path.dirname(__file__), "updater.sh")) as f:
            script = f.read()
    except Exception as e:
        return f"updater script missing from image: {e}"

    updater_tag = UPDATER_IMAGE.split(":", 1)[1] if ":" in UPDATER_IMAGE else "latest"
    updater_repo = UPDATER_IMAGE.split(":", 1)[0]
    try:
        client.images.pull(updater_repo, tag=updater_tag)
    except Exception as e:
        return f"updater image pull failed: {e}"

    # Clear any leftover updater from a previous interrupted run.
    try:
        client.containers.get(UPDATER_CONTAINER).remove(force=True)
    except Exception:
        pass

    try:
        client.containers.run(
            UPDATER_IMAGE,
            name=UPDATER_CONTAINER,
            command=["sh", "-c", script],
            detach=True,
            working_dir="/project",
            environment={
                "BOT_IMAGE_TAG": tag,
                "COMPOSE_PROJECT_NAME": project_name,
                "REPO_SLUG": REPO_SLUG,
            },
            volumes={
                "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"},
                project_dir: {"bind": "/project", "mode": "rw"},
            },
        )
    except Exception as e:
        return f"failed to launch updater: {e}"

    # Keep the DB tag in step with what the updater pins in .env, so cold starts
    # and update.sh agree.
    set_config("bot_image_tag", tag)
    return UPDATER_CONTAINER


def updater_status(name: str = UPDATER_CONTAINER) -> dict:
    """Inspect the updater container. Returns {running, exit_code, logs?}."""
    try:
        import docker
        c = docker.from_env().containers.get(name)
        c.reload()
        state = c.attrs.get("State", {}) or {}
        running = bool(state.get("Running"))
        out = {"running": running, "exit_code": state.get("ExitCode")}
        if not running:
            try:
                out["logs"] = c.logs(tail=25).decode(errors="ignore")
            except Exception:
                out["logs"] = ""
        return out
    except Exception as e:
        return {"running": False, "exit_code": -1, "logs": f"status check failed: {e}"}


def remove_updater(name: str = UPDATER_CONTAINER) -> None:
    """Remove the ephemeral updater container (best effort)."""
    try:
        import docker
        docker.from_env().containers.get(name).remove(force=True)
    except Exception:
        pass
