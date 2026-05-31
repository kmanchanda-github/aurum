"""Integration tests for the auth flow: register, login, /me."""
import pytest


def test_register_returns_201_and_token(client, unique_email):
    resp = client.post("/api/auth/register", json={
        "email": unique_email,
        "password": "SecurePass1!",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


def test_register_duplicate_email_returns_409(client, unique_email):
    payload = {"email": unique_email, "password": "SecurePass1!"}
    client.post("/api/auth/register", json=payload)  # first registration
    resp = client.post("/api/auth/register", json=payload)  # duplicate
    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"].lower()


def test_register_with_full_profile(client, unique_email):
    resp = client.post("/api/auth/register", json={
        "email": unique_email,
        "password": "MyPass123!",
        "full_name": "Jane Doe",
        "risk_tolerance": "aggressive",
        "knowledge_level": "advanced",
    })
    assert resp.status_code == 201


def test_register_invalid_risk_tolerance_returns_422(client, unique_email):
    resp = client.post("/api/auth/register", json={
        "email": unique_email,
        "password": "Pass123!",
        "risk_tolerance": "reckless",
    })
    assert resp.status_code == 422


def test_login_valid_credentials_returns_token(client, registered_user):
    resp = client.post("/api/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"],
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password_returns_401(client, registered_user):
    resp = client.post("/api/auth/login", json={
        "email": registered_user["email"],
        "password": "wrong-password",
    })
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


def test_login_unknown_email_returns_401(client):
    resp = client.post("/api/auth/login", json={
        "email": "ghost@nowhere.com",
        "password": "anything",
    })
    assert resp.status_code == 401


def test_me_returns_user_profile(client, registered_user, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == registered_user["email"]
    assert "id" in body
    assert "risk_tolerance" in body


def test_me_without_token_returns_401(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_bad_token_returns_401(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401
