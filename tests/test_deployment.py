import os

from nhlgm.cli import parser


def test_web_cli_uses_render_port(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("HOST", "0.0.0.0")
    args = parser().parse_args(["web"])
    assert args.port == 10000
    assert args.host == "0.0.0.0"


def test_web_cli_has_local_fallback(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("HOST", raising=False)
    args = parser().parse_args(["web"])
    assert args.port == 8000
    assert args.host == "127.0.0.1"
