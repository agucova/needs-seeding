import bencodepy
import hashlib
import btdht
import binascii
import asyncio
import requests
import os
import contextlib
import urllib.request
import csv
from typing import List, Tuple
from multiprocessing.pool import ThreadPool
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path


LINK = "http://libgen.rs/scimag/repository_torrent/"
DOWNLOAD_PATH = "torrents/"

OUTPUT_CSV = True
OUTPUT_PATH = "torrents_check.csv"

CHECK_MAX_TORRENTS = 10
SHOW_MAX_TORRENTS = 5


def supress_stdout(func):
    def wrapper(*a, **ka):
        with open(os.devnull, "w") as devnull:
            with contextlib.redirect_stdout(devnull):
                func(*a, **ka)

    return wrapper


def fetch_url(uri):
    torrent_name = os.path.basename(uri)
    path = DOWNLOAD_PATH + torrent_name
    if not os.path.exists(path):
        r = requests.get(uri, stream=True)
        if r.status_code == 200:
            with open(path, "wb") as f:
                for chunk in r:
                    f.write(chunk)
    return path


async def check_peers(paths: List[str]) -> List[Tuple[str, int]]:
    dht = btdht.DHT()
    dht.start()
    print("[INFO] Starting DHT...")
    await asyncio.sleep(20)

    async def check_peer(path: str) -> Tuple[str, int]:
        torrent_name = os.path.basename(path)
        info_hash = hashlib.sha1(
            bencodepy.encode(bencodepy.bread(path)[b"info"])
        ).hexdigest()
        peers = dht.get_peers(binascii.a2b_hex(info_hash), limit=20, block=True)
        peers = peers if peers else []
        return torrent_name, len(peers)
    
    return await asyncio.gather(
        *(check_peer(path) for path in paths), return_exceptions=True
    )


async def main():
    print("[INFO] Getting torrent list...")
    page = urllib.request.urlopen(LINK)
    soup = BeautifulSoup(page, "html.parser")
    torrents = [urljoin(LINK, link.get("href")) for link in soup.findAll("a")][
        :CHECK_MAX_TORRENTS
    ]
    torrents = [torrent for torrent in torrents if ".torrent" in torrent]
    
    print("[INFO] Downloading .torrent files...")
    Path(DOWNLOAD_PATH).mkdir(exist_ok=True)
    paths = ThreadPool().imap(fetch_url, torrents)
    
    print("[INFO] Checking torrents...")
    checks = await check_peers(paths=paths)

    # Discard errors
    checks = [check for check in checks if isinstance(check, tuple)]
    checks = sorted(checks, key=lambda x: x[1])
    
    print()
    print(f"[RESULT] Top {SHOW_MAX_TORRENTS} less seeded torrents:")
    for check in checks[:SHOW_MAX_TORRENTS]:
        print(f"[{check[1]} peers] {check[0]}")
    
    if OUTPUT_CSV:
        with open(OUTPUT_PATH, "w") as f:
            co = csv.writer(f)
            co.writerow(["torrent", "peers"])
            for check in checks:
                co.writerow(check)


asyncio.run(main())
