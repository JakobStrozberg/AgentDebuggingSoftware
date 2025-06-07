"""
CLI interface for CellSight - LLM Agent Debugging Tool
"""

import click
import json
import subprocess
import time
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.tree import Tree
from datetime import datetime

from cellsight.core.tracer import ExecutionTracer, ErrorType
from cellsight.core.agent import create_agent
from cellsight.core.test_harness import TestHarness, create_default_test_cases


console = Console()


@click.group()
def cli():
    """CellSight - Debug and evaluate LLM-powered agents"""
    pass


@cli.command()
@click.option('--host', default='127.0.0.1', help='Host for mock API server')
@click.option('--port', default=8000, help='Port for mock API server')
def start_api(host, port):
    """Start the mock API server"""
    console.print(f"[green]Starting mock API server on {host}:{port}...[/green]")
    
    try:
        # Run the API server
        subprocess.run([
            "python", "-m", "uvicorn", 
            "cellsight.api.mock_api:app",
            "--host", host,
            "--port", str(port),
            "--reload"
        ])
    except KeyboardInterrupt:
        console.print("\n[yellow]API server stopped.[/yellow]")


@cli.command()
@click.argument('query')
@click.option('--mock', is_flag=True, help='Use mock agent (no OpenAI API needed)')
@click.option('--verbose', is_flag=True, help='Show detailed execution trace')
def run(query, mock, verbose):
    """Run a single query through the agent"""
    tracer = ExecutionTracer()
    
    console.print(f"[blue]Running query:[/blue] {query}")
    console.print()
    
    try:
        agent = create_agent(tracer, use_mock=mock, verbose=verbose)
        result = agent.run(query)
        
        console.print(Panel(result, title="[green]Result[/green]", border_style="green"))
        
        # Show execution trace if verbose
        if verbose:
            run_data = tracer.get_run(tracer.current_run.run_id if tracer.current_run else None)
            if run_data:
                _display_trace(run_data)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        
        # Show trace on error
        run_data = tracer.get_run(tracer.current_run.run_id if tracer.current_run else None)
        if run_data:
            _display_trace(run_data)


@cli.command()
@click.option('--test-file', help='JSON file with test cases')
@click.option('--mock', is_flag=True, default=True, help='Use mock agent')
@click.option('--save-results', help='Save results to JSON file')
def test(test_file, mock, save_results):
    """Run test cases through the agent"""
    tracer = ExecutionTracer()
    harness = TestHarness(tracer, use_mock_agent=mock)
    
    # Load test cases
    if test_file:
        harness.load_test_cases(test_file)
        console.print(f"[green]Loaded test cases from {test_file}[/green]")
    else:
        # Use default test cases
        for test_case in create_default_test_cases():
            harness.add_test_case(test_case)
        console.print("[green]Using default test cases[/green]")
    
    console.print()
    
    # Run tests
    results = harness.run_all_tests()
    
    # Display summary
    summary = harness.get_summary()
    _display_test_summary(summary)
    
    # Save results if requested
    if save_results:
        harness.save_results(save_results)
        console.print(f"\n[green]Results saved to {save_results}[/green]")


@cli.command()
@click.option('--limit', default=10, help='Number of recent runs to show')
def history(limit):
    """Show recent agent runs"""
    tracer = ExecutionTracer()
    runs = tracer.get_recent_runs(limit)
    
    if not runs:
        console.print("[yellow]No runs found.[/yellow]")
        return
    
    table = Table(title="Recent Agent Runs")
    table.add_column("Run ID", style="cyan")
    table.add_column("Query", style="white")
    table.add_column("Status", style="green")
    table.add_column("Error Type", style="red")
    table.add_column("Start Time", style="blue")
    
    for run in runs:
        status_style = "green" if run['status'] == 'success' else "red"
        table.add_row(
            run['run_id'][:8] + "...",
            run['query'][:50] + "..." if len(run['query']) > 50 else run['query'],
            f"[{status_style}]{run['status']}[/{status_style}]",
            run['error_type'] or "-",
            run['start_time']
        )
    
    console.print(table)


