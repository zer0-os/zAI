from typing import Dict, Any, Optional
import base64
import json
import os
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec


class PrivyAuthorizationSigner:
    """
    Utility class for generating Privy authorization signatures using ECDSA P-256.
    """

    def __init__(self, app_id: str, auth_key: Optional[str] = None):
        """
        Initialize the Privy authorization signer.

        Args:
            app_id: The Privy application ID
            auth_key: The private key from Privy dashboard. If not provided,
                     will look for PRIVY_SERVER_WALLETS_KEY environment variable
        """
        self.app_id = app_id
        self.auth_key = auth_key or os.getenv("PRIVY_SERVER_WALLETS_KEY")
        if not self.auth_key:
            raise ValueError("Privy authorization key is required")

        # Initialize private key
        self.private_key = self._load_private_key()

    def _load_private_key(self) -> ec.EllipticCurvePrivateKey:
        """Load and validate the private key."""
        key_content = self.auth_key.replace("wallet-auth:", "")
        pem = f"-----BEGIN PRIVATE KEY-----\n{key_content}\n-----END PRIVATE KEY-----"

        private_key = serialization.load_pem_private_key(pem.encode(), password=None)
        if not isinstance(private_key, ec.EllipticCurvePrivateKey):
            raise ValueError("Invalid key type. Expected P-256 private key")
        return private_key

    def _canonicalize(self, data: Dict[str, Any]) -> bytes:
        """Simple JSON canonicalization using sorted keys."""
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

    def get_auth_headers(
        self,
        url: str,
        body: Dict[str, Any],
        method: str = "POST",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Get all required Privy authorization headers for a request.

        Args:
            url: The full URL for the request
            body: The request body as a dictionary
            method: The HTTP method (default: POST)
            idempotency_key: Optional idempotency key

        Returns:
            Dictionary containing all required Privy headers
        """
        headers = {"privy-app-id": self.app_id}
        if idempotency_key:
            headers["privy-idempotency-key"] = idempotency_key

        payload = {
            "version": 1,
            "method": method.upper(),
            "url": url.rstrip("/"),
            "body": body,
            "headers": headers,
        }

        signature = self.private_key.sign(
            self._canonicalize(payload), ec.ECDSA(hashes.SHA256())
        )

        headers["privy-authorization-signature"] = base64.b64encode(signature).decode()
        return headers
