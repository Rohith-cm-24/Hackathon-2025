# Real-Time Sensitive Information Checker with gRPC and Local AI

A high-performance, low-latency service for detecting sensitive or confidential content in text using gRPC and local AI models. This system combines explicit pattern detection with semantic analysis to provide comprehensive content screening in real-time.

## 🌟 Features

- **Multi-tiered Detection Pipeline**
  - Explicit content detection (keywords, regex patterns, PII)
  - Semantic analysis using sentence transformers
  - Named entity recognition with spaCy
  - PII detection with Microsoft Presidio

- **High Performance**
  - Low-latency processing (typically <100ms per text)
  - Multi-threaded gRPC server for concurrent requests
  - Local AI models (no external API calls)
  - Efficient sentence embedding caching

- **Configurable Business Rules**
  - Customizable sensitivity categories
  - JSON-based rule configuration
  - Dynamic rule loading and updates
  - Confidence-based risk scoring

- **Production Ready**
  - Comprehensive error handling
  - Health check endpoints
  - Structured logging
  - Batch processing support

## 🏗️ Architecture

```
┌─────────────────┐    gRPC     ┌─────────────────┐
│                 │ ◄────────── │                 │
│  gRPC Client    │             │  gRPC Server    │
│                 │ ──────────► │                 │
└─────────────────┘             └─────────────────┘
                                         │
                                         ▼
                                ┌─────────────────┐
                                │ Detection       │
                                │ Pipeline        │
                                └─────────────────┘
                                         │
                         ┌───────────────┼───────────────┐
                         ▼               ▼               ▼
                ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
                │ Explicit    │ │ Semantic    │ │ PII         │
                │ Detection   │ │ Analysis    │ │ Detection   │
                │             │ │             │ │             │
                │ • Keywords  │ │ • Sentence  │ │ • Presidio  │
                │ • Regex     │ │   Transformers │ • spaCy NER │
                │ • Patterns  │ │ • Business  │ │ • Custom    │
                │             │ │   Rules     │ │   Patterns  │
                └─────────────┘ └─────────────┘ └─────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Virtual environment (recommended)

### Installation

1. **Clone and setup the project:**
```bash
cd Hackathon
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Download required models:**
```bash
# Download spaCy English model
python -m spacy download en_core_web_sm
```

### Running the Server

1. **Start the gRPC server:**
```bash
# Using the example script
python examples/server_example.py

# Or directly
python -m src.info_checker_service
```

The server will start on `localhost:50051` by default.

2. **Verify server is running:**
```bash
# Health check
python -m src.client --health
```

### Testing the Client

1. **Run example tests:**
```bash
python examples/client_example.py
```

2. **Interactive mode:**
```bash
python examples/client_example.py --interactive
```

3. **Command-line usage:**
```bash
# Check specific text
python -m src.client --text "My salary is $75,000 per year"

# Check file content
python -m src.client --file sample.txt

# Interactive mode
python -m src.client --interactive
```

## 📋 Usage Examples

### Basic Text Checking

```python
from src.client import InfoCheckerClient

client = InfoCheckerClient("localhost:50051")
client.connect()

# Check sensitive content
result = client.check_text("My credit card number is 4532-1234-5678-9012")

print(f"Sensitive: {result['is_sensitive']}")
print(f"Risk Level: {result['overall_risk_level']}")
print(f"Matches: {len(result['matches'])}")

client.disconnect()
```

### Batch Processing

```python
texts = [
    "Regular business email content",
    "Our quarterly revenue was $2.5M",
    "Planning layoffs next month"
]

results = client.check_batch(texts)
for i, result in enumerate(results):
    print(f"Text {i+1}: {'SENSITIVE' if result['is_sensitive'] else 'SAFE'}")
```

### Custom Configuration

```python
# Custom similarity threshold
result = client.check_text(
    "Discussing employee performance", 
    similarity_threshold=0.8
)

# Custom business rules (server-side configuration)
from src.semantic_analyzer import BusinessRule

custom_rule = BusinessRule(
    name="project_codenames",
    description="Internal project codenames and development names",
    examples=[
        "Project Phoenix launch date",
        "Operation Blue Sky status",
        "Alpha release candidate"
    ],
    category="business",
    severity="MEDIUM"
)
```

