# scripts/derive_polymarket_creds.py
import os
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON


def derive_creds():
    private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
    if not private_key:
        raise ValueError("Set POLYMARKET_PRIVATE_KEY in environment")

    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=POLYGON,  # 137
    )

    # This is the correct method name
    api_creds = client.create_api_key()

    print(f"POLYMARKET_API_KEY={api_creds.api_key}")
    print(f"POLYMARKET_SECRET={api_creds.api_secret}")
    print(f"POLYMARKET_PASSPHRASE={api_creds.api_passphrase}")


if __name__ == "__main__":
    derive_creds()
