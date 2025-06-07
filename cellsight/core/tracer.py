"""
Tracer module for capturing agent execution steps, errors, and metrics.
"""

import json
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
import sqlite3
from pathlib import Path
import uuid


class StepType(Enum):
    """Types of steps in agent execution"""
    AGENT_START = "agent_start"
    TOOL_SELECTION = "tool_selection"
    TOOL_EXECUTION = "tool_execution"
    TOOL_ERROR = "tool_error"
    AGENT_DECISION = "agent_decision"
    AGENT_END = "agent_end"
    AGENT_ERROR = "agent_error"


class ErrorType(Enum):
    """Types of errors that can occur"""
    TOOL_SELECTION_ERROR = "tool_selection_error"
    TOOL_EXECUTION_ERROR = "tool_execution_error"
    API_ERROR = "api_error"
    TIMEOUT_ERROR = "timeout_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ExecutionStep:
    """Represents a single step in agent execution"""
    step_id: str
    run_id: str
    timestamp: datetime
    step_type: StepType
    tool_name: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['step_type'] = self.step_type.value
        return data


@dataclass
class AgentRun:
    """Represents a complete agent execution run"""
    run_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    query: str = ""
    status: str = "running"  # running, success, failed
    error_type: Optional[ErrorType] = None
    error_message: Optional[str] = None
    steps: List[ExecutionStep] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.steps is None:
            self.steps = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat() if self.end_time else None
        data['error_type'] = self.error_type.value if self.error_type else None
        data['steps'] = [step.to_dict() for step in self.steps]
        return data


