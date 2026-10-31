"""Download the pinned CC BY 4.0 source in bounded HTTP ranges, verify upstream checksum."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path('dataset/public/road-damage-17834373')
URL='https://zenodo.org/api/records/17834373/files/archive.zip/content'
SIZE=193459929
MD5='ef8b402e9f7ee7d2e64919f21ad6ab6a'

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    def fetch(part):
        start=part*8_000_000;end=min(SIZE,start+8_000_000)-1
        path=ROOT/f'part-{part:03d}'
        if path.exists() and path.stat().st_size==end-start+1:return path
        req=urllib.request.Request(URL,headers={'Range':f'bytes={start}-{end}'})
        with urllib.request.urlopen(req,timeout=120) as response:
            if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{SIZE}':raise ValueError('Unexpected range response')
            with path.open('wb') as out:
                while True:
                    chunk=response.read(65536)
                    if not chunk:break
                    out.write(chunk)
        if path.stat().st_size!=end-start+1:raise ValueError('Incomplete range')
        print('Downloaded part',part,flush=True)
        return path
    with ThreadPoolExecutor(max_workers=6) as pool:parts=list(pool.map(fetch,range((SIZE+7_999_999)//8_000_000)))
    dest=ROOT/'verified.zip';digest=hashlib.md5()
    with dest.open('wb') as out:
        for path in parts:
            data=path.read_bytes();digest.update(data);out.write(data)
    if digest.hexdigest()!=MD5:raise ValueError('Source checksum mismatch')
    for path in parts:path.unlink()
    print('Verified source MD5',MD5,flush=True)

if __name__=='__main__':main()
