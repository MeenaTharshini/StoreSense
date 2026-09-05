"""
StoreSense QR Code Generator

Generates QR codes that open the StoreSense mobile
quick-entry page for a specific store.

Example:

    python -m src.qr

This creates:

    qr_codes/
        main_store.png
        mall_store.png
        campus_store.png
"""


from pathlib import Path
import re

import qrcode


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

# Change this IP to the IP address of the computer
# running StoreSense.
#
# Example:
#
# http://192.168.1.25:8000
#
# IMPORTANT:
# The phone and computer must normally be connected
# to the same Wi-Fi network for this local demo.
#
BASE_URL = "http://192.168.1.25:8000"


# Stores used by the current StoreSense dataset.
#
# The IDs MUST match the store_id values in stores.csv.
STORES = [
    {
        "store_id": "STORE_01",
        "store_name": "Main Street Store",
    },
    {
        "store_id": "STORE_02",
        "store_name": "Mall Store",
    },
    {
        "store_id": "STORE_03",
        "store_name": "Campus Store",
    },
]


# Output directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIR = PROJECT_ROOT / "qr_codes"


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def safe_filename(name: str) -> str:
    """
    Convert a store name into a safe filename.

    Example:
        Main Street Store
        ->
        main_street_store
    """

    name = name.strip().lower()

    name = re.sub(
        r"[^a-z0-9]+",
        "_",
        name
    )

    return name.strip("_")


def build_mobile_url(store_id: str) -> str:
    """
    Build the URL embedded inside the QR code.
    """

    return (
        f"{BASE_URL.rstrip('/')}"
        f"/mobile?store={store_id}"
    )


def generate_qr(
    store_id: str,
    store_name: str
) -> Path:
    """
    Generate a QR code for one store.

    Returns the generated file path.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    url = build_mobile_url(store_id)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    qr.add_data(url)

    qr.make(
        fit=True
    )

    image = qr.make_image()

    filename = (
        f"{safe_filename(store_name)}.png"
    )

    output_path = (
        OUTPUT_DIR / filename
    )

    image.save(output_path)

    print(
        f"Generated: {output_path}"
    )

    print(
        f"Store: {store_name}"
    )

    print(
        f"URL:   {url}"
    )

    print("-" * 60)

    return output_path


# ---------------------------------------------------------
# Generate all store QR codes
# ---------------------------------------------------------

def generate_all_qr_codes():
    """
    Generate QR codes for all configured stores.
    """

    print()
    print("=" * 60)
    print("StoreSense QR Code Generator")
    print("=" * 60)
    print()

    print(
        f"Base URL: {BASE_URL}"
    )

    print()

    for store in STORES:

        generate_qr(
            store_id=store["store_id"],
            store_name=store["store_name"]
        )

    print()
    print("=" * 60)
    print("QR generation completed.")
    print(f"Files saved to: {OUTPUT_DIR}")
    print("=" * 60)
    print()


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

if __name__ == "__main__":
    generate_all_qr_codes()
    