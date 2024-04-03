#!/usr/bin/env python

"""Tests for `daylight_timelapser` package."""


import unittest
from click.testing import CliRunner

from daylight_timelapser import daylight_timelapser


class TestDaylight_timelapser(unittest.TestCase):
    """Tests for `daylight_timelapser` package."""

    def setUp(self):
        """Set up test fixtures, if any."""

    def tearDown(self):
        """Tear down test fixtures, if any."""

    def test_000_something(self):
        """Test something."""

    def test_command_line_interface(self):
        """Test the CLI."""
        runner = CliRunner()
        #result = runner.invoke(daylight_timelapser.main)
        #assert result.exit_code == 0
        #assert 'daylight_timelapser.cli.main' in result.output

        help_result = runner.invoke(daylight_timelapser.main, ['--help'])
        assert help_result.exit_code == 0
        assert 'Usage: main [OPTIONS]' in help_result.output