@cli.command()
@click.argument('run_id')
def trace(run_id):
    """Show detailed trace for a specific run"""
    tracer = ExecutionTracer()
    
    # Try to find run with partial ID
    runs = tracer.get_recent_runs(100)
    matching_run = None
    for run in runs:
        if run['run_id'].startswith(run_id):
            matching_run = run
            break
    
    if not matching_run:
        console.print(f"[red]Run ID {run_id} not found.[/red]")
        return
    
    # Get full run data
    run_data = tracer.get_run(matching_run['run_id'])
    if not run_data:
        console.print(f"[red]Could not load run data.[/red]")
        return
    
    _display_trace(run_data)


@cli.command()
def metrics():
    """Show overall metrics and statistics"""
    tracer = ExecutionTracer()
    metrics = tracer.get_metrics()
    
    # Create metrics panel
    metrics_text = f"""
[bold]Total Runs:[/bold] {metrics['total_runs']}
[bold]Success Rate:[/bold] {metrics['success_rate']:.1%}
[bold]Average Duration:[/bold] {metrics.get('avg_duration_seconds', 0):.2f}s

[bold]Status Distribution:[/bold]
"""
    
    for status, count in metrics['status_counts'].items():
        percentage = (count / metrics['total_runs'] * 100) if metrics['total_runs'] > 0 else 0
        metrics_text += f"  • {status}: {count} ({percentage:.1f}%)\n"
    
    if metrics['error_counts']:
        metrics_text += "\n[bold]Error Types:[/bold]\n"
        for error_type, count in metrics['error_counts'].items():
            metrics_text += f"  • {error_type}: {count}\n"
    
    console.print(Panel(metrics_text.strip(), title="[cyan]CellSight Metrics[/cyan]", border_style="cyan"))


@cli.command()
@click.argument('run_id')
def replay(run_id):
    """Replay a specific run for debugging"""
    tracer = ExecutionTracer()
    
    # Find the run
    runs = tracer.get_recent_runs(100)
    matching_run = None
    for run in runs:
        if run['run_id'].startswith(run_id):
            matching_run = run
            break
    
    if not matching_run:
        console.print(f"[red]Run ID {run_id} not found.[/red]")
        return
    
    # Get full run data
    run_data = tracer.get_run(matching_run['run_id'])
    if not run_data:
        console.print(f"[red]Could not load run data.[/red]")
        return
    
    query = run_data['query']
    console.print(f"[blue]Replaying query:[/blue] {query}")
    console.print()
    
    # Create new agent and run
    agent = create_agent(tracer, use_mock=True, verbose=True)
    
    try:
        result = agent.run(query)
        console.print(Panel(result, title="[green]Replay Result[/green]", border_style="green"))
        
        # Show new trace
        new_run_data = tracer.get_run(tracer.current_run.run_id if tracer.current_run else None)
        if new_run_data:
            console.print("\n[yellow]New Execution Trace:[/yellow]")
            _display_trace(new_run_data)
            
    except Exception as e:
        console.print(f"[red]Replay Error:[/red] {str(e)}")


@cli.command()
@click.option('--failure-rate', type=float, help='Set API failure rate (0.0-1.0)')
@click.option('--timeout-rate', type=float, help='Set API timeout rate (0.0-1.0)')
@click.option('--invalid-rate', type=float, help='Set invalid response rate (0.0-1.0)')
def configure_api(failure_rate, timeout_rate, invalid_rate):
    """Configure mock API behavior for testing"""
    import httpx
    
    config = {}
    if failure_rate is not None:
        config['failure_rate'] = failure_rate
    if timeout_rate is not None:
        config['timeout_rate'] = timeout_rate
    if invalid_rate is not None:
        config['invalid_response_rate'] = invalid_rate
    
    if not config:
        # Show current config
        try:
            response = httpx.get("http://localhost:8000/api/config")
            response.raise_for_status()
            current_config = response.json()
            
            console.print(Panel(
                json.dumps(current_config, indent=2),
                title="[cyan]Current API Configuration[/cyan]",
                border_style="cyan"
            ))
        except Exception as e:
            console.print(f"[red]Could not get API configuration: {str(e)}[/red]")
            console.print("[yellow]Make sure the API server is running (cellsight start-api)[/yellow]")
    else:
        # Update config
        try:
            response = httpx.post("http://localhost:8000/api/config", params=config)
            response.raise_for_status()
            new_config = response.json()
            
            console.print(Panel(
                json.dumps(new_config, indent=2),
                title="[green]Updated API Configuration[/green]",
                border_style="green"
            ))
        except Exception as e:
            console.print(f"[red]Could not update API configuration: {str(e)}[/red]")
            console.print("[yellow]Make sure the API server is running (cellsight start-api)[/yellow]")


