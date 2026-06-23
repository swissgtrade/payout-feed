import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)

BUILDS = [
    (
        "firmup-payout-carousel.zip",
        "firmup-payout-carousel",
        [
            "firmup-payout-carousel.php",
            "assets/payout-carousel.css",
            "assets/payout-carousel.js",
        ],
    ),
    (
        "firmup-payouts.zip",
        "firmup-payouts",
        [
            "firmup-payouts.php",
            "INSTALL.txt",
            "assets/payout-carousel.css",
            "assets/payout-carousel.js",
        ],
    ),
]

carousel_assets = ROOT / "wordpress" / "assets"
carousel_plugin_assets = ROOT / "wordpress" / "firmup-payout-carousel" / "assets"
carousel_plugin_assets.mkdir(parents=True, exist_ok=True)
for name in ("payout-carousel.css", "payout-carousel.js"):
    shutil.copy2(carousel_assets / name, carousel_plugin_assets / name)

for zip_name, folder, files in BUILDS:
    zip_path = DIST / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            if folder == "firmup-payout-carousel":
                src = ROOT / "wordpress" / folder / rel
            else:
                src = ROOT / "wordpress" / rel
            arcname = f"{folder}/{rel}"
            zf.write(src, arcname)
            print(f"{zip_name}: {arcname}")
    print(f"OK {zip_path} ({zip_path.stat().st_size} bytes)\n")
