import argparse
import logging
import sys

from src.crypto import decrypt_file


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Decrypt a Vaultwarden backup")
    parser.add_argument("input", help="Path to encrypted backup file (.enc)")
    parser.add_argument("output", help="Path for decrypted archive (.tar.gz)")
    parser.add_argument("-p", "--password", help="Encryption password (or set DECRYPTION_PASSWORD env)")
    args = parser.parse_args()

    password = args.password
    if not password:
        import os
        password = os.getenv("DECRYPTION_PASSWORD", "")
    if not password:
        logger.error("Password required: use -p or set DECRYPTION_PASSWORD")
        sys.exit(1)

    try:
        decrypt_file(args.input, args.output, password)
        logger.info("Decrypted %s -> %s", args.input, args.output)
    except Exception:
        logger.exception("Decryption failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
