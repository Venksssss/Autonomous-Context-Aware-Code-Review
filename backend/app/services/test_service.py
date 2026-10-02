import logging
from typing import Optional
from app.schemas.test_run import TestDiscoveryResult, TestExecutionResult, TestExecutionRequest
from app.services.test_discovery import TestDiscoveryService, TestDiscoveryError
from app.services.test_executor import TestExecutorService, TestExecutionError, TestTimeoutError

logger = logging.getLogger(__name__)

class TestService:
    def __init__(self):
        self.discovery_service = TestDiscoveryService()
        self.executor_service = TestExecutorService()

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
        logger.info(f"test_execution_started: {request.repository_path} target={request.test_path}")
        try:
            result = self.executor_service.execute_tests(request)
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
