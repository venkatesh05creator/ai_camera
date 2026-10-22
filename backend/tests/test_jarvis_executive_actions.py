"""Tests for Holographic HUD endpoints and JARVIS executive actions."""

import pytest
from fastapi import status


def test_hud_page_served_correctly(client):
    """GET /hud must return HTTP 200 with Holographic HUD HTML."""
    response = client.get("/hud")
    assert response.status_code == status.HTTP_200_OK
    assert "text/html" in response.headers.get("content-type", "")
    assert "Holographic HUD" in response.text
    assert "reactor" in response.text or "canvas" in response.text


def test_hud_state_telemetry(client):
    """GET /api/state and GET /api/hud/state must return live telemetry."""
    for path in ["/api/state", "/api/hud/state", "/api/v1/hud/state"]:
        response = client.get(path)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "sys" in data
        assert "cpu" in data["sys"]
        assert "ram" in data["sys"]
        assert "stocks" in data
        assert isinstance(data["stocks"], list)
        assert "mic" in data
        assert "chat" in data
        assert "cards" in data


def test_whatsapp_executive_action(client, admin_headers):
    """'OK. Can you open WhatsApp?' must execute WhatsApp Web action, not fall through to Wikipedia."""
    payload = {
        "query": "OK. Can you open WhatsApp?",
        "speak": True,
    }
    response = client.post("/api/v1/ai/camera-interact", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["action"] == "open_url"
    assert "whatsapp.com" in data["action_payload"].get("url", "")
    assert "WhatsApp" in data["answer"]
    assert "Duolicious" not in data["answer"]
    assert "Wikipedia" not in data["answer"]


def test_youtube_executive_action(client, admin_headers):
    """'Play lofi music on YouTube' must return open_url with YouTube search query."""
    payload = {
        "query": "Play lofi music on YouTube",
        "speak": True,
    }
    response = client.post("/api/v1/ai/camera-interact", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["action"] == "open_url"
    assert "youtube.com" in data["action_payload"].get("url", "")
    assert "lofi" in data["action_payload"].get("url", "").lower() or "lofi" in data["answer"].lower()


def test_app_launch_executive_action(client, admin_headers):
    """'Open VS Code' must trigger app launcher action."""
    payload = {
        "query": "Open VS Code",
        "speak": True,
    }
    response = client.post("/api/v1/ai/camera-interact", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["action"] in ["app_launch", "open_url"]
    assert "VS Code" in data["answer"] or "code" in data["answer"].lower()


def test_stock_market_executive_action(client, admin_headers):
    """'Stock market report' must trigger market briefing with financial intelligence."""
    payload = {
        "query": "Stock market report",
        "speak": True,
    }
    response = client.post("/api/v1/ai/camera-interact", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["action"] == "market_briefing"
    assert "Market" in data["answer"] or "Price" in data["answer"] or "trading" in data["speech_text"]


def test_time_inquiry_executive_action(client, admin_headers):
    """'What time is it' must return formatted time."""
    payload = {
        "query": "What time is it",
        "speak": True,
    }
    response = client.post("/api/v1/ai/camera-interact", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "current time is" in data["speech_text"].lower() or "time" in data["answer"].lower()
