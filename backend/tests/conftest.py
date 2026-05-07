"""Ensure async engine picks test-friendly pooling before importing the app."""

import os


def pytest_configure(config) -> None:  # noqa: ARG001
    os.environ["OCEAN_READ_TEST_NULL_POOL"] = "1"
