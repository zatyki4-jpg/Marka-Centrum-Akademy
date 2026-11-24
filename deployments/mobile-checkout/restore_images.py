#!/usr/bin/env python3
"""Restore five exact original course images without changing lesson records."""
import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request

ORIGIN = "https://id-preview--0be60f9c-cb81-4b7c-8ba2-969e84bb9145.lovable.app"
ROOT = Path("/srv/marka-course-academy/asset-mirror")
ASSETS = [
"35d2754e-1d89-48d0-97cc-64387983db19/e1-konstrukcja-drewniana.jpg",
"ab4b3783-7f00-4859-819b-7f09b0fe0916/e1-poszycie.jpg",
"5c29ae3a-47df-411f-a8b4-0afd6708ed2c/e1-stal-poszycie.jpg",
"c816fe77-fffd-49f1-adea-bc281d246eb6/e1-stal-detal.jpg",
"f8c2cada-ae8c-43d5-a462-afb31e7a2dae/e1-beton.jpg",
]
def main():
    if os.geteuid() != 0 or not ROOT.is_dir():
        raise RuntimeError("Existing Academy asset root required")
    for item in ASSETS:
        path = "/__l5e/assets-v1/" + item
        with urllib.request.urlopen(ORIGIN + path, timeout=30) as response:
            content = response.read(12000001)
            if response.geturl() != ORIGIN + path or response.headers.get_content_type() != "image/jpeg":
                raise RuntimeError("Original JPEG response required")
        if not 1000 < len(content) <= 12000000 or not content.startswith(b"\xff\xd8\xff") or not content.endswith(b"\xff\xd9"):
            raise RuntimeError("Invalid original JPEG")
        dest = ROOT / path.lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        if dest.exists():
            if dest.read_bytes() != content:
                raise RuntimeError("Refusing to overwrite a different existing image")
        else:
            fd, name = tempfile.mkstemp(dir=dest.parent)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(content)
                    output.flush()
                    os.fsync(output.fileno())
                os.chmod(name, 0o644)
                os.replace(name, dest)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
        with urllib.request.urlopen("https://www.markacentrumacademy.eu" + path, timeout=30) as response:
            served = response.read(12000001)
        if served != content:
            raise RuntimeError("Public image does not match original")
        print("ORIGINAL_VERIFIED", dest.name, len(content), hashlib.sha256(content).hexdigest())
    print("FIVE_ORIGINAL_IMAGES_RESTORED")
if __name__ == "__main__":
    main()
