"""Fetch only pinned public source bytes; never extract paths from an archive."""
import hashlib
import tarfile
import requests
from common import DATA, REPORT, save, protocol

ARCHIVE_SHA = '043a7d81c0b98de1a093d7aa9fbe57527924eb4bb013d7d39cbd313683ce46e0'
FILES = {'web_sites.avt': '1ca07999ad93d3206f59073ead289277b1a301c9c864212e6b0b12e938d49809',
         'pl-app.avt': '17f6e972733e7c8621153d4ff0985b4242e2608214cc8d4b1a5ae194db919eb2',
         'availability.bib': '0d22771692e4f3857e070a28631024b36223a1d3de441fa1dcc67a9d6ad1d4af'}


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    archive = DATA / 'availability-0.3.tar.bz2'
    url = protocol()['source']['archive_url']
    if not archive.exists():
        r = requests.get(url, timeout=(10, 90)); r.raise_for_status()
        archive.write_bytes(r.content)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError('Archive checksum changed; refuse unpinned input')
    source = {'url': url, 'archive_sha256': ARCHIVE_SHA, 'bytes': archive.stat().st_size, 'files': {}}
    with tarfile.open(archive, 'r:bz2') as tar:
        for name, expected in FILES.items():
            matches = [m for m in tar.getmembers() if m.isfile() and m.name.split('/')[-1] == name]
            if len(matches) != 1:
                raise ValueError('Archive entry missing or ambiguous')
            data = tar.extractfile(matches[0]).read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('Source file checksum mismatch')
            (DATA / name).write_bytes(data)
            source['files'][name] = {'sha256': expected, 'bytes': len(data)}
    save(REPORT / 'sources.json', source)
    print(source)


if __name__ == '__main__':
    main()
