"""Connection to the local Proton Mail Bridge IMAP server."""

import ssl

from imapclient import IMAPClient

from pmail import config


def connect() -> IMAPClient:
    """Log in to Bridge on this machine.

    Bridge uses a self-signed certificate and only listens on localhost, so
    certificate checks are skipped; we refuse to do that for any other host.
    """
    if config.BRIDGE_HOST not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("Refusing to skip TLS verification for a non-local Bridge host.")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    username, password = config.load_credentials()
    try:
        client = IMAPClient(config.BRIDGE_HOST, port=config.BRIDGE_IMAP_PORT, ssl=False, timeout=30)
    except ConnectionRefusedError:
        raise SystemExit(
            f"Can't reach Bridge at {config.BRIDGE_HOST}:{config.BRIDGE_IMAP_PORT}. "
            "Is Proton Mail Bridge running and signed in?"
        )
    client.starttls(ctx)
    client.login(username, password)
    return client
