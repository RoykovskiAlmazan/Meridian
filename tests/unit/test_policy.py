import jsonschema
import pytest

from meridian.policy import DEFAULT_POLICY, requires_approval, resolve_policy, validate_policy


def test_default_policy_is_conservative():
    assert DEFAULT_POLICY["destructive"]["allowed"] is False
    assert DEFAULT_POLICY["requires_approval_intents"] == ["*"]


def test_resolve_policy_empty_returns_default():
    assert resolve_policy({}) == DEFAULT_POLICY


def test_resolve_policy_partial_merges_with_default():
    resolved = resolve_policy({"tone": "cordial"})
    assert resolved["tone"] == "cordial"
    assert resolved["destructive"] == DEFAULT_POLICY["destructive"]


def test_requires_approval_wildcard():
    assert requires_approval({"requires_approval_intents": ["*"]}, "anything.at_all") is True


def test_requires_approval_specific_intent():
    policy = {"requires_approval_intents": ["files.delete"]}
    assert requires_approval(policy, "files.delete") is True
    assert requires_approval(policy, "files.move") is False


def test_requires_approval_empty_list_means_none():
    assert requires_approval({"requires_approval_intents": []}, "files.delete") is False


def test_validate_policy_rejects_unknown_field():
    with pytest.raises(jsonschema.ValidationError):
        validate_policy({"schema_version": "1.0", "unknown_field": True})


def test_validate_policy_accepts_default():
    validate_policy(DEFAULT_POLICY)  # no exception