class ExecutionTracer:
    """Main tracer class for capturing agent executions"""
    
    def __init__(self, db_path: str = "cellsight/data/traces.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.current_run: Optional[AgentRun] = None
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database for storing traces"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                start_time TEXT NOT NULL,
                end_time TEXT,
                query TEXT,
                status TEXT,
                error_type TEXT,
                error_message TEXT,
                metadata TEXT
            )
        """)
        
        # Create steps table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS steps (
                step_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                step_type TEXT NOT NULL,
                tool_name TEXT,
                input_data TEXT,
                output_data TEXT,
                error TEXT,
                duration_ms REAL,
                metadata TEXT,
                FOREIGN KEY (run_id) REFERENCES runs (run_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def start_run(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start a new agent run"""
        run_id = str(uuid.uuid4())
        self.current_run = AgentRun(
            run_id=run_id,
            start_time=datetime.now(),
            query=query,
            metadata=metadata or {}
        )
        
        # Log the start
        self.log_step(
            step_type=StepType.AGENT_START,
            input_data={"query": query},
            metadata=metadata
        )
        
        return run_id
    
    def end_run(self, status: str = "success", error: Optional[Exception] = None):
        """End the current run"""
        if not self.current_run:
            return
        
        self.current_run.end_time = datetime.now()
        self.current_run.status = status
        
        if error:
            self.current_run.error_type = self._classify_error(error)
            self.current_run.error_message = str(error)
            
            # Log the error
            self.log_step(
                step_type=StepType.AGENT_ERROR,
                error={
                    "type": self.current_run.error_type.value,
                    "message": str(error),
                    "traceback": traceback.format_exc()
                }
            )
        
        # Log the end
        self.log_step(
            step_type=StepType.AGENT_END,
            output_data={"status": status}
        )
        
        # Save to database
        self._save_run()
        self.current_run = None
    
    def log_step(self,
                 step_type: StepType,
                 tool_name: Optional[str] = None,
                 input_data: Optional[Dict[str, Any]] = None,
                 output_data: Optional[Dict[str, Any]] = None,
                 error: Optional[Dict[str, Any]] = None,
                 duration_ms: Optional[float] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        """Log a single execution step"""
        if not self.current_run:
            return
        
        step = ExecutionStep(
            step_id=str(uuid.uuid4()),
            run_id=self.current_run.run_id,
            timestamp=datetime.now(),
            step_type=step_type,
            tool_name=tool_name,
            input_data=input_data,
            output_data=output_data,
            error=error,
            duration_ms=duration_ms,
            metadata=metadata
        )
        
        self.current_run.steps.append(step)
    
    def log_tool_execution(self, tool_name: str, input_data: Dict[str, Any], 
                          start_time: float) -> 'ToolExecutionContext':
        """Context manager for logging tool execution"""
        return ToolExecutionContext(self, tool_name, input_data, start_time)
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify the type of error"""
        error_str = str(error).lower()
        
        if "timeout" in error_str:
            return ErrorType.TIMEOUT_ERROR
        elif "api" in error_str or "request" in error_str:
            return ErrorType.API_ERROR
        elif "validation" in error_str or "invalid" in error_str:
            return ErrorType.VALIDATION_ERROR
        elif "tool" in error_str and "selection" in error_str:
            return ErrorType.TOOL_SELECTION_ERROR
        elif "tool" in error_str:
            return ErrorType.TOOL_EXECUTION_ERROR
        else:
            return ErrorType.UNKNOWN_ERROR
    
    def _save_run(self):
        """Save the current run to database"""
        if not self.current_run:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Save run
        run_data = self.current_run.to_dict()
        cursor.execute("""
            INSERT INTO runs (run_id, start_time, end_time, query, status, 
                            error_type, error_message, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_data['run_id'],
            run_data['start_time'],
            run_data['end_time'],
            run_data['query'],
            run_data['status'],
            run_data['error_type'],
            run_data['error_message'],
            json.dumps(run_data.get('metadata', {}))
        ))
        
        # Save steps
        for step in self.current_run.steps:
            step_data = step.to_dict()
            cursor.execute("""
                INSERT INTO steps (step_id, run_id, timestamp, step_type, tool_name,
                                 input_data, output_data, error, duration_ms, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                step_data['step_id'],
                step_data['run_id'],
                step_data['timestamp'],
                step_data['step_type'],
                step_data.get('tool_name'),
                json.dumps(step_data.get('input_data', {})),
                json.dumps(step_data.get('output_data', {})),
                json.dumps(step_data.get('error', {})),
                step_data.get('duration_ms'),
                json.dumps(step_data.get('metadata', {}))
            ))
        
        conn.commit()
        conn.close()
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a run by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get run
        cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        run_row = cursor.fetchone()
        
        if not run_row:
            conn.close()
            return None
        
        # Get steps
        cursor.execute("SELECT * FROM steps WHERE run_id = ? ORDER BY timestamp", (run_id,))
        step_rows = cursor.fetchall()
        
        conn.close()
        
        # Convert to dict
        run_data = {
            'run_id': run_row[0],
            'start_time': run_row[1],
            'end_time': run_row[2],
            'query': run_row[3],
            'status': run_row[4],
            'error_type': run_row[5],
            'error_message': run_row[6],
            'metadata': json.loads(run_row[7] or '{}'),
            'steps': []
        }
        
        for step_row in step_rows:
            step_data = {
                'step_id': step_row[0],
                'run_id': step_row[1],
                'timestamp': step_row[2],
                'step_type': step_row[3],
                'tool_name': step_row[4],
                'input_data': json.loads(step_row[5] or '{}'),
                'output_data': json.loads(step_row[6] or '{}'),
                'error': json.loads(step_row[7] or '{}'),
                'duration_ms': step_row[8],
                'metadata': json.loads(step_row[9] or '{}')
            }
            run_data['steps'].append(step_data)
        
        return run_data
    
    def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent runs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT run_id, start_time, end_time, query, status, error_type
            FROM runs
            ORDER BY start_time DESC
            LIMIT ?
        """, (limit,))
        
        runs = []
        for row in cursor.fetchall():
            runs.append({
                'run_id': row[0],
                'start_time': row[1],
                'end_time': row[2],
                'query': row[3],
                'status': row[4],
                'error_type': row[5]
            })
        
        conn.close()
        return runs
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get overall metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total runs
        cursor.execute("SELECT COUNT(*) FROM runs")
        total_runs = cursor.fetchone()[0]
        
        # Success/failure counts
        cursor.execute("SELECT status, COUNT(*) FROM runs GROUP BY status")
        status_counts = dict(cursor.fetchall())
        
        # Error type counts
        cursor.execute("""
            SELECT error_type, COUNT(*) 
            FROM runs 
            WHERE error_type IS NOT NULL 
            GROUP BY error_type
        """)
        error_counts = dict(cursor.fetchall())
        
        # Average duration
        cursor.execute("""
            SELECT AVG(julianday(end_time) - julianday(start_time)) * 86400
            FROM runs
            WHERE end_time IS NOT NULL
        """)
        avg_duration = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_runs': total_runs,
            'status_counts': status_counts,
            'error_counts': error_counts,
            'avg_duration_seconds': avg_duration,
            'success_rate': status_counts.get('success', 0) / total_runs if total_runs > 0 else 0
        }


class ToolExecutionContext:
    """Context manager for tracking tool execution"""
    
    def __init__(self, tracer: ExecutionTracer, tool_name: str, 
                 input_data: Dict[str, Any], start_time: float):
        self.tracer = tracer
        self.tool_name = tool_name
        self.input_data = input_data
        self.start_time = start_time
        self.output_data = None
        self.error = None
    
    def __enter__(self):
        self.tracer.log_step(
            step_type=StepType.TOOL_EXECUTION,
            tool_name=self.tool_name,
            input_data=self.input_data
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type:
            self.error = {
                'type': exc_type.__name__,
                'message': str(exc_val),
                'traceback': traceback.format_exc()
            }
            self.tracer.log_step(
                step_type=StepType.TOOL_ERROR,
                tool_name=self.tool_name,
                error=self.error,
                duration_ms=duration_ms
            )
        else:
            self.tracer.log_step(
                step_type=StepType.TOOL_EXECUTION,
                tool_name=self.tool_name,
                output_data=self.output_data,
                duration_ms=duration_ms
            )
        
        return False  # Don't suppress exceptions 