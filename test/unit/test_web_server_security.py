from unittest.mock import patch

from web_server import Handler


class RequestStub:
    def __init__(self, authorization=""):
        self.headers = {"Authorization": authorization}


def test_tokenless_api_access_is_limited_to_loopback_development():
    request = RequestStub()
    with patch("web_server.NEXUS_API_TOKEN", ""), patch("web_server.ALLOW_UNAUTHENTICATED_LOCAL", False), patch("web_server.HOST", "127.0.0.1"):
        assert Handler._authorized(request) is False
    with patch("web_server.NEXUS_API_TOKEN", ""), patch("web_server.ALLOW_UNAUTHENTICATED_LOCAL", True), patch("web_server.HOST", "127.0.0.1"):
        assert Handler._authorized(request) is True
    with patch("web_server.NEXUS_API_TOKEN", ""), patch("web_server.ALLOW_UNAUTHENTICATED_LOCAL", True), patch("web_server.HOST", "localhost"):
        assert Handler._authorized(request) is True
    with patch("web_server.NEXUS_API_TOKEN", ""), patch("web_server.ALLOW_UNAUTHENTICATED_LOCAL", True), patch("web_server.HOST", "0.0.0.0"):
        assert Handler._authorized(request) is False


def test_configured_api_token_requires_exact_bearer_header():
    request = RequestStub("Bearer correct-token")
    with patch("web_server.NEXUS_API_TOKEN", "correct-token"), patch("web_server.HOST", "0.0.0.0"):
        assert Handler._authorized(request) is True

    wrong_token = RequestStub("Bearer wrong-token")
    with patch("web_server.NEXUS_API_TOKEN", "correct-token"), patch("web_server.HOST", "127.0.0.1"):
        assert Handler._authorized(wrong_token) is False

    missing_token = RequestStub()
    with patch("web_server.NEXUS_API_TOKEN", "correct-token"):
        assert Handler._authorized(missing_token) is False

def test_all_sensitive_post_endpoints_require_authorization():
    class PostStub:
        def __init__(self, path):
            self.path = path
            self.response = None

        def _authorized(self):
            return False

        def _json(self, status, payload):
            self.response = (status, payload)

    for path in (
        "/api/approvals/decision",
        "/api/livekit/token",
        "/api/realtime/token",
        "/api/realtime/brain",
        "/api/chat",
        "/api/chat/stream",
    ):
        request = PostStub(path)
        Handler.do_POST(request)
        assert request.response == (401, {"error": "Unauthorized"}), path
