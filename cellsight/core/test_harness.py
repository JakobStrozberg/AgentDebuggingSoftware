"""
Test harness for running test cases through the agent and evaluating results.
"""

import json
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import traceback

from cellsight.core.tracer import ExecutionTracer
from cellsight.core.agent import create_agent


@dataclass
class TestCase:
    """Represents a single test case"""
    id: str
    name: str
    query: str
    expected_behavior: str
    expected_tools: Optional[List[str]] = None
    expected_error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TestResult:
    """Result of running a test case"""
    test_id: str
    run_id: str
    status: str  # passed, failed, error
    actual_output: Optional[str] = None
    actual_error: Optional[str] = None
    tools_used: Optional[List[str]] = None
    duration_ms: Optional[float] = None
    failure_reason: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.timestamp:
            data['timestamp'] = self.timestamp.isoformat()
        return data


class TestHarness:
    """Harness for running test cases against the agent"""
    
    def __init__(self, tracer: ExecutionTracer, use_mock_agent: bool = True):
        self.tracer = tracer
        self.use_mock_agent = use_mock_agent
        self.test_cases: List[TestCase] = []
        self.results: List[TestResult] = []
    
    def add_test_case(self, test_case: TestCase):
        """Add a test case to the harness"""
        self.test_cases.append(test_case)
    
    def load_test_cases(self, file_path: str):
        """Load test cases from a JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        for case_data in data:
            test_case = TestCase(**case_data)
            self.add_test_case(test_case)
    
    def run_test(self, test_case: TestCase) -> TestResult:
        """Run a single test case"""
        start_time = time.time()
        
        # Create agent for this test
        agent = create_agent(
            tracer=self.tracer,
            use_mock=self.use_mock_agent,
            verbose=False
        )
        
        try:
            # Run the agent
            output = agent.run(test_case.query, test_case.metadata)
            
            # Get the run details from tracer
            run_data = self.tracer.get_run(self.tracer.current_run.run_id if self.tracer.current_run else None)
            
            # Extract tools used
            tools_used = []
            if run_data and 'steps' in run_data:
                for step in run_data['steps']:
                    if step['step_type'] == 'tool_execution' and step['tool_name']:
                        tools_used.append(step['tool_name'])
            
            # Evaluate the result
            status = "passed"
            failure_reason = None
            
            # Check if expected tools were used
            if test_case.expected_tools:
                missing_tools = set(test_case.expected_tools) - set(tools_used)
                extra_tools = set(tools_used) - set(test_case.expected_tools)
                
                if missing_tools or extra_tools:
                    status = "failed"
                    failure_reason = f"Tool mismatch. Missing: {missing_tools}, Extra: {extra_tools}"
            
            # Check if we expected an error but didn't get one
            if test_case.expected_error and status == "passed":
                status = "failed"
                failure_reason = f"Expected error '{test_case.expected_error}' but execution succeeded"
            
            duration_ms = (time.time() - start_time) * 1000
            
            return TestResult(
                test_id=test_case.id,
                run_id=run_data['run_id'] if run_data else "unknown",
                status=status,
                actual_output=output,
                tools_used=tools_used,
                duration_ms=duration_ms,
                failure_reason=failure_reason,
                timestamp=datetime.now()
            )
        
        except Exception as e:
            # Handle errors
            error_str = str(e)
            duration_ms = (time.time() - start_time) * 1000
            
            # Check if this was an expected error
            status = "error"
            failure_reason = f"Unexpected error: {error_str}"
            
            if test_case.expected_error:
                if test_case.expected_error.lower() in error_str.lower():
                    status = "passed"
                    failure_reason = None
                else:
                    status = "failed"
                    failure_reason = f"Expected error '{test_case.expected_error}' but got '{error_str}'"
            
            return TestResult(
                test_id=test_case.id,
                run_id="error",
                status=status,
                actual_error=error_str,
                duration_ms=duration_ms,
                failure_reason=failure_reason,
                timestamp=datetime.now()
            )
    
    def run_all_tests(self, parallel: bool = False) -> List[TestResult]:
        """Run all test cases"""
        self.results = []
        
        for test_case in self.test_cases:
            print(f"Running test: {test_case.name}")
            result = self.run_test(test_case)
            self.results.append(result)
            
            # Print result
            status_symbol = "✓" if result.status == "passed" else "✗"
            print(f"  {status_symbol} {result.status.upper()}")
            if result.failure_reason:
                print(f"    Reason: {result.failure_reason}")
        
        return self.results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of test results"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "passed")
        failed = sum(1 for r in self.results if r.status == "failed")
        errors = sum(1 for r in self.results if r.status == "error")
        
        avg_duration = sum(r.duration_ms or 0 for r in self.results) / total if total > 0 else 0
        
        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": passed / total if total > 0 else 0,
            "avg_duration_ms": avg_duration,
            "timestamp": datetime.now().isoformat()
        }
    
    def save_results(self, file_path: str):
        """Save test results to a JSON file"""
        data = {
            "summary": self.get_summary(),
            "test_cases": [tc.to_dict() for tc in self.test_cases],
            "results": [r.to_dict() for r in self.results]
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def replay_failed_tests(self) -> List[TestResult]:
        """Re-run only the failed tests"""
        failed_test_ids = [r.test_id for r in self.results if r.status in ["failed", "error"]]
        failed_tests = [tc for tc in self.test_cases if tc.id in failed_test_ids]
        
        print(f"\nReplaying {len(failed_tests)} failed tests...")
        
        replay_results = []
        for test_case in failed_tests:
            print(f"Replaying: {test_case.name}")
            result = self.run_test(test_case)
            replay_results.append(result)
            
            status_symbol = "✓" if result.status == "passed" else "✗"
            print(f"  {status_symbol} {result.status.upper()}")
        
        return replay_results


def create_default_test_cases() -> List[TestCase]:
    """Create a default set of test cases for demonstration"""
    return [
        # Successful cases
        TestCase(
            id="test_001",
            name="Weather Query - Success",
            query="What's the weather in London?",
            expected_behavior="Should use weather tool and return weather information",
            expected_tools=["get_weather"]
        ),
        
        TestCase(
            id="test_002",
            name="Customer Lookup - Success",
            query="Look up customer 12345",
            expected_behavior="Should use customer tool and return customer information",
            expected_tools=["get_customer"]
        ),
        
        TestCase(
            id="test_003",
            name="Calculator - Success",
            query="Calculate 15 * 23 + 7",
            expected_behavior="Should use calculator tool and return result",
            expected_tools=["calculate"]
        ),
        
        TestCase(
            id="test_004",
            name="Text Summarization - Success",
            query="Summarize: The quick brown fox jumps over the lazy dog. This is a classic pangram that contains all letters of the alphabet.",
            expected_behavior="Should use summarize tool",
            expected_tools=["summarize_text"]
        ),
        
        # Error cases
        TestCase(
            id="test_005",
            name="Customer Not Found",
            query="Look up customer invalid123",
            expected_behavior="Should fail with customer not found error",
            expected_tools=["get_customer"],
            expected_error="not found"
        ),
        
        TestCase(
            id="test_006",
            name="Invalid Calculation",
            query="Calculate 10 / 0",
            expected_behavior="Should fail with division by zero error",
            expected_tools=["calculate"],
            expected_error="division by zero"
        ),
        
        TestCase(
            id="test_007",
            name="Text Too Short",
            query="Summarize: Hi",
            expected_behavior="Should fail with text too short error",
            expected_tools=["summarize_text"],
            expected_error="too short"
        ),
        
        # Edge cases
        TestCase(
            id="test_008",
            name="Ambiguous Query",
            query="Tell me about the status",
            expected_behavior="Agent should handle ambiguous query gracefully",
            expected_tools=[]
        ),
        
        TestCase(
            id="test_009",
            name="Multiple Tools Query",
            query="What's the weather in Paris and calculate 100 + 200",
            expected_behavior="Should use multiple tools",
            expected_tools=["get_weather", "calculate"]
        ),
    ]


if __name__ == "__main__":
    # Example usage
    tracer = ExecutionTracer()
    harness = TestHarness(tracer, use_mock_agent=True)
    
    # Add default test cases
    for test_case in create_default_test_cases():
        harness.add_test_case(test_case)
    
    # Run tests
    results = harness.run_all_tests()
    
    # Print summary
    summary = harness.get_summary()
    print(f"\nTest Summary:")
    print(f"  Total: {summary['total_tests']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Errors: {summary['errors']}")
    print(f"  Pass Rate: {summary['pass_rate']:.1%}") 