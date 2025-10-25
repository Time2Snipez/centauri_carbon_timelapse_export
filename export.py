#!/usr/bin/env python3
import asyncio, json, time, uuid, urllib.request, argparse, sys, os, re
import websockets
from urllib.parse import urljoin

PING_INTERVAL = 20  # seconds

def make_export_cmd(path: str):
    return {
        "Id": "",
        "Data": {
            "Cmd": 323,
            "Data": {"Url": [path]},
            "RequestID": uuid.uuid4().hex,
            "MainboardID": "",
            "TimeStamp": int(time.time() * 1000),
            "From": 1
        }
    }

def http_exists(url: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception:
        return False

def http_get(url: str, timeout: float = 10.0) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()

def download_file(url: str, dest_path: str, timeout: float = 30.0, retries: int = 5, backoff: float = 1.5, verbose: bool = False):
    """Download url -> dest_path with basic retries."""
    wait = 1.0
    for attempt in range(1, retries + 1):
        try:
            if verbose:
                print(f"[download] Attempt {attempt}: {url} -> {dest_path}")
            with urllib.request.urlopen(url, timeout=timeout) as r, open(dest_path, "wb") as f:
                # Stream in chunks
                while True:
                    chunk = r.read(1024 * 64)
                    if not chunk:
                        break
                    f.write(chunk)
            if verbose:
                print("[download] Success")
            return True
        except Exception as e:
            if attempt == retries:
                print(f"[download] Failed: {e}", file=sys.stderr)
                return False
            time.sleep(wait)
            wait = min(wait * backoff, 8.0)
    return False

def parse_latest_from_listing(html: str):
    row_re = re.compile(r"<tr\b[^>]*>([\s\S]*?)</tr>", re.IGNORECASE)
    link_re = re.compile(r'<a[^>]*href="(?![^"]*\.mp4)([^"]+)"[^>]*>([\s\S]*?)</a>', re.IGNORECASE)
    td_name_re = re.compile(r'<td[^>]*\bname\s*=\s*"?(-?\d+)"?[^>]*>', re.IGNORECASE)

    latest = None
    for m in row_re.finditer(html):
        row = m.group(1)
        link = link_re.search(row)
        if not link:
            continue
        href = link.group(1)
        name = re.sub(r"<[^>]*>", "", (link.group(2) or "")).strip() or href

        td_vals = [int(n) for n in td_name_re.findall(row) if re.match(r"-?\d+$", n)]
        modified = td_vals[0] if td_vals else None
        if modified is None:
            continue

        if (latest is None) or (modified > latest["modified"]):
            latest = {"name": name, "href": href, "modified": modified}

    return latest

def find_latest_mp4_path(host: str, list_path: str, verbose: bool=False) -> str:
    """
    Fetch directory listing at list_path (e.g. /local/aic_tlp/) and compute the mp4 path for latest item.
    If listing provides href like '/local/aic_tlp/NAME/', turn it into '/local/aic_tlp/NAME.mp4'
    """
    base_url = f"http://{host}"
    page_url = urljoin(base_url, list_path if list_path.endswith("/") else list_path + "/")

    if verbose:
        print(f"[latest] Fetching listing: {page_url}")
    try:
        html = http_get(page_url).decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[latest] Failed to fetch listing: {e}", file=sys.stderr)
        sys.exit(1)

    latest = parse_latest_from_listing(html)
    if not latest:
        print("[latest] Could not find any entries on listing page.", file=sys.stderr)
        sys.exit(1)

    # Trim trailing slash from visible name, build mp4 path from href or name.
    vis_name = latest["name"][:-1] if latest["name"].endswith("/") else latest["name"]
    href = latest["href"]

    # If href already absolute, use it; else join with list_path
    if href.startswith("/"):
        candidate_base = href
    else:
        candidate_base = urljoin(list_path if list_path.endswith("/") else list_path + "/", href)

    # Remove trailing slash, append .mp4
    candidate_base = candidate_base[:-1] if candidate_base.endswith("/") else candidate_base
    mp4_path = f"{candidate_base}.mp4"

    if verbose:
        ts_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(latest["modified"]))
        print(f"[latest] Latest item: name='{vis_name}' href='{href}' modified={latest['modified']} ({ts_iso})")
        print(f"[latest] Resolved MP4 path: {mp4_path}")

    return mp4_path

