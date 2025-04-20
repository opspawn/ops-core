# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install dependencies
# Using RUN pip install --no-cache-dir instead of copying requirements.txt
# as this agent has minimal, fixed dependencies.
RUN pip install --no-cache-dir fastapi uvicorn httpx

# Copy the current directory contents into the container at /app
COPY main.py .

# Make port 8080 available to the world outside this container
# This should match AGENT_PORT in main.py if not overridden by env var
EXPOSE 8080

# Define environment variable for the default port (can be overridden)
ENV AGENT_PORT=8080

# Run main.py when the container launches
# Use the PORT environment variable if set, otherwise default to 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${AGENT_PORT}"]