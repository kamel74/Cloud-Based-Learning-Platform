"""
Unit tests for Quiz Service
"""
import pytest


def test_basic():
    """Basic test to ensure testing works"""
    assert True


def test_flask_import():
    """Test Flask can be imported"""
    from flask import Flask
    app = Flask(__name__)
    assert app is not None