async def run(host: str, target_mp4: str, check: bool, max_wait: int, verbose: bool, download_dir: str, url_only: bool = False):
    ws_url = f"ws://{host}:3030/websocket"
    http_url = f"http://{host}{target_mp4}"
    filename = os.path.basename(target_mp4)
    dest_path = os.path.join(download_dir, filename)

    async with websockets.connect(ws_url) as ws:
        # 1) send export trigger
        await ws.send(json.dumps(make_export_cmd(target_mp4)))
        print(f"Export requested for: {target_mp4}")

        # 2) keepalive pings (optional)
        async def keepalive():
            try:
                while True:
                    await asyncio.sleep(PING_INTERVAL)
                    await ws.send("ping")
            except Exception:
                pass

        # 3) wait for WS confirmation (Cmd 323 + same Url)
        ws_ready = asyncio.Event()
        http_ready = asyncio.Event()

        async def ws_waiter():
            while not ws_ready.is_set():
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=PING_INTERVAL + 10)
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    if verbose:
                        print("[ws] recv error/closed", file=sys.stderr)
                    break

                try:
                    data = json.loads(msg)
                except Exception:
                    continue

                d = (data or {}).get("Data") or {}
                if d.get("Cmd") == 323:
                    urls = ((d.get("Data") or {}).get("Url")) or []
                    got = urls[0] if urls else None
                    if verbose:
                        print(f"[ws] 323 for: {got}")
                    if got == target_mp4:
                        ws_ready.set()
                        return
                    if verbose and got != target_mp4 and got:
                        print(f"[ws] 323 for different file: {got}", file=sys.stderr)

        # 4) poll HTTP as a fallback/parallel completion detector
        async def http_waiter():
            delay = 1.5
            start = time.time()
            while time.time() - start < max_wait and not http_ready.is_set():
                if http_exists(http_url, timeout=3):
                    http_ready.set()
                    return
                await asyncio.sleep(delay)
                delay = min(delay * 1.5, 5.0)

        ka = asyncio.create_task(keepalive())
        tws = asyncio.create_task(ws_waiter())
        thttp = asyncio.create_task(http_waiter())

        try:
            done, pending = await asyncio.wait(
                {tws, thttp},
                timeout=max_wait,
                return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            for t in (tws, thttp):
                if not t.done():
                    t.cancel()

        ok = ws_ready.is_set() or http_ready.is_set()
        if ok and check and not http_ready.is_set():
            if http_exists(http_url, timeout=5):
                http_ready.set()

        ka.cancel()

        if not ok:
            print(f"ERROR: timed out after {max_wait}s waiting for {target_mp4}", file=sys.stderr)
            sys.exit(1)

        print(f"Timelapse ready at: {http_url}")
        if check and not http_ready.is_set():
            print("(Heads-up: WS said ready, HTTP not yet downloadable)")

        if url_only:
            print(f"Download URL: {http_url}")
            return

        # 7) Download the file (with a couple of retries in case disk write or tiny delay)
        os.makedirs(download_dir, exist_ok=True)
        success = download_file(http_url, dest_path, verbose=verbose)
        if not success:
            print(f"ERROR: download failed for {http_url}", file=sys.stderr)
            sys.exit(2)
        print(f"Saved: {dest_path}")

def main():
    ap = argparse.ArgumentParser(description="Trigger Centauri timelapse export and wait for completion; optionally auto-pick latest and download.")
    ap.add_argument("host", help="Printer IP/host")
    ap.add_argument("file", nargs="?", help="MP4 path as shown by the UI, e.g. NAME.mp4")
    ap.add_argument("--check", action="store_true", help="HTTP check after ready")
    ap.add_argument("--timeout", type=int, default=180, help="Max seconds to wait (default 180)")
    ap.add_argument("--verbose", action="store_true", help="Log extra WS/download info")

    # New options
    ap.add_argument("--latest", action="store_true", help="Discover latest item from listing, then export and download it")
    ap.add_argument("--list-path", default="/local/aic_tlp/", help="Listing path used with --latest (default /local/aic_tlp/)")
    ap.add_argument("--out-dir", default=".", help="Directory to save the downloaded MP4 (default current dir)")
    ap.add_argument("--url-only", action="store_true", help="Return the download URL without downloading the file")
    args = ap.parse_args()

    # Validate parameters
    if args.latest:
        # Discover latest MP4 path from the listing page
        target_mp4 = find_latest_mp4_path(args.host, args.list_path, verbose=args.verbose)
    else:
        if not args.file:
            print("ERROR: provide a file path or use --latest", file=sys.stderr)
            sys.exit(2)
        target_mp4 = args.list_path + args.file

    asyncio.run(run(args.host, target_mp4, args.check, args.timeout, args.verbose, args.out_dir, args.url_only))

if __name__ == "__main__":
    main()

