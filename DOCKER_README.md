# Running the Sensitive Information Checker with Docker

## Prerequisites
- Docker installed on your Mac
- Docker Compose installed (usually comes with Docker Desktop)

## Quick Start

### 1. Build and Run the Service
```bash
docker-compose up --build
```

This will:
- Build the Docker image
- Start the gRPC service on port 50051
- Mount local directories for logs, config, and data

### 2. Run in Background (Detached Mode)
```bash
docker-compose up -d --build
```

### 3. View Logs
```bash
docker-compose logs -f info-checker-service
```

### 4. Stop the Service
```bash
docker-compose down
```

## Testing the Service

### Option 1: Run the Example Client
```bash
docker-compose --profile testing up info-checker-client
```

### Option 2: Use Python Client Directly
Once the service is running, you can use the Python client:

```bash
# Activate your virtual environment
source venv/bin/activate

# Run the client example
python examples/client_example.py

# Or run interactively
python run_client.py --interactive
```

### Option 3: Test with Custom Text
```python
from src.client import InfoCheckerClient

client = InfoCheckerClient("localhost:50051")
client.connect()

result = client.check_text("My credit card number is 4532-1234-5678-9012")
print(result)

client.disconnect()
```

## Service Endpoints

The gRPC service exposes these endpoints:
- `CheckText` - Check a single text for sensitive content
- `CheckBatch` - Batch check multiple texts
- `HealthCheck` - Check service health

## Configuration

- **Port**: 50051 (mapped to host)
- **Logs**: Stored in `./logs` directory
- **Config**: Business rules in `./config` directory
- **Data**: Models and data in `./data` directory

## Troubleshooting

### Check if service is running:
```bash
docker-compose ps
```

### Check service health:
```bash
docker-compose exec info-checker-service python -c "
from src.client import InfoCheckerClient
client = InfoCheckerClient('localhost:50051')
client.connect()
print(client.health_check())
"
```

### Rebuild after code changes:
```bash
docker-compose down
docker-compose up --build
``` 