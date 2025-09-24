# Use an official Python runtime as a parent image
FROM python:3.12-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for spacy
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     curl \
#     && rm -rf /var/lib/apt/lists/*

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Generate protobuf files (if not already generated)
# RUN python -m grpc_tools.protoc -I./protos --python_out=./src --grpc_python_out=./src ./protos/info_checker.proto

# Expose the port that the gRPC server will listen on
EXPOSE 50051

# Run the command to start the gRPC server
CMD ["python", "run_server.py"] 