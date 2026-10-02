import json
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

TEST_ISSUER = "https://api.guard-core.test"
TEST_AUDIENCE = "https://mcp.guard-core.test"
TEST_SCOPE = "mcp"
TEST_KID = "guard-test-key"


def generate_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def build_jwks(pem: str) -> str:
    private_key = serialization.load_pem_private_key(pem.encode(), password=None)
    entry = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    entry["kid"] = TEST_KID
    entry["alg"] = "RS256"
    return json.dumps({"keys": [entry]})


def sign_token(pem: str, kid: str = TEST_KID, **overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": TEST_ISSUER,
        "aud": TEST_AUDIENCE,
        "sub": "user_abc123",
        "scope": TEST_SCOPE,
        "iat": now,
        "exp": now + 600,
        "jti": "token-1",
    }
    for name, value in overrides.items():
        if value is None:
            claims.pop(name, None)
        else:
            claims[name] = value
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})
