"""Tests for the desktop update checker (phase 5).

The network is stubbed, so these are deterministic and offline-safe.
"""

from desktop import updates


def test_parse_version_strips_prefix_and_text():
    assert updates.parse_version("v3.2.10") == (3, 2, 10)
    assert updates.parse_version("3.1.1") == (3, 1, 1)
    assert updates.parse_version("") == (0,)


def test_is_newer_handles_uneven_lengths():
    assert updates.is_newer("3.2.0", "3.1.1") is True
    assert updates.is_newer("v3.1.2", "3.1.1") is True
    assert updates.is_newer("3.1.1", "3.1.1") is False
    assert updates.is_newer("3.1.0", "3.1.1") is False
    assert updates.is_newer("3.2", "3.1.9") is True       # (3,2) > (3,1,9)


def test_check_for_update_returns_info_when_newer(monkeypatch):
    monkeypatch.setattr(updates, "fetch_latest_release", lambda timeout=4.0: {
        "tag_name": "v9.9.9",
        "html_url": "https://github.com/phindagijimana/BIDSHub/releases/tag/v9.9.9",
        "name": "BIDSHub 9.9.9",
    })
    info = updates.check_for_update(current="3.1.1")
    assert info is not None
    assert info["version"] == "v9.9.9"
    assert "9.9.9" in info["url"]


def test_check_for_update_none_when_current_is_latest(monkeypatch):
    monkeypatch.setattr(updates, "fetch_latest_release", lambda timeout=4.0: {
        "tag_name": "v3.1.1", "html_url": "x", "name": "y",
    })
    assert updates.check_for_update(current="3.1.1") is None


def test_check_for_update_none_when_offline(monkeypatch):
    monkeypatch.setattr(updates, "fetch_latest_release", lambda timeout=4.0: None)
    assert updates.check_for_update(current="3.1.1") is None
