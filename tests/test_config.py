"""
Test timeout configuration in config.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from torvalds_skill import config


def test_read_timeout_default():
    """READ_TIMEOUT defaults to 120 seconds"""
    assert config.READ_TIMEOUT == 120


def test_wall_clock_glm_default():
    """WALL_CLOCK_GLM defaults to 1800 seconds (30 minutes)"""
    assert config.WALL_CLOCK_GLM == 1800


def test_wall_clock_long_default():
    """WALL_CLOCK_LONG defaults to 900 seconds (15 minutes)"""
    assert config.WALL_CLOCK_LONG == 900


def test_wall_clock_default_default():
    """WALL_CLOCK_DEFAULT defaults to 300 seconds (5 minutes)"""
    assert config.WALL_CLOCK_DEFAULT == 300


def test_request_timeout_unchanged():
    """REQUEST_TIMEOUT still defaults to 60 seconds"""
    assert config.REQUEST_TIMEOUT == 60


if __name__ == "__main__":
    test_read_timeout_default()
    test_wall_clock_glm_default()
    test_wall_clock_long_default()
    test_wall_clock_default_default()
    test_request_timeout_unchanged()
    print("All timeout config tests passed!")