import pytest
from unittest.mock import patch
import subprocess

from app.services.docker_runtime import DockerRuntime, DockerRuntimeError

class TestDockerRuntime:
    @patch("subprocess.run")
    def test_check_availability_success(self, mock_run):
        # Mock successful docker info
        mock_run.return_value.returncode = 0
        
        assert DockerRuntime.check_availability() is True
        mock_run.assert_called_once_with(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5.0
        )

    @patch("subprocess.run")
    def test_check_availability_failure(self, mock_run):
        # Mock failed docker info (daemon not running)
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Cannot connect to the Docker daemon"
        
        assert DockerRuntime.check_availability() is False

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_check_availability_not_installed(self, mock_run):
        # Mock docker CLI not installed
        assert DockerRuntime.check_availability() is False

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="docker info", timeout=5.0))
    def test_check_availability_timeout(self, mock_run):
        assert DockerRuntime.check_availability() is False
