import logging
from typing import Optional
from app.schemas.test_run import TestDiscoveryResult, TestExecutionResult, TestExecutionRequest
from app.services.test_discovery import TestDiscoveryService, TestDiscoveryError
from app.services.test_executor import TestExecutorService, TestExecutionError, TestTimeoutError
from app.services.docker_sandbox import DockerSandboxExecutor, DockerSandboxError
from app.services.docker_runtime import DockerRuntime
from app.config import settings

logger = logging.getLogger(__name__)

class TestService:
    def __init__(self):
        self.discovery_service = TestDiscoveryService()
        self.local_executor = TestExecutorService()
        self.docker_executor = DockerSandboxExecutor()

    def discover_tests(self, repository_path: str) -> TestDiscoveryResult:
        logger.info(f"test_discovery_started: {repository_path}")
        try:
            result = self.discovery_service.discover_tests(repository_path)
            logger.info(f"test_discovery_completed: found {result.test_count} tests")
            return result
        except TestDiscoveryError as e:
            logger.error(f"test_discovery_failed: {str(e)}")
            raise

    def execute_tests(self, request: TestExecutionRequest) -> TestExecutionResult:
        logger.info(f"test_execution_started: mode={request.execution_mode} repo={request.repository_path} target={request.test_path}")
        try:
            if request.execution_mode == "docker":
                if not settings.docker_sandbox_enabled:
                    raise DockerSandboxError("DOCKER_SANDBOX_DISABLED")
                if not DockerRuntime.check_availability():
                    raise DockerSandboxError("DOCKER_UNAVAILABLE")
                result = self.docker_executor.execute_tests(request)
            else:
                result = self.local_executor.execute_tests(request)
                
            if result.status == "timeout":
                logger.warning("test_execution_timeout")
            elif result.status == "error":
                logger.error("test_execution_failed")
            else:
                logger.info(f"test_execution_completed: status={result.status} exit_code={result.exit_code}")
            return result
        except TestExecutionError as e:
            logger.error(f"test_execution_failed: {str(e)}")
            raise
        except DockerSandboxError as e:
            logger.error(f"sandbox_failed: {str(e)}")
            raise TestExecutionError(str(e))
