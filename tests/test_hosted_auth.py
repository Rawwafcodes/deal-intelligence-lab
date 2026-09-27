"""Task 19.4 (M19): hosted sign-in (DEAL_LAB_AUTH_MODE=clerk).

A real HTTP server with a real RSA key pair and real signed JWTs, standing in
for Clerk's JWKS. Proves that in hosted mode identity comes only from a
verified token, that nobody is silently given the default identity, that
sign-in is invite-only, and that the dev identity endpoints are gone."""

import json
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

import auth_tokens
import identity
import server
import store

ISSUER = "https://clerk.example.test"
ORIGIN = "https://staging.example.test"


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


SIGNING_KEY = _key()
OTHER_KEY = _key()


class _Resolver:
    """Stands in for PyJWKClient: always returns this deployment's public key."""

    def get_signing_key_from_jwt(self, token):
        return type("K", (), {"key": SIGNING_KEY.public_key()})()


def _token(sub="user_abc", email=None, key=SIGNING_KEY, iss=ISSUER, azp=ORIGIN, exp_in=60, alg="RS256"):
    now = int(time.time())
    claims = {"sub": sub, "iss": iss, "iat": now, "nbf": now, "exp": now + exp_in, "sid": "sess_1"}
    if azp is not None:
        claims["azp"] = azp
    if email is not None:
        claims["email"] = email
    return jwt.encode(claims, key, algorithm=alg)


class HostedAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        identity.init_identity_db()
        cls.invited = identity.create_user("Invited.Person@Example.com", "Invited Person")
        cls._env = patch.dict("os.environ", {
            "DEAL_LAB_AUTH_ISSUER": ISSUER, "DEAL_LAB_AUTH_AUTHORIZED_PARTIES": ORIGIN,
        })
        cls._env.start()
        cls._mode = patch.object(server, "AUTH_MODE", "clerk")
        cls._mode.start()
        auth_tokens.set_key_resolver(_Resolver())
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        auth_tokens.set_key_resolver(None)
        cls._mode.stop()
        cls._env.stop()
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def _get(self, path, token=None, cookie=None, method="GET", body=None):
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if cookie:
            headers["Cookie"] = f"__session={cookie}"
        data = json.dumps(body).encode() if body is not None else None
        if data:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=headers, method=method)
        try:
            res = urllib.request.urlopen(req)
            return res.status, json.loads(res.read() or b"null"), res.headers
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"null"), exc.headers

    def test_no_token_is_401_never_the_default_identity(self):
        status, body, headers = self._get("/api/session")
        self.assertEqual(status, 401)
        self.assertNotIn("dl_session", headers.get("Set-Cookie", "") or "")

    def test_health_is_public(self):
        self.assertEqual(self._get("/api/health")[0], 200)

    def test_invited_user_signs_in_by_email_then_by_linked_id(self):
        status, body, _ = self._get("/api/session", token=_token(sub="user_first", email="invited.person@example.com"))
        self.assertEqual(status, 200)
        self.assertEqual(body["user"]["id"], self.invited.id)
        # Once linked, the id alone is enough - no email claim needed.
        status, body, _ = self._get("/api/session", cookie=_token(sub="user_first"))
        self.assertEqual(status, 200)
        self.assertEqual(body["user"]["id"], self.invited.id)

    def test_uninvited_account_is_403(self):
        status, body, _ = self._get("/api/session", token=_token(sub="user_x", email="stranger@example.com"))
        self.assertEqual(status, 403)
        self.assertIn("not been invited", body["error"])

    def test_an_email_already_linked_to_another_sign_in_cannot_be_taken_over(self):
        other = identity.create_user("owner@example.com", "Owner")
        self.assertEqual(self._get("/api/session", token=_token(sub="user_owner", email="owner@example.com"))[1]["user"]["id"], other.id)
        status, _, _ = self._get("/api/session", token=_token(sub="user_imposter", email="owner@example.com"))
        self.assertEqual(status, 403)

    def test_seeded_dev_identities_can_never_be_signed_into(self):
        # lead@local.dev is a seeded org admin in every database.
        status, _, _ = self._get("/api/session", token=_token(sub="user_devlead", email="lead@local.dev"))
        self.assertEqual(status, 403)

    def test_rejected_tokens(self):
        cases = {
            "expired": _token(exp_in=-60),
            "wrong issuer": _token(iss="https://evil.example"),
            "wrong origin (azp)": _token(azp="https://evil.example"),
            "forged signature": _token(key=OTHER_KEY),
            "garbage": "not-a-jwt",
        }
        for label, token in cases.items():
            with self.subTest(label):
                self.assertEqual(self._get("/api/session", token=token)[0], 401)

    def test_hs256_signed_token_is_rejected(self):
        # Only RS256 is accepted - a symmetric-algorithm token must never verify.
        now = int(time.time())
        hs = jwt.encode({"sub": "user_first", "iss": ISSUER, "iat": now, "exp": now + 60}, "s" * 32, algorithm="HS256")
        self.assertEqual(self._get("/api/session", token=hs)[0], 401)

    def test_dev_identity_endpoints_are_gone(self):
        token = _token(sub="user_first", email="invited.person@example.com")
        self.assertEqual(self._get("/api/dev/identities", token=token)[0], 404)
        status, _, _ = self._get("/api/dev/session", token=token, method="POST", body={"user_id": identity.get_default_user_id()})
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