def _display_trace(run_data):
    """Display a run trace in a nice format"""
    # Header
    console.print(Panel(
        f"[bold]Query:[/bold] {run_data['query']}\n"
        f"[bold]Status:[/bold] {run_data['status']}\n"
        f"[bold]Duration:[/bold] {_calculate_duration(run_data)}ms",
        title=f"[cyan]Run {run_data['run_id'][:8]}...[/cyan]",
        border_style="cyan"
    ))
    
    # Steps tree
    tree = Tree("[bold]Execution Steps[/bold]")
    
    for step in run_data['steps']:
        step_type = step['step_type']
        timestamp = step['timestamp']
        
        # Create step node
        if step_type == 'agent_start':
            node = tree.add(f"[green]▶ Agent Started[/green] @ {timestamp}")
        elif step_type == 'agent_end':
            node = tree.add(f"[green]■ Agent Ended[/green] @ {timestamp}")
        elif step_type == 'agent_error':
            node = tree.add(f"[red]✗ Agent Error[/red] @ {timestamp}")
            if step.get('error'):
                node.add(f"[red]{step['error']['message']}[/red]")
        elif step_type == 'tool_selection':
            node = tree.add(f"[blue]🔧 Selected Tool: {step['tool_name']}[/blue] @ {timestamp}")
        elif step_type == 'tool_execution':
            duration = f" ({step.get('duration_ms', 0):.1f}ms)" if step.get('duration_ms') else ""
            node = tree.add(f"[yellow]⚡ Executed: {step['tool_name']}[/yellow]{duration} @ {timestamp}")
            if step.get('input_data'):
                node.add(f"Input: {json.dumps(step['input_data'], indent=2)}")
            if step.get('output_data'):
                node.add(f"Output: {json.dumps(step['output_data'], indent=2)}")
        elif step_type == 'tool_error':
            node = tree.add(f"[red]✗ Tool Error: {step['tool_name']}[/red] @ {timestamp}")
            if step.get('error'):
                node.add(f"[red]{step['error']['message']}[/red]")
        elif step_type == 'agent_decision':
            node = tree.add(f"[magenta]🤔 Agent Decision[/magenta] @ {timestamp}")
            if step.get('input_data'):
                node.add(f"Decision: {json.dumps(step['input_data'], indent=2)}")
    
    console.print(tree)
    
    # Error details if failed
    if run_data['status'] == 'failed' and run_data.get('error_message'):
        console.print(Panel(
            f"[bold]Error Type:[/bold] {run_data.get('error_type', 'Unknown')}\n"
            f"[bold]Message:[/bold] {run_data['error_message']}",
            title="[red]Error Details[/red]",
            border_style="red"
        ))


def _display_test_summary(summary):
    """Display test summary in a nice format"""
    # Calculate pass rate color
    pass_rate = summary['pass_rate']
    if pass_rate >= 0.9:
        rate_color = "green"
    elif pass_rate >= 0.7:
        rate_color = "yellow"
    else:
        rate_color = "red"
    
    summary_text = f"""
[bold]Total Tests:[/bold] {summary['total_tests']}
[bold]Passed:[/bold] [green]{summary['passed']}[/green]
[bold]Failed:[/bold] [red]{summary['failed']}[/red]
[bold]Errors:[/bold] [red]{summary['errors']}[/red]
[bold]Pass Rate:[/bold] [{rate_color}]{pass_rate:.1%}[/{rate_color}]
[bold]Average Duration:[/bold] {summary['avg_duration_ms']:.1f}ms
"""
    
    console.print(Panel(
        summary_text.strip(),
        title="[cyan]Test Summary[/cyan]",
        border_style="cyan"
    ))


def _calculate_duration(run_data):
    """Calculate run duration in milliseconds"""
    if not run_data.get('start_time') or not run_data.get('end_time'):
        return 0
    
    start = datetime.fromisoformat(run_data['start_time'])
    end = datetime.fromisoformat(run_data['end_time'])
    duration = (end - start).total_seconds() * 1000
    return round(duration, 1)


if __name__ == "__main__":
    cli() 