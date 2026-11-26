"""Publish the RoofMaster Android association without changing application code."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request

FINGERPRINTS = [
    '58:F0:59:1E:D6:E2:E8:28:A5:CF:55:0E:04:EB:EA:E6:76:08:2B:20:27:5F:43:14:F8:82:ED:07:7A:73:8D:EA',
    '81:72:F6:24:7F:35:1B:74:B2:9F:36:2B:D7:5E:05:70:E6:1C:7E:2D:AC:6F:71:BB:CB:F8:B6:A6:EF:50:3F:D7',
    'CE:08:21:21:28:1C:CB:4A:58:78:18:80:9D:FF:A7:46:1A:B8:E4:C1:3D:17:CC:9F:16:58:9C:76:BD:7C:67:3A',
]
ASSOCIATION = [{'relation': ['delegate_permission/common.handle_all_urls'], 'target': {
    'namespace': 'android_app', 'package_name': 'eu.roofmaaster.app',
    'sha256_cert_fingerprints': FINGERPRINTS,
}}]
LOCATION = '''
    # RoofMaster Android App Links, Play signing certificates.
    location = /.well-known/assetlinks.json {
        alias /var/www/roofmaster-android/assetlinks.json;
        default_type application/json;
        add_header Cache-Control "public, max-age=300";
        limit_except GET { deny all; }
    }
'''

def configure(text):
    if 'location = /.well-known/assetlinks.json' in text:
        if 'alias /var/www/roofmaster-android/assetlinks.json;' not in text:
            raise RuntimeError('An existing association route needs manual review.')
        return text
    matches = []
    for match in re.finditer(r'\bserver\s*\{', text):
        depth, pos = 1, match.end()
        while pos < len(text) and depth:
            depth += (text[pos] == '{') - (text[pos] == '}')
            pos += 1
        block = text[match.end():pos - 1]
        name = re.search(r'\bserver_name\s+roofmaaster\.eu\s*;', block)
        if name and re.search(r'\blisten\s+443\b', block):
            matches.append(match.end() + name.end())
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one canonical RoofMaster HTTPS server.')
    point = matches[0]
    return text[:point] + '\n' + LOCATION + text[point:]


def write_atomic(path, content, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Run as root on the RoofMaster host.')
    config = Path('/etc/nginx/sites-enabled/roofmaaster.eu').resolve(strict=True)
    asset = Path('/var/www/roofmaster-android/assetlinks.json')
    original = config.read_bytes()
    updated = configure(original.decode()).encode()
    previous_asset = asset.read_bytes() if asset.exists() else None
    config_mode = config.stat().st_mode & 0o777
    backup = Path('/var/backups/roofmaster-app-links') / time.strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(config, backup / 'nginx.conf')
    if previous_asset is not None:
        shutil.copy2(asset, backup / 'assetlinks.json')
    try:
        write_atomic(asset, (json.dumps(ASSOCIATION, indent=2) + '\n').encode())
        write_atomic(config, updated, config_mode)
        subprocess.run(['nginx', '-t'], check=True)
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
        with urllib.request.urlopen('https://roofmaaster.eu/.well-known/assetlinks.json', timeout=20) as response:
            if response.status != 200 or response.geturl() != 'https://roofmaaster.eu/.well-known/assetlinks.json':
                raise RuntimeError('Association must return HTTP 200 without redirects.')
            if response.headers.get_content_type() != 'application/json':
                raise RuntimeError('Association has incorrect content type.')
            if json.load(response) != ASSOCIATION:
                raise RuntimeError('Public association does not match Play Console.')
    except BaseException:
        write_atomic(config, original, config_mode)
        if previous_asset is None:
            asset.unlink(missing_ok=True)
        else:
            write_atomic(asset, previous_asset)
        subprocess.run(['nginx', '-t'], check=True)
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
        raise
    print('ROOFMASTER_APP_LINKS_READY HTTP_200 application/json eu.roofmaaster.app certificates=3')
    print('BACKUP', backup)

if __name__ == '__main__':
    main()
