from typing import List, Tuple
import bencodepy
import hashlib
import btdht
import binascii
import asyncio
from multiprocessing.pool import ThreadPool
import requests
import os
from bs4 import BeautifulSoup
import urllib.request
from urllib.parse import urljoin
from pathlib import Path

LINK = "http://libgen.rs/scimag/repository_torrent/"
OUTPUT_PATH = "./torrents/"

def fetch_url(uri):
    path = OUTPUT_PATH + os.path.basename(uri)
    print(f"Writing to {path}")
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
    await asyncio.sleep(15)

    async def check_peer(path: str) -> Tuple[str, int]:
        print(f"Checking {path}...")
        info_hash = hashlib.sha1(
            bencodepy.encode(bencodepy.bread(path)[b"info"])
        ).hexdigest
        print(f"Got infohash for {path}.")
        peers = dht.get_peers(binascii.a2b_hex(info_hash), limit=20, block=True)
        print(f"Got {len(peers)} peers for {path}.")
        return path, len(peers)

    return await asyncio.gather(
        *(check_peer(path) for path in paths), return_exceptions=True
    )


page = urllib.request.urlopen(LINK)
soup = BeautifulSoup(page, "html.parser")
torrents = [urljoin(LINK, link.get("href")) for link in soup.findAll("a")]
torrents = [torrent for torrent in torrents if ".torrent" in torrent]
Path(OUTPUT_PATH).mkdir(exist_ok=True)
paths = ThreadPool(8).imap(fetch_url, torrents)
for path in paths:
    print(path)

asyncio.run(check_peers(paths=paths))
