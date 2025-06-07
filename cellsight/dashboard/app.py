"""
Streamlit dashboard for CellSight - Web UI for debugging LLM agents
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import time

from cellsight.core.tracer import ExecutionTracer, ErrorType
from cellsight.core.agent import create_agent
from cellsight.core.test_harness import TestHarness, create_default_test_cases


# Page config
st.set_page_config(
    page_title="CellSight Dashboard",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'tracer' not in st.session_state:
    st.session_state.tracer = ExecutionTracer()

if 'test_harness' not in st.session_state:
    st.session_state.test_harness = TestHarness(st.session_state.tracer, use_mock_agent=True)


def main():
    """Main dashboard application"""
    st.title("🔍 CellSight - LLM Agent Debugger")
    st.markdown("Debug and evaluate LLM-powered agents with detailed execution tracing")
    
    # Sidebar navigation
    page = st.sidebar.selectbox(
        "Navigation",
        ["Run Agent", "Test Suite", "Execution History", "Metrics & Analytics", "Trace Viewer"]
    )
    
    if page == "Run Agent":
        run_agent_page()
    elif page == "Test Suite":
        test_suite_page()
    elif page == "Execution History":
        execution_history_page()
    elif page == "Metrics & Analytics":
        metrics_page()
    elif page == "Trace Viewer":
        trace_viewer_page()


def run_agent_page():
    """Page for running single queries through the agent"""
    st.header("🤖 Run Agent")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        query = st.text_input("Enter your query:", placeholder="What's the weather in London?")
    
    with col2:
        use_mock = st.checkbox("Use Mock Agent", value=True, help="Use mock agent (no OpenAI API needed)")
    
    if st.button("Run Query", type="primary"):
        if query:
            with st.spinner("Running agent..."):
                try:
                    # Create and run agent
                    agent = create_agent(st.session_state.tracer, use_mock=use_mock, verbose=False)
                    start_time = time.time()
                    result = agent.run(query)
                    duration = (time.time() - start_time) * 1000
                    
                    # Display result
                    st.success("Query completed successfully!")
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.subheader("Result")
                        st.info(result)
                    
                    with col2:
                        st.metric("Duration", f"{duration:.1f} ms")
                    
                    # Show trace
                    with st.expander("View Execution Trace", expanded=True):
                        run_data = st.session_state.tracer.get_run(
                            st.session_state.tracer.current_run.run_id 
                            if st.session_state.tracer.current_run else None
                        )
                        if run_data:
                            display_trace(run_data)
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    
                    # Show error trace
                    with st.expander("View Error Trace", expanded=True):
                        run_data = st.session_state.tracer.get_run(
                            st.session_state.tracer.current_run.run_id 
                            if st.session_state.tracer.current_run else None
                        )
                        if run_data:
                            display_trace(run_data)
        else:
            st.warning("Please enter a query")


def test_suite_page():
    """Page for running test suites"""
    st.header("🧪 Test Suite")
    
    # Test case management
    col1, col2 = st.columns([2, 1])
    
    with col1:
        test_option = st.radio(
            "Test Cases",
            ["Use Default Test Cases", "Upload Custom Test Cases"]
        )
    
    if test_option == "Upload Custom Test Cases":
        uploaded_file = st.file_uploader("Upload test cases (JSON)", type=['json'])
        if uploaded_file:
            test_cases = json.load(uploaded_file)
            st.success(f"Loaded {len(test_cases)} test cases")
    
    # Run tests button
    if st.button("Run Test Suite", type="primary"):
        # Clear previous results
        st.session_state.test_harness = TestHarness(st.session_state.tracer, use_mock_agent=True)
        
        # Add test cases
        if test_option == "Use Default Test Cases":
            for test_case in create_default_test_cases():
                st.session_state.test_harness.add_test_case(test_case)
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Run tests
        results = []
        total_tests = len(st.session_state.test_harness.test_cases)
        
        for i, test_case in enumerate(st.session_state.test_harness.test_cases):
            status_text.text(f"Running test {i+1}/{total_tests}: {test_case.name}")
            result = st.session_state.test_harness.run_test(test_case)
            results.append(result)
            progress_bar.progress((i + 1) / total_tests)
        
        st.session_state.test_harness.results = results
        status_text.text("Test suite completed!")
        
        # Display results
        display_test_results()


def display_test_results():
    """Display test suite results"""
    if not st.session_state.test_harness.results:
        return
    
    summary = st.session_state.test_harness.get_summary()
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Tests", summary['total_tests'])
    
    with col2:
        st.metric("Passed", summary['passed'], 
                 delta=f"{summary['pass_rate']:.1%}")
    
    with col3:
        st.metric("Failed", summary['failed'])
    
    with col4:
        st.metric("Avg Duration", f"{summary['avg_duration_ms']:.1f} ms")
    
    # Results table
    st.subheader("Test Results")
    
    results_data = []
    for result in st.session_state.test_harness.results:
        test_case = next(tc for tc in st.session_state.test_harness.test_cases 
                        if tc.id == result.test_id)
        
        results_data.append({
            "Test Name": test_case.name,
            "Status": result.status,
            "Duration (ms)": f"{result.duration_ms:.1f}" if result.duration_ms else "N/A",
            "Tools Used": ", ".join(result.tools_used) if result.tools_used else "None",
            "Failure Reason": result.failure_reason or "-"
        })
    
    df = pd.DataFrame(results_data)
    
    # Color code status
    def color_status(val):
        if val == "passed":
            return "background-color: #90EE90"
        elif val == "failed":
            return "background-color: #FFB6C1"
        else:
            return "background-color: #FFFFE0"
    
    styled_df = df.style.applymap(color_status, subset=['Status'])
    st.dataframe(styled_df, use_container_width=True)
    
    # Failed tests details
    failed_results = [r for r in st.session_state.test_harness.results 
                     if r.status in ["failed", "error"]]
    
    if failed_results:
        st.subheader("Failed Test Details")
        for result in failed_results:
            test_case = next(tc for tc in st.session_state.test_harness.test_cases 
                           if tc.id == result.test_id)
            
            with st.expander(f"❌ {test_case.name}"):
                st.write(f"**Query:** {test_case.query}")
                st.write(f"**Expected Behavior:** {test_case.expected_behavior}")
                if result.failure_reason:
                    st.error(f"**Failure Reason:** {result.failure_reason}")
                if result.actual_error:
                    st.error(f"**Error:** {result.actual_error}")


def execution_history_page():
    """Page for viewing execution history"""
    st.header("📜 Execution History")
    
    # Get recent runs
    limit = st.sidebar.number_input("Number of runs to show", min_value=10, max_value=100, value=20)
    runs = st.session_state.tracer.get_recent_runs(limit)
    
    if not runs:
        st.info("No execution history found. Run some queries first!")
        return
    
    # Filter options
    col1, col2 = st.columns(2)
    
    with col1:
        status_filter = st.multiselect(
            "Filter by status",
            ["success", "failed"],
            default=["success", "failed"]
        )
    
    with col2:
        search_query = st.text_input("Search queries", placeholder="Search...")
    
    # Filter runs
    filtered_runs = [
        run for run in runs
        if run['status'] in status_filter and
        (not search_query or search_query.lower() in run['query'].lower())
    ]
    
    # Display runs
    st.subheader(f"Showing {len(filtered_runs)} runs")
    
    for run in filtered_runs:
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        
        with col1:
            st.write(f"**{run['query'][:100]}{'...' if len(run['query']) > 100 else ''}**")
        
        with col2:
            if run['status'] == 'success':
                st.success(run['status'])
            else:
                st.error(run['status'])
        
        with col3:
            st.caption(run['start_time'][:19])
        
        with col4:
            if st.button("View Trace", key=f"trace_{run['run_id']}"):
                st.session_state.selected_run_id = run['run_id']
                st.experimental_rerun()


def metrics_page():
    """Page for metrics and analytics"""
    st.header("📊 Metrics & Analytics")
    
    metrics = st.session_state.tracer.get_metrics()
    
    if metrics['total_runs'] == 0:
        st.info("No data available yet. Run some queries to see metrics!")
        return
    
    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Runs", metrics['total_runs'])
    
    with col2:
        st.metric("Success Rate", f"{metrics['success_rate']:.1%}")
    
    with col3:
        st.metric("Avg Duration", f"{metrics.get('avg_duration_seconds', 0):.2f}s")
    
    with col4:
        error_count = sum(metrics['error_counts'].values()) if metrics['error_counts'] else 0
        st.metric("Total Errors", error_count)
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Status distribution pie chart
        if metrics['status_counts']:
            fig = px.pie(
                values=list(metrics['status_counts'].values()),
                names=list(metrics['status_counts'].keys()),
                title="Run Status Distribution",
                color_discrete_map={'success': '#90EE90', 'failed': '#FFB6C1'}
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Error types bar chart
        if metrics['error_counts']:
            fig = px.bar(
                x=list(metrics['error_counts'].keys()),
                y=list(metrics['error_counts'].values()),
                title="Error Type Distribution",
                labels={'x': 'Error Type', 'y': 'Count'}
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Recent trends
    st.subheader("Recent Trends")
    
    # Get all runs for trend analysis
    all_runs = st.session_state.tracer.get_recent_runs(1000)
    
    if len(all_runs) > 1:
        # Convert to DataFrame
        df = pd.DataFrame(all_runs)
        df['start_time'] = pd.to_datetime(df['start_time'])
        df['hour'] = df['start_time'].dt.floor('H')
        
        # Hourly success rate
        hourly_stats = df.groupby(['hour', 'status']).size().unstack(fill_value=0)
        if 'success' in hourly_stats.columns and 'failed' in hourly_stats.columns:
            hourly_stats['success_rate'] = (
                hourly_stats['success'] / 
                (hourly_stats['success'] + hourly_stats['failed'])
            ) * 100
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=hourly_stats.index,
                y=hourly_stats['success_rate'],
                mode='lines+markers',
                name='Success Rate',
                line=dict(color='green', width=2)
            ))
            
            fig.update_layout(
                title="Success Rate Over Time",
                xaxis_title="Time",
                yaxis_title="Success Rate (%)",
                yaxis=dict(range=[0, 105])
            )
            
            st.plotly_chart(fig, use_container_width=True)


def trace_viewer_page():
    """Page for viewing detailed execution traces"""
    st.header("🔍 Trace Viewer")
    
    # Run ID input
    run_id = st.text_input("Enter Run ID (or partial ID):", 
                          value=st.session_state.get('selected_run_id', ''))
    
    if run_id:
        # Find matching run
        runs = st.session_state.tracer.get_recent_runs(100)
        matching_run = None
        
        for run in runs:
            if run['run_id'].startswith(run_id):
                matching_run = run
                break
        
        if matching_run:
            # Get full run data
            run_data = st.session_state.tracer.get_run(matching_run['run_id'])
            
            if run_data:
                # Display run info
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Status", run_data['status'])
                
                with col2:
                    duration = calculate_duration(run_data)
                    st.metric("Duration", f"{duration:.1f} ms")
                
                with col3:
                    step_count = len(run_data.get('steps', []))
                    st.metric("Steps", step_count)
                
                st.subheader("Query")
                st.info(run_data['query'])
                
                # Display trace
                display_trace(run_data)
                
                # Replay button
                if st.button("🔄 Replay This Run"):
                    with st.spinner("Replaying..."):
                        agent = create_agent(st.session_state.tracer, use_mock=True, verbose=False)
                        try:
                            result = agent.run(run_data['query'])
                            st.success("Replay completed!")
                            st.write("**New Result:**")
                            st.info(result)
                        except Exception as e:
                            st.error(f"Replay failed: {str(e)}")
            else:
                st.error("Could not load run data")
        else:
            st.warning(f"No run found matching ID: {run_id}")
    else:
        st.info("Enter a Run ID to view its trace")


def display_trace(run_data):
    """Display execution trace in a nice format"""
    st.subheader("Execution Trace")
    
    steps = run_data.get('steps', [])
    
    for i, step in enumerate(steps):
        step_type = step['step_type']
        timestamp = step['timestamp']
        
        # Create step display
        if step_type == 'agent_start':
            st.success(f"▶ **Agent Started** - {timestamp}")
            
        elif step_type == 'agent_end':
            st.success(f"■ **Agent Ended** - {timestamp}")
            
        elif step_type == 'agent_error':
            st.error(f"✗ **Agent Error** - {timestamp}")
            if step.get('error'):
                st.error(f"Error: {step['error']['message']}")
                with st.expander("Stack Trace"):
                    st.code(step['error'].get('traceback', 'No traceback available'))
                    
        elif step_type == 'tool_selection':
            st.info(f"🔧 **Selected Tool:** `{step['tool_name']}` - {timestamp}")
            
        elif step_type == 'tool_execution':
            duration = step.get('duration_ms', 0)
            st.warning(f"⚡ **Executed:** `{step['tool_name']}` ({duration:.1f}ms) - {timestamp}")
            
            col1, col2 = st.columns(2)
            with col1:
                if step.get('input_data'):
                    with st.expander("Input"):
                        st.json(step['input_data'])
            
            with col2:
                if step.get('output_data'):
                    with st.expander("Output"):
                        st.json(step['output_data'])
                        
        elif step_type == 'tool_error':
            st.error(f"✗ **Tool Error:** `{step['tool_name']}` - {timestamp}")
            if step.get('error'):
                st.error(f"Error: {step['error']['message']}")
                
        elif step_type == 'agent_decision':
            st.info(f"🤔 **Agent Decision** - {timestamp}")
            if step.get('input_data'):
                with st.expander("Decision Details"):
                    st.json(step['input_data'])


def calculate_duration(run_data):
    """Calculate run duration in milliseconds"""
    if not run_data.get('start_time') or not run_data.get('end_time'):
        return 0
    
    start = datetime.fromisoformat(run_data['start_time'])
    end = datetime.fromisoformat(run_data['end_time'])
    duration = (end - start).total_seconds() * 1000
    return duration


if __name__ == "__main__":
    main() 