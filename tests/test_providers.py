import pytest

from autonomousdev.providers import HttpJsonProvider, ProviderError


def test_json_fence_is_parsed() -> None:
    assert HttpJsonProvider._parse_object('```json\n{"ok": true}\n```') == {"ok": True}


def test_non_object_provider_response_is_rejected() -> None:
    with pytest.raises(ProviderError):
        HttpJsonProvider._parse_object("[]")
