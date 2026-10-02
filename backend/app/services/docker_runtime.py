import subprocess
import logging

logger = logging.getLogger(__name__)

class DockerRuntimeError(Exception):
    pass

class DockerRuntime:
    @staticmethod
    def check_availability() -> bool:
        """
        Detects whether Docker is available and the daemon is reachable.
        """
        try:
            # We use 'docker info' as it verifies both the CLI and daemon connection
            process = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5.0
            )
            if process.returncode == 0:
                return True
            else:
                logger.warning(f"Docker daemon returned non-zero exit code. Stderr: {process.stderr}")
                return False
        except FileNotFoundError:
            logger.warning("Docker CLI executable not found.")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("Docker info command timed out.")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking Docker availability: {str(e)}")
            return False
