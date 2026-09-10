"""Prueba real (no solo estructural) del backend de AWS Secrets Manager usando `moto`,
que mockea la API de AWS en memoria -- sin tocar una cuenta de AWS real ni necesitar
credenciales, pero ejerciendo el código real de boto3 contra una implementación fiel de
la API. Ver docs/design/0019-cloud-secret-backends.md."""
import json

import boto3
import pytest
from moto import mock_aws

from meridian.secrets import aws_backend
from meridian.secrets.resolver import resolve_secret_ref


@pytest.fixture
def aws_secret():
    with mock_aws():
        client = boto3.client("secretsmanager", region_name="us-east-1")
        client.create_secret(Name="meridian/test-provider", SecretString=json.dumps({"api_key": "sk-test-12345"}))
        client.create_secret(Name="meridian/plain-string", SecretString="just-a-plain-token")
        yield


def test_aws_backend_resolves_json_field(aws_secret):
    value = aws_backend.resolve("meridian/test-provider", "api_key", region_name="us-east-1")
    assert value == "sk-test-12345"


def test_aws_backend_resolves_plain_string_via_value_field(aws_secret):
    value = aws_backend.resolve("meridian/plain-string", "value", region_name="us-east-1")
    assert value == "just-a-plain-token"


def test_aws_backend_missing_field_raises(aws_secret):
    with pytest.raises(aws_backend.SecretRefError):
        aws_backend.resolve("meridian/test-provider", "does_not_exist", region_name="us-east-1")


def test_resolver_dispatches_aws_sm_prefix(aws_secret, monkeypatch):
    # El SecretRef genérico no lleva region_name -- se prueba con la región default de boto3
    # dentro del mock (moto no exige credenciales pero sí una región resoluble).
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    value = resolve_secret_ref("aws-sm:meridian/test-provider#api_key")
    assert value == "sk-test-12345"
