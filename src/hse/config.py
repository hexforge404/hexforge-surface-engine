from pathlib import Path
import os

# Public assets root inside the web server (URL prefix)
PUBLIC_ASSETS_URL_ROOT = os.getenv("HSE_PUBLIC_ASSETS_URL_ROOT", "/assets/surface")

# On-disk root that corresponds to the /assets URL in nginx
# This MUST map to the nginx-mounted /usr/share/nginx/html/assets on the web side.
PUBLIC_ASSETS_DISK_ROOT = Path(
    os.getenv("HSE_PUBLIC_ASSETS_DISK_ROOT", "/mnt/hdd-storage/hexforge-assets/assets")
).resolve()

# HSE-specific sub-root under the shared /assets
SURFACE_SUBDIR = "surface"

def surface_assets_root() -> Path:
    return (PUBLIC_ASSETS_DISK_ROOT / SURFACE_SUBDIR).resolve()