## 🔧 Configuration

### Business Rules

Edit `config/business_rules.json` to customize detection rules:

```json
{
  "name": "custom_rule",
  "description": "Description of what this rule detects",
  "examples": [
    "Example sensitive text 1",
    "Example sensitive text 2"
  ],
  "category": "business|financial|hr|legal|technical",
  "severity": "LOW|MEDIUM|HIGH"
}
```

### Server Configuration

Key configuration options in `src/info_checker_service.py`:

```python
# Server settings
PORT = 50051
MAX_WORKERS = 10
SIMILARITY_THRESHOLD = 0.7

# Model settings
SENTENCE_TRANSFORMER_MODEL = "all-MiniLM-L6-v2"
SPACY_MODEL = "en_core_web_sm"
```

## 🎯 Detection Categories

### Explicit Detection

1. **Keywords**: Financial terms, confidential markers, etc.
2. **Regex Patterns**: Credit cards, SSNs, phone numbers, emails
3. **PII Detection**: Using Microsoft Presidio
4. **Named Entities**: Using spaCy NER

### Semantic Analysis

1. **Business Rules**: Configurable semantic matching
2. **Sentence Transformers**: Context-aware similarity
3. **Risk Scoring**: Weighted confidence calculation
4. **Category Classification**: Automatic content categorization

## 📊 Performance

### Benchmarks

- **Single text check**: ~50-100ms (typical)
- **Batch processing**: ~30-60ms per text
- **Memory usage**: ~500MB-1GB (model loading)
- **Throughput**: ~100-200 requests/second

### Optimization Tips

1. **Use batch processing** for multiple texts
2. **Adjust similarity thresholds** based on use case
3. **Configure max_workers** based on CPU cores
4. **Cache frequently checked patterns**

## 🛡️ Security Considerations

- **Local Processing**: All analysis happens on-device
- **No External APIs**: No data leaves your infrastructure
- **Memory Management**: Models loaded once, reused
- **Input Validation**: Comprehensive request validation

## 🔍 API Reference

### gRPC Service Methods

#### CheckText
```protobuf
rpc CheckText(CheckRequest) returns (CheckResponse);
```
Check a single text for sensitive content.

#### CheckBatch
```protobuf
rpc CheckBatch(BatchCheckRequest) returns (BatchCheckResponse);
```
Check multiple texts in batch.

#### HealthCheck
```protobuf
rpc HealthCheck(HealthCheckRequest) returns (HealthCheckResponse);
```
Check service health and availability.

### Response Format

```json
{
  "is_sensitive": true,
  "overall_risk_level": "HIGH",
  "confidence_score": 0.85,
  "matches": [
    {
      "match_type": "SEMANTIC",
      "rule_name": "salary_information",
      "matched_text": "salary increase to $85,000",
      "confidence": 0.92,
      "start_position": 12,
      "end_position": 38,
      "explanation": "Detected salary-related information"
    }
  ]
}
```

## 🧪 Testing

### Running Tests

```bash
# Run example tests
python examples/client_example.py

# Health check
python -m src.client --health

# Interactive testing
python -m src.client --interactive
```

### Test Cases

The system includes comprehensive test cases covering:

- Non-sensitive content (baseline)
- PII detection (credit cards, SSNs)
- Financial information (salaries, revenue)
- HR information (layoffs, performance)
- Business intelligence (clients, deals)
- Legal matters (lawsuits, compliance)
- Technical security (vulnerabilities)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

### Common Issues

1. **Model loading errors**: Ensure spaCy model is installed
2. **Connection refused**: Verify server is running on correct port
3. **Memory issues**: Reduce max_workers or use lighter models
4. **Slow performance**: Check CPU usage and adjust thresholds

### Getting Help

- Check the examples in the `examples/` directory
- Review the configuration in `config/`
- Enable verbose logging with `--verbose` flag

## 🔮 Roadmap

- [ ] Support for additional languages
- [ ] Custom model fine-tuning
- [ ] Real-time streaming analysis
- [ ] Web dashboard for monitoring
- [ ] Docker containerization
- [ ] Kubernetes deployment configs # Hackathon-Keycode
