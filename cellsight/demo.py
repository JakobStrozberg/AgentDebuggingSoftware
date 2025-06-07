"""
Demo script showcasing CellSight capabilities
"""

import time
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import track

from cellsight.core.tracer import ExecutionTracer
from cellsight.core.agent import create_agent
from cellsight.core.test_harness import TestHarness, TestCase


console = Console()


def demo_single_query():
    """Demo: Running a single query with tracing"""
    console.print("\n[bold cyan]Demo 1: Single Query Execution[/bold cyan]")
    console.print("Running a weather query with full tracing...\n")
    
    tracer = ExecutionTracer()
    agent = create_agent(tracer, use_mock=True, verbose=False)
    
    query = "What's the weather in London?"
    
    try:
        console.print(f"[blue]Query:[/blue] {query}")
        result = agent.run(query)
        console.print(f"[green]Result:[/green] {result}\n")
        
        # Show trace summary
        run_data = tracer.get_run(tracer.current_run.run_id if tracer.current_run else None)
        if run_data:
            console.print("[yellow]Execution Trace:[/yellow]")
            for step in run_data['steps']:
                if step['step_type'] == 'tool_execution':
                    console.print(f"  • Used tool: [cyan]{step['tool_name']}[/cyan]")
    
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


def demo_error_handling():
    """Demo: Error handling and tracing"""
    console.print("\n[bold cyan]Demo 2: Error Handling[/bold cyan]")
    console.print("Demonstrating error capture and classification...\n")
    
    tracer = ExecutionTracer()
    agent = create_agent(tracer, use_mock=True, verbose=False)
    
    error_queries = [
        ("Division by zero", "Calculate 100 / 0"),
        ("Customer not found", "Look up customer invalid123"),
        ("Text too short", "Summarize: Hi")
    ]
    
    for name, query in error_queries:
        console.print(f"[blue]Testing:[/blue] {name}")
        console.print(f"[blue]Query:[/blue] {query}")
        
        try:
            result = agent.run(query)
            console.print(f"[green]Result:[/green] {result}")
        except Exception as e:
            console.print(f"[red]Expected Error:[/red] {str(e)}")
        
        console.print()


