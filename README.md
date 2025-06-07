# CellSight 🔍

**Debug and evaluate LLM-powered agents with detailed execution tracing**

CellSight is a powerful debugging and evaluation tool designed specifically for LLM-powered agents built with LangChain. It provides comprehensive tracing, error analysis, and testing capabilities to help developers quickly identify and fix issues in their agent implementations.

## Features

### 🔍 Core Capabilities

- **Agent Execution Tracing**: Capture every step of agent execution including tool selection, API calls, and decision-making
- **Error & Failure Capture**: Automatically detect and categorize errors (timeouts, API errors, validation failures, etc.)
- **Test Harness**: Run comprehensive test suites with expected behaviors and failure scenarios
- **Replay/Debugging**: Store and replay failed runs for debugging and analysis
- **Metrics Dashboard**: Track success rates, error frequencies, and performance metrics
- **API-Agnostic**: Works with mock APIs for testing without external dependencies

### 🛠️ Built-in Tools

- **Weather API Tool**: Mock weather service with configurable failure scenarios
- **Customer Data Tool**: Mock customer database with error simulation
- **Text Summarization**: Internal tool for text processing
- **Calculator**: Mathematical expression evaluation with error handling

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/cellsight.git
cd cellsight

# Install dependencies
pip install -r requirements.txt

# Or install as a package
pip install -e .
```

## Quick Start

### 1. Start the Mock API Server

```bash
cellsight start-api
```

This starts a FastAPI server on `http://localhost:8000` with mock endpoints for testing.

### 2. Run a Single Query (CLI)

```bash
# Using mock agent (no OpenAI API needed)
cellsight run "What's the weather in London?" --mock

# With verbose output
cellsight run "Calculate 15 * 23 + 7" --mock --verbose
```

### 3. Run Test Suite

```bash
# Run default test cases
cellsight test

# Save results
cellsight test --save-results results.json
```

### 4. View Execution History

```bash
# Show recent runs
cellsight history

# View detailed trace
cellsight trace <run_id>

# Show metrics
cellsight metrics
```

### 5. Launch Web Dashboard

```bash
streamlit run cellsight/dashboard/app.py
```

Open `http://localhost:8501` to access the interactive dashboard.

## Usage Examples

### Running Tests Programmatically

```python
from cellsight.core.tracer import ExecutionTracer
from cellsight.core.test_harness import TestHarness, TestCase

# Initialize
tracer = ExecutionTracer()
harness = TestHarness(tracer, use_mock_agent=True)

# Add test cases
harness.add_test_case(TestCase(
    id="test_001",
    name="Weather Query Test",
    query="What's the weather in Paris?",
    expected_behavior="Should use weather tool",
    expected_tools=["get_weather"]
))

# Run tests
results = harness.run_all_tests()

# Get summary
summary = harness.get_summary()
print(f"Pass rate: {summary['pass_rate']:.1%}")
```

### Custom Agent Integration

```python
from cellsight.core.tracer import ExecutionTracer
from cellsight.core.agent import TracedAgent

# Create tracer
tracer = ExecutionTracer()

# Create agent with tracing
agent = TracedAgent(
    tracer=tracer,
    model_name="gpt-3.5-turbo",
    temperature=0.0,
    api_base_url="http://localhost:8000"
)

# Run with tracing
try:
    result = agent.run("Look up customer 12345")
    print(result)
except Exception as e:
    # Error is automatically traced
    print(f"Error: {e}")

# View metrics
metrics = tracer.get_metrics()
print(f"Success rate: {metrics['success_rate']:.1%}")
```

### Configuring Mock API Behavior

```bash
# Set high failure rate for testing
cellsight configure-api --failure-rate 0.5 --timeout-rate 0.2

# View current configuration
cellsight configure-api
```

## Architecture

```
cellsight/
├── core/
│   ├── tracer.py       # Execution tracing and storage
│   ├── agent.py        # LangChain agent with tracing
│   └── test_harness.py # Test execution framework
├── tools/
│   └── langchain_tools.py  # Tool implementations
├── api/
│   └── mock_api.py     # Mock API server
├── dashboard/
│   └── app.py          # Streamlit web UI
└── cli.py              # Command-line interface
```

## Key Components

### ExecutionTracer
- Captures all agent execution steps
- Stores traces in SQLite database
- Classifies and tracks errors
- Provides metrics and analytics

### TracedAgent
- LangChain agent wrapper with integrated tracing
- Supports both real and mock LLM backends
- Automatic error handling and logging

### TestHarness
- Runs test cases with expected behaviors
- Validates tool usage and outputs
- Supports failure scenario testing
- Generates detailed test reports

## Extending CellSight

### Adding New Tools

```python
from cellsight.tools.langchain_tools import TracedTool

class MyCustomTool(TracedTool):
    name = "my_tool"
    description = "My custom tool"
    
    def _execute(self, input_param: str) -> str:
        # Tool implementation
        return f"Processed: {input_param}"
```

### Custom Error Types

```python
from cellsight.core.tracer import ErrorType

# Add to error classification
if "my_error" in str(error).lower():
    return ErrorType.CUSTOM_ERROR
```

### API Integration

Replace mock API calls with real endpoints:

```python
# In langchain_tools.py
self.api_base_url = "https://real-api.example.com"
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

```bash
black cellsight/
flake8 cellsight/
```

## Troubleshooting

### Common Issues

1. **API Connection Error**
   - Ensure mock API server is running: `cellsight start-api`
   - Check port 8000 is available

2. **OpenAI API Key**
   - For real agent: Set `OPENAI_API_KEY` environment variable
   - For testing: Use `--mock` flag

3. **Database Errors**
   - Check write permissions in `cellsight/data/`
   - Delete `traces.db` to reset

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

Built with:
- LangChain for agent orchestration
- FastAPI for mock API server
- Streamlit for web dashboard
- Rich for CLI formatting 