import os
import uuid
import time
import subprocess
import logging
from pathlib import Path
from typing import Optional, List

from app.config import settings
from app.schemas.test_run import TestExecutionRequest, TestExecutionResult, TestStatus
from app.services.test_executor import PytestSummaryParser

logger = logging.getLogger(__name__)

class DockerSandboxError(Exception):
    pass

class DockerSandboxExecutor:
    def __init__(self):
        self.image = settings.docker_image
        self.cpu_limit = settings.docker_cpu_limit
        self.memory_limit = settings.docker_memory_limit
        self.pids_limit = settings.docker_pids_limit
        self.timeout = settings.docker_timeout_seconds
        self.max_output = settings.docker_output_limit

    def execute_tests(self, request: TestExecutionRequest) -> TestExecutionResult:
        repo_path = Path(request.repository_path).resolve()
        
        if not repo_path.exists() or not repo_path.is_dir():
            raise DockerSandboxError("TEST_TARGET_INVALID")
            
        target = "."
        if request.test_path:
            target_path = (repo_path / request.test_path).resolve()
            if not str(target_path).startswith(str(repo_path)):
                raise DockerSandboxError("TEST_TARGET_OUTSIDE_REPOSITORY")
            if not target_path.exists():
                raise DockerSandboxError("TEST_TARGET_INVALID")
            # Convert to container-relative path
            target = request.test_path

        container_name = f"sandbox_{uuid.uuid4().hex[:12]}"
        
        # We mount the repository as read-only.
        # We don't mount a separate writable dir by default unless pytest complains.
        # Often `pytest` can run from a read-only directory if `__pycache__` write failures are ignored,
        # but to be completely safe, we can mount a tmpfs to /tmp and set pytest cache there.
        
        docker_cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--network", "none",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges=true",
            "--cpus", str(self.cpu_limit),
            "--memory", self.memory_limit,
            "--pids-limit", str(self.pids_limit),
            # Mount the repository as read-only to /workspace
            "-v", f"{str(repo_path)}:/workspace:ro",
            # Provide an ephemeral writable tmpfs for caches and temp files
            "--tmpfs", "/tmp:exec,mode=1777",
            "-w", "/workspace",
            # We don't force a non-root user via -u here because the base python image runs as root,
            # but we could. For MVP, relying on standard python images. We'll add -u 1000:1000.
            "-u", "1000:1000",
            self.image,
            "python", "-m", "pytest",
            # Tell pytest to use the writable /tmp for its cache
            "-o", "cache_dir=/tmp/.pytest_cache",
            target
        ]

        logger.info(f"sandbox_started: container={container_name} target={target}")
        start_time = time.time()
        
        stdout_data = ""
        stderr_data = ""
        exit_code = None
        status: TestStatus = "unknown"
        
        try:
            process = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            stdout_data = process.stdout
            stderr_data = process.stderr
            exit_code = process.returncode
            
            # 125 means docker run itself failed (e.g., image not found, invalid args)
            # 126 means command cannot be invoked
            # 127 means command not found
            if exit_code == 125:
                if "Unable to find image" in stderr_data:
                    raise DockerSandboxError("DOCKER_IMAGE_NOT_AVAILABLE")
                raise DockerSandboxError(f"DOCKER_SANDBOX_START_FAILED: {stderr_data}")
                
            if exit_code == 0:
                status = "passed"
            elif exit_code == 1:
                status = "failed"
            elif exit_code == 5:
                status = "passed"
            else:
                status = "error"
                
        except subprocess.TimeoutExpired as e:
            status = "timeout"
            if e.stdout:
                stdout_data = e.stdout.decode(errors='replace') if isinstance(e.stdout, bytes) else e.stdout
            if e.stderr:
                stderr_data = e.stderr.decode(errors='replace') if isinstance(e.stderr, bytes) else e.stderr
            
            stdout_data += f"\n\n[Container terminated after {self.timeout}s timeout]"
            logger.warning(f"sandbox_timeout: container={container_name}")
            
            # Explicitly kill the container since subprocess timeout doesn't always kill Docker cleanly
            try:
                subprocess.run(["docker", "kill", container_name], capture_output=True, timeout=5.0)
            except Exception:
                pass
                
        except DockerSandboxError:
            raise
        except Exception as e:
            status = "error"
            stderr_data = str(e)
            logger.error(f"sandbox_failed: {str(e)}")
            
        duration = time.time() - start_time
        
        output_truncated = False
        if len(stdout_data) > self.max_output:
            stdout_data = stdout_data[:self.max_output] + "\n\n...[STDOUT TRUNCATED]..."
            output_truncated = True
            
        if len(stderr_data) > self.max_output:
            stderr_data = stderr_data[:self.max_output] + "\n\n...[STDERR TRUNCATED]..."
            output_truncated = True
            
        summary = PytestSummaryParser.parse_summary(stdout_data)
        
        if summary["tests_failed"] and summary["tests_failed"] > 0 and status == "passed":
            status = "failed"
            
        logger.info(f"sandbox_completed: container={container_name} status={status}")
        
        return TestExecutionResult(
            framework="pytest",
            execution_mode="docker",
            sandboxed=True,
            status=status,
            exit_code=exit_code,
            duration_seconds=duration,
            stdout=stdout_data,
            stderr=stderr_data,
            tests_run=summary["tests_run"],
            tests_passed=summary["tests_passed"],
            tests_failed=summary["tests_failed"],
            tests_skipped=summary["tests_skipped"],
            tests_errors=summary["tests_errors"],
            output_truncated=output_truncated
        )