def demo_test_suite():
    """Demo: Running a test suite"""
    console.print("\n[bold cyan]Demo 3: Test Suite Execution[/bold cyan]")
    console.print("Running a comprehensive test suite...\n")
    
    tracer = ExecutionTracer()
    harness = TestHarness(tracer, use_mock_agent=True)
    
    # Add test cases
    test_cases = [
        TestCase(
            id="demo_001",
            name="Weather Success",
            query="What's the weather in Paris?",
            expected_behavior="Should get weather",
            expected_tools=["get_weather"]
        ),
        TestCase(
            id="demo_002",
            name="Math Calculation",
            query="Calculate 25 * 4 + 10",
            expected_behavior="Should calculate",
            expected_tools=["calculate"]
        ),
        TestCase(
            id="demo_003",
            name="Expected Failure",
            query="Calculate 10 / 0",
            expected_behavior="Should fail with division by zero",
            expected_tools=["calculate"],
            expected_error="division by zero"
        )
    ]
    
    for tc in test_cases:
        harness.add_test_case(tc)
    
    # Run tests with progress
    results = []
    for tc in track(harness.test_cases, description="Running tests..."):
        result = harness.run_test(tc)
        results.append(result)
    
    harness.results = results
    
    # Display results
    summary = harness.get_summary()
    
    table = Table(title="Test Results")
    table.add_column("Test", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Duration", style="yellow")
    
    for i, result in enumerate(results):
        status_style = "green" if result.status == "passed" else "red"
        table.add_row(
            test_cases[i].name,
            f"[{status_style}]{result.status}[/{status_style}]",
            f"{result.duration_ms:.1f}ms"
        )
    
    console.print(table)
    console.print(f"\n[bold]Pass Rate:[/bold] {summary['pass_rate']:.1%}")


def demo_metrics():
    """Demo: Metrics and analytics"""
    console.print("\n[bold cyan]Demo 4: Metrics Dashboard[/bold cyan]")
    console.print("Showing execution metrics and analytics...\n")
    
    tracer = ExecutionTracer()
    
    # Run some queries to generate data
    agent = create_agent(tracer, use_mock=True, verbose=False)
    
    queries = [
        "What's the weather in Tokyo?",
        "Calculate 15 * 23",
        "Look up customer 12345",
        "Calculate 10 / 0",  # Will fail
        "Summarize: This is a test",
        "What's the weather in Berlin?"
    ]
    
    console.print("Generating sample data...")
    for query in track(queries, description="Running queries..."):
        try:
            agent.run(query)
        except:
            pass  # Ignore errors for demo
    
    # Get and display metrics
    metrics = tracer.get_metrics()
    
    panel_content = f"""
[bold]Total Runs:[/bold] {metrics['total_runs']}
[bold]Success Rate:[/bold] {metrics['success_rate']:.1%}
[bold]Average Duration:[/bold] {metrics.get('avg_duration_seconds', 0):.2f}s

[bold]Status Distribution:[/bold]
"""
    
    for status, count in metrics['status_counts'].items():
        panel_content += f"  • {status}: {count}\n"
    
    if metrics['error_counts']:
        panel_content += "\n[bold]Error Types:[/bold]\n"
        for error_type, count in metrics['error_counts'].items():
            panel_content += f"  • {error_type}: {count}\n"
    
    console.print(Panel(panel_content.strip(), title="Execution Metrics", border_style="cyan"))


def demo_replay():
    """Demo: Replay functionality"""
    console.print("\n[bold cyan]Demo 5: Replay Failed Runs[/bold cyan]")
    console.print("Demonstrating replay functionality for debugging...\n")
    
    tracer = ExecutionTracer()
    agent = create_agent(tracer, use_mock=True, verbose=False)
    
    # First, create a failed run
    query = "Look up customer invalid999"
    console.print(f"[blue]Original Query:[/blue] {query}")
    
    try:
        result = agent.run(query)
    except Exception as e:
        console.print(f"[red]Failed:[/red] {str(e)}")
    
    # Get the run ID
    runs = tracer.get_recent_runs(1)
    if runs:
        run_id = runs[0]['run_id']
        console.print(f"\n[yellow]Run ID:[/yellow] {run_id[:8]}...")
        
        # Replay the run
        console.print("\n[green]Replaying the failed run...[/green]")
        run_data = tracer.get_run(run_id)
        
        if run_data:
            # Create new agent and replay
            new_agent = create_agent(tracer, use_mock=True, verbose=False)
            
            try:
                result = new_agent.run(run_data['query'])
                console.print(f"[green]Replay Result:[/green] {result}")
            except Exception as e:
                console.print(f"[red]Replay also failed:[/red] {str(e)}")
                console.print("[yellow]This confirms the error is reproducible![/yellow]")


def main():
    """Run all demos"""
    console.print(Panel.fit(
        "[bold]CellSight Demo[/bold]\n"
        "Showcasing LLM Agent Debugging Capabilities",
        border_style="cyan"
    ))
    
    demos = [
        demo_single_query,
        demo_error_handling,
        demo_test_suite,
        demo_metrics,
        demo_replay
    ]
    
    for demo in demos:
        demo()
        time.sleep(1)  # Pause between demos
    
    console.print("\n[bold green]Demo completed![/bold green]")
    console.print("Try running these commands:")
    console.print("  • [cyan]cellsight run \"What's the weather in London?\" --mock[/cyan]")
    console.print("  • [cyan]cellsight test[/cyan]")
    console.print("  • [cyan]cellsight history[/cyan]")
    console.print("  • [cyan]cellsight metrics[/cyan]")
    console.print("  • [cyan]streamlit run cellsight/dashboard/app.py[/cyan]")


if __name__ == "__main__":
    main() 