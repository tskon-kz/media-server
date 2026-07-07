import json
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
    BOT_IMAGE, BOT_CONTAINER,
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


def self_update(tag: str) -> bool | str:
    """Replace the running bot container with `tag` via the Docker Engine API.

    Blue/green, new-before-old: pulls the image, starts a replacement container
    from a clone of this container's live config, confirms it is healthy, and
    only then retires the old one. A bad pull/start never leaves the user with
    no bot. Returns True on success, or an error string on failure (in which
    case the original bot keeps running untouched).

    ONLY the bot container is touched — qBittorrent/Jellyfin/Jackett/cloudflared
    are never recreated, so a bot update can't reset qB auth or churn the tunnel
    URL. Infrastructure/topology changes go through update.sh on the host. The
    canonical container name is preserved, so cloudflared keeps resolving
    `telegram-bot`. `tag` is `stable` or `edge` (the channel switcher).

    Runs via asyncio.to_thread; the current process is replaced at the very end,
    so on success this may not return at all — the new container reports done via
    the `update_pending` flag in _post_init.
    """
    import time
    try:
        import docker
    except Exception as e:
        return f"docker SDK unavailable: {e}"
    try:
        client = docker.from_env()
    except Exception as e:
        return f"cannot reach Docker socket: {e}"

    image_ref = f"{BOT_IMAGE}:{tag}"
    try:
        client.images.pull(BOT_IMAGE, tag=tag)
    except Exception as e:
        return f"pull failed: {e}"

    # Our own container ID is the hostname inside the container.
    try:
        me = client.containers.get(socket.gethostname())
    except Exception as e:
        return f"self-inspect failed: {e}"

    cfg      = me.attrs
    host_cfg = cfg.get("HostConfig", {}) or {}
    conf     = cfg.get("Config", {}) or {}

    # Clone the live env, but drop APP_VERSION so the NEW image's baked-in value
    # (from its build ARG) wins — otherwise the replacement would report the old
    # version. Everything else (BOT_TOKEN, QB_HOST, proxy, …) is carried over.
    env = [e for e in (conf.get("Env") or []) if not e.startswith("APP_VERSION=")]
    run_kwargs = {
        "image":       image_ref,
        "detach":      True,
        "environment": env,
        "volumes":     host_cfg.get("Binds") or [],
        "labels":      conf.get("Labels") or {},
    }
    rp = host_cfg.get("RestartPolicy") or {}
    if rp.get("Name"):
        run_kwargs["restart_policy"] = {
            "Name": rp["Name"],
            "MaximumRetryCount": rp.get("MaximumRetryCount", 0),
        }

    # The replacement must keep answering to the SAME compose network alias
    # (e.g. `telegram-bot`) that cloudflared and other services dial — otherwise
    # Docker DNS can't resolve it and the tunnel 502s. Cloning NetworkMode alone
    # is not enough (it re-joins the network but only under the container name),
    # so we attach explicitly with the old container's aliases after create.
    networks = (cfg.get("NetworkSettings", {}) or {}).get("Networks", {}) or {}
    net_name = next(iter(networks), None)
    aliases = [a for a in (networks.get(net_name, {}).get("Aliases") or [])
               if a and not me.id.startswith(a)] if net_name else []
    compose_service = (conf.get("Labels") or {}).get("com.docker.compose.service")
    if compose_service and compose_service not in aliases:
        aliases.append(compose_service)

    new_name = f"{BOT_CONTAINER}-new"
    old_name = f"{BOT_CONTAINER}-old"
    # Clear any leftovers from a previous interrupted update.
    for stale in (new_name, old_name):
        try:
            client.containers.get(stale).remove(force=True)
        except Exception:
            pass

    new = None
    try:
        # create (not run) so we can attach to the compose network WITH aliases
        # before the container starts.
        new = client.containers.create(name=new_name, **run_kwargs)
        if net_name:
            # create() auto-joins the default bridge; move it onto the compose
            # network under the right aliases.
            try:
                client.networks.get("bridge").disconnect(new, force=True)
            except Exception:
                pass
            client.networks.get(net_name).connect(new, aliases=aliases or None)
        new.start()
    except Exception as e:
        if new is not None:
            try: new.remove(force=True)
            except Exception: pass
        return f"start replacement failed: {e}"

    # Confirm the replacement stays up (a broken image would exit immediately).
    time.sleep(6)
    try:
        new.reload()
    except Exception as e:
        try: new.remove(force=True)
        except Exception: pass
        return f"replacement health check failed: {e}"
    if new.status != "running":
        logs = ""
        try: logs = new.logs(tail=20).decode(errors="ignore")
        except Exception: pass
        try: new.remove(force=True)
        except Exception: pass
        return f"replacement not running (status={new.status}). Old bot kept.\n{logs[-400:]}"

    # Healthy. Put everything in its final state BEFORE stopping ourselves, so
    # even if this process dies mid-teardown the new bot already owns the
    # canonical name and is running.
    try:
        me.rename(old_name)
        new.rename(BOT_CONTAINER)
    except Exception as e:
        # Naming failed but the new container is alive; report so the maintainer
        # can reconcile with `docker compose up -d` on next cold start.
        return f"replacement running but rename failed: {e}"

    set_config("bot_image_tag", tag)

    # Retire the old container last. This stops our own process; anything after
    # the stop call is not guaranteed to run, which is fine — state is final.
    try:
        me.remove(force=True)
    except Exception:
        pass
    return True
