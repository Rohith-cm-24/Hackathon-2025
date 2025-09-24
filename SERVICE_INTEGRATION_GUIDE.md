# Service Integration Guide

## 🚀 Running the Service

### 1. **Start with Docker Compose**
```bash
# Start the main service
docker-compose up -d

# Check service status
docker-compose ps
docker-compose logs info-checker-service
```

### 2. **Multi-Service Setup**
```bash
# Run with example client services
docker-compose -f docker-compose.multi-service.yml up info-checker-service example-client-service

# Run with web API
docker-compose -f docker-compose.multi-service.yml up info-checker-service web-api-service
```

## 🔌 How Other Services Can Call This Service

### **Method 1: Direct gRPC Client (Python)**

```python
import grpc
import info_checker_pb2
import info_checker_pb2_grpc

# Connect to service
channel = grpc.insecure_channel('localhost:50051')
stub = info_checker_pb2_grpc.InfoCheckerStub(channel)

# Check single text
request = info_checker_pb2.CheckRequest(
    text="My credit card number is 4532-1234-5678-9012",
    similarity_threshold=0.8
)
response = stub.CheckText(request)

print(f"Sensitive: {response.is_sensitive}")
print(f"Risk Level: {response.overall_risk_level}")
print(f"Matches: {len(response.matches)}")

# Batch check
batch_request = info_checker_pb2.BatchCheckRequest(
    requests=[
        info_checker_pb2.CheckRequest(text="Hello world"),
        info_checker_pb2.CheckRequest(text="SSN: 123-45-6789")
    ]
)
batch_response = stub.CheckBatch(batch_request)

channel.close()
```

### **Method 2: REST API (Any Language)**

If you run the web API service, you can use HTTP requests:

```bash
# Start the web API
docker-compose -f docker-compose.multi-service.yml up info-checker-service web-api-service
```

**Check Single Text:**
```bash
curl -X POST http://localhost:8080/check \
  -H "Content-Type: application/json" \
  -d '{
    "text": "My credit card is 4532-1234-5678-9012",
    "threshold": 0.8
  }'
```

**Batch Check:**
```bash
curl -X POST http://localhost:8080/check/batch \
  -H "Content-Type: application/json" \
  -d '{
    "texts": [
      "Hello world",
      "SSN: 123-45-6789",
      "Company revenue is $5.2M"
    ],
    "threshold": 0.7
  }'
```

**Health Check:**
```bash
curl http://localhost:8080/health
```

### **Method 3: Docker Network Communication**

When services run in the same Docker network:

```yaml
# docker-compose.yml
version: '3.8'
services:
  your-service:
    image: your-app
    environment:
      - INFO_CHECKER_HOST=info-checker-service:50051
    depends_on:
      - info-checker-service
    networks:
      - app-network

  info-checker-service:
    # ... (as defined in our compose file)
    networks:
      - app-network

networks:
  app-network:
```

```python
# In your service code
import os
INFO_CHECKER_HOST = os.getenv('INFO_CHECKER_HOST', 'localhost:50051')
channel = grpc.insecure_channel(INFO_CHECKER_HOST)
```

## 🎯 Integration Patterns

### **1. Chat/Messaging Service**
```python
class ChatService:
    def send_message(self, user_id: str, message: str):
        # Check message before storing/broadcasting
        result = info_checker.check_text(message)
        
        if result['is_sensitive']:
            # Block or flag the message
            return {"status": "blocked", "reason": result['risk_level']}
        
        # Proceed with normal flow
        return self.store_message(user_id, message)
```

### **2. Document Upload Service**
```python
class DocumentService:
    def upload_document(self, file_content: str, filename: str):
        # Batch check document sections
        sections = self.split_document(file_content)
        results = info_checker.check_batch(sections)
        
        sensitive_sections = [r for r in results if r['is_sensitive']]
        
        if sensitive_sections:
            # Quarantine or request approval
            return self.quarantine_document(filename, sensitive_sections)
        
        return self.store_document(filename, file_content)
```

### **3. API Gateway/Middleware**
```python
from flask import Flask, request, jsonify

def check_request_content():
    """Middleware to check API request content"""
    if request.is_json:
        content = str(request.get_json())
        result = info_checker.check_text(content)
        
        if result['is_sensitive'] and result['risk_level'] in ['HIGH', 'MEDIUM']:
            return jsonify({"error": "Content blocked"}), 403
    
    return None  # Continue processing
```

### **4. Background Job/Queue Consumer**
```python
import pika  # RabbitMQ example

def process_message(ch, method, properties, body):
    message = body.decode('utf-8')
    
    # Check content before processing
    result = info_checker.check_text(message)
    
    if result['is_sensitive']:
        # Log incident and move to DLQ
        logger.warning(f"Sensitive content in queue: {result['risk_level']}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return
    
    # Process normally
    process_business_logic(message)
    ch.basic_ack(delivery_tag=method.delivery_tag)
```

