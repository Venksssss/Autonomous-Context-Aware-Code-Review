# Use a trusted minimal base image
FROM python:3.12-slim

# Create a non-root user and group
RUN groupadd -g 1000 sandbox && \
    useradd -u 1000 -g sandbox -s /bin/bash -m sandbox

# Install pytest and any required standard dependencies for the sandbox MVP
RUN pip install --no-cache-dir pytest==7.4.3

# Set the working directory to the mount point (workspace)
WORKDIR /workspace

# Switch to the non-root user
USER sandbox:sandbox

# Default command
CMD ["python", "-m", "pytest"]
