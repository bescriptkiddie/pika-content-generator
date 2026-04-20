from types import SimpleNamespace

from core.langgraph.tools import xhs_cli_provider


class _FakeClientContext:
    def __init__(self, client):
        self._client = client

    def __enter__(self):
        return self._client

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeClient:
    def __init__(self, *, detail_result=None, detail_exc=None, publish_result=None, publish_exc=None):
        self._detail_result = detail_result
        self._detail_exc = detail_exc
        self._publish_result = publish_result
        self._publish_exc = publish_exc

    def get_note_detail(self, note_id, xsec_token=""):
        if self._detail_exc:
            raise self._detail_exc
        return self._detail_result

    def publish_note(self, title, content, image_paths):
        if self._publish_exc:
            raise self._publish_exc
        return self._publish_result


class _LoginError(Exception):
    pass


class _DataFetchError(Exception):
    pass


def _patch_load_xhs_cli(monkeypatch, *, cookie="session=ok", client=None):
    fake_client = client or _FakeClient()
    monkeypatch.setattr(
        xhs_cli_provider,
        "_load_xhs_cli",
        lambda: (
            True,
            lambda: cookie,
            lambda cookie_value: {"cookie": cookie_value},
            lambda cookie_dict: _FakeClientContext(fake_client),
            _DataFetchError,
            _LoginError,
        ),
    )


def test_fetch_note_detail_returns_verification_required(monkeypatch):
    client = _FakeClient(
        detail_exc=_LoginError(
            "QR login requires verification. verify_type=124 verify_uuid=824a93bd-7347-47e9-b54b-1a7b0a259ade"
        )
    )
    _patch_load_xhs_cli(monkeypatch, client=client)

    result = xhs_cli_provider.fetch_note_detail("note-1", xsec_token="token")

    assert result["error_code"] == "verification_required"
    assert result["verification_required"] is True
    assert result["action_required"] == "verify"
    assert result["verify_type"] == "124"
    assert result["verify_uuid"] == "824a93bd-7347-47e9-b54b-1a7b0a259ade"



def test_fetch_note_detail_returns_auth_expired(monkeypatch):
    client = _FakeClient(detail_exc=_LoginError("session expired"))
    _patch_load_xhs_cli(monkeypatch, client=client)

    result = xhs_cli_provider.fetch_note_detail("note-1")

    assert result["error_code"] == "auth_expired"
    assert result["action_required"] == "reauth"
    assert result["verification_required"] is False



def test_fetch_note_detail_returns_success(monkeypatch):
    client = _FakeClient(detail_result={"title": "detail title", "content": "body"})
    _patch_load_xhs_cli(monkeypatch, client=client)

    result = xhs_cli_provider.fetch_note_detail("note-1")

    assert result == {"title": "detail title", "content": "body"}



def test_publish_note_returns_verification_required(monkeypatch):
    client = _FakeClient(
        publish_exc=_LoginError(
            "Blocked by security verification while publishing: verify_type=124 verify_uuid=824a93bd-7347-47e9-b54b-1a7b0a259ade"
        )
    )
    _patch_load_xhs_cli(monkeypatch, client=client)

    result = xhs_cli_provider.publish_note(title="t", body="b")

    assert result["error_code"] == "verification_required"
    assert result["verification_required"] is True
    assert result["action_required"] == "verify"
    assert result["verify_type"] == "124"
    assert result["verify_uuid"] == "824a93bd-7347-47e9-b54b-1a7b0a259ade"



def test_publish_note_returns_success(monkeypatch):
    client = _FakeClient(publish_result={"status": "published", "note_id": "123"})
    _patch_load_xhs_cli(monkeypatch, client=client)

    result = xhs_cli_provider.publish_note(title="t", body="b", images=["a.png"])

    assert result == {"status": "published", "note_id": "123"}