## 🌐 Language-Specific Examples

### **JavaScript/Node.js**
```javascript
const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');

const packageDefinition = protoLoader.loadSync('protos/info_checker.proto');
const infoChecker = grpc.loadPackageDefinition(packageDefinition).info_checker;

const client = new infoChecker.InfoChecker('localhost:50051', 
    grpc.credentials.createInsecure());

// Check text
const request = { 
    text: 'My SSN is 123-45-6789',
    similarity_threshold: 0.8 
};

client.CheckText(request, (error, response) => {
    if (error) {
        console.error('Error:', error);
        return;
    }
    
    console.log('Sensitive:', response.is_sensitive);
    console.log('Risk Level:', response.overall_risk_level);
});
```

### **Go**
```go
package main

import (
    "context"
    "log"
    
    "google.golang.org/grpc"
    pb "path/to/your/generated/protobuf"
)

func main() {
    conn, err := grpc.Dial("localhost:50051", grpc.WithInsecure())
    if err != nil {
        log.Fatal(err)
    }
    defer conn.Close()
    
    client := pb.NewInfoCheckerClient(conn)
    
    req := &pb.CheckRequest{
        Text: "My credit card is 4532-1234-5678-9012",
        SimilarityThreshold: 0.8,
    }
    
    resp, err := client.CheckText(context.Background(), req)
    if err != nil {
        log.Fatal(err)
    }
    
    log.Printf("Sensitive: %v, Risk: %s", resp.IsSensitive, resp.OverallRiskLevel)
}
```

### **Java**
```java
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;

public class InfoCheckerClient {
    public static void main(String[] args) {
        ManagedChannel channel = ManagedChannelBuilder
            .forAddress("localhost", 50051)
            .usePlaintext()
            .build();
            
        InfoCheckerGrpc.InfoCheckerBlockingStub stub = 
            InfoCheckerGrpc.newBlockingStub(channel);
            
        CheckRequest request = CheckRequest.newBuilder()
            .setText("My SSN is 123-45-6789")
            .setSimilarityThreshold(0.8)
            .build();
            
        CheckResponse response = stub.checkText(request);
        
        System.out.println("Sensitive: " + response.getIsSensitive());
        System.out.println("Risk Level: " + response.getOverallRiskLevel());
        
        channel.shutdown();
    }
}
```

## 🔧 Configuration Options

### **Service Discovery**
```python
# Using environment variables
INFO_CHECKER_HOST = os.getenv('INFO_CHECKER_HOST', 'localhost:50051')

# Using service discovery (Consul, etcd, etc.)
def get_service_endpoint():
    return consul_client.health.service('info-checker-service')[1][0]['Service']['Address']
```

### **Connection Pooling**
```python
class InfoCheckerPool:
    def __init__(self, host: str, pool_size: int = 5):
        self.host = host
        self.pool = []
        for _ in range(pool_size):
            channel = grpc.insecure_channel(host)
            stub = info_checker_pb2_grpc.InfoCheckerStub(channel)
            self.pool.append((channel, stub))
    
    def get_client(self):
        return self.pool[hash(threading.current_thread()) % len(self.pool)][1]
```

### **Retry Logic**
```python
import grpc
from grpc import RpcError

def check_text_with_retry(text: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return stub.CheckText(request)
        except RpcError as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

## 📊 Monitoring & Observability

### **Health Checks**
```python
def health_check():
    try:
        request = info_checker_pb2.HealthCheckRequest(service="info_checker")
        response = stub.HealthCheck(request)
        return response.status == info_checker_pb2.HealthCheckResponse.SERVING
    except:
        return False
```

### **Metrics Collection**
```python
import time
import logging

def check_text_with_metrics(text: str):
    start_time = time.time()
    
    try:
        result = stub.CheckText(request)
        
        # Log metrics
        processing_time = time.time() - start_time
        logging.info(f"InfoChecker: processed in {processing_time:.3f}s, "
                    f"sensitive={result.is_sensitive}, risk={result.overall_risk_level}")
        
        return result
    except Exception as e:
        logging.error(f"InfoChecker error: {e}")
        raise
```

## 🚀 Quick Start Commands

```bash
# 1. Start the service
docker-compose up -d

# 2. Test with Python client
source venv/bin/activate
python examples/other_service_example.py

# 3. Test with REST API
docker-compose -f docker-compose.multi-service.yml up web-api-service
curl -X POST http://localhost:8080/check -H "Content-Type: application/json" -d '{"text":"test message"}'

# 4. Check service health
curl http://localhost:8080/health

# 5. View logs
docker-compose logs -f info-checker-service
```

This service is now ready for integration with any application that needs to detect sensitive information! 