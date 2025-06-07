"""
LangChain tools for the agent, including API tools and internal tools.
"""

import time
import httpx
import json
from typing import Dict, Any, Optional, Type
from langchain.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field
from cellsight.core.tracer import ExecutionTracer, StepType


# Input schemas for tools
class WeatherInput(BaseModel):
    location: str = Field(description="The location to get weather for")
    units: str = Field(default="celsius", description="Temperature units (celsius or fahrenheit)")


class CustomerInput(BaseModel):
    customer_id: str = Field(description="The customer ID to look up")
    include_history: bool = Field(default=False, description="Whether to include order history")


class SummarizeInput(BaseModel):
    text: str = Field(description="The text to summarize")
    max_length: int = Field(default=100, description="Maximum length of summary in words")


class CalculateInput(BaseModel):
    expression: str = Field(description="Mathematical expression to evaluate")


# Tool implementations
class TracedTool(BaseTool):
    """Base class for tools with execution tracing"""
    
    tracer: Optional[ExecutionTracer] = None
    
    class Config:
        arbitrary_types_allowed = True
    
    def _run(self, *args, **kwargs) -> str:
        """Run the tool with tracing"""
        start_time = time.time()
        
        # Log tool selection
        if self.tracer:
            self.tracer.log_step(
                step_type=StepType.TOOL_SELECTION,
                tool_name=self.name,
                input_data={"args": args, "kwargs": kwargs}
            )
        
        # Execute with tracing
        if self.tracer:
            with self.tracer.log_tool_execution(
                tool_name=self.name,
                input_data={"args": args, "kwargs": kwargs},
                start_time=start_time
            ) as ctx:
                try:
                    result = self._execute(*args, **kwargs)
                    ctx.output_data = {"result": result}
                    return result
                except Exception as e:
                    # Error is logged by context manager
                    raise
        else:
            return self._execute(*args, **kwargs)
    
    def _execute(self, *args, **kwargs) -> str:
        """Actual tool execution - to be implemented by subclasses"""
        raise NotImplementedError
    
    async def _arun(self, *args, **kwargs) -> str:
        """Async version not implemented"""
        raise NotImplementedError("Async execution not supported")


class WeatherTool(TracedTool):
    """Tool for getting weather information from the mock API"""
    
    name: str = "get_weather"
    description: str = "Get current weather information for a location"
    args_schema: Type[BaseModel] = WeatherInput
    api_base_url: str = "http://localhost:8000"
    
    def _execute(self, location: str, units: str = "celsius") -> str:
        """Get weather from the mock API"""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    f"{self.api_base_url}/api/weather",
                    json={"location": location, "units": units}
                )
                response.raise_for_status()
                data = response.json()
                
                return (f"Weather in {data['location']}: "
                       f"{data['temperature']}°{units[0].upper()}, "
                       f"{data['conditions']}, "
                       f"Humidity: {data['humidity']}%")
        
        except httpx.TimeoutException:
            raise Exception("Weather API request timed out")
        except httpx.HTTPStatusError as e:
            raise Exception(f"Weather API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Failed to get weather: {str(e)}")


class CustomerTool(TracedTool):
    """Tool for getting customer information from the mock API"""
    
    name: str = "get_customer"
    description: str = "Get customer information by ID"
    args_schema: Type[BaseModel] = CustomerInput
    api_base_url: str = "http://localhost:8000"
    
    def _execute(self, customer_id: str, include_history: bool = False) -> str:
        """Get customer data from the mock API"""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    f"{self.api_base_url}/api/customer",
                    json={"customer_id": customer_id, "include_history": include_history}
                )
                response.raise_for_status()
                data = response.json()
                
                result = (f"Customer {data['name']} (ID: {data['customer_id']})\n"
                         f"Email: {data['email']}\n"
                         f"Status: {data['status']}\n"
                         f"Total Orders: {data['total_orders']}")
                
                if data.get('last_order'):
                    result += f"\nLast Order: {data['last_order']}"
                
                return result
        
        except httpx.TimeoutException:
            raise Exception("Customer API request timed out")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Exception(f"Customer {customer_id} not found")
            raise Exception(f"Customer API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Failed to get customer data: {str(e)}")


class SummarizeTool(TracedTool):
    """Internal tool for text summarization"""
    
    name: str = "summarize_text"
    description: str = "Summarize a given text to a specified length"
    args_schema: Type[BaseModel] = SummarizeInput
    
    def _execute(self, text: str, max_length: int = 100) -> str:
        """Simple text summarization"""
        # Simulate potential failures
        if len(text) < 10:
            raise ValueError("Text too short to summarize")
        
        if max_length < 10:
            raise ValueError("Maximum length must be at least 10 words")
        
        # Simple word-based truncation (in real scenario, would use NLP)
        words = text.split()
        
        if len(words) <= max_length:
            return text
        
        # Take first max_length words and add ellipsis
        summary = ' '.join(words[:max_length]) + "..."
        
        return f"Summary ({max_length} words): {summary}"


class CalculatorTool(TracedTool):
    """Internal tool for mathematical calculations"""
    
    name: str = "calculate"
    description: str = "Evaluate mathematical expressions"
    args_schema: Type[BaseModel] = CalculateInput
    
    def _execute(self, expression: str) -> str:
        """Evaluate mathematical expression"""
        try:
            # Remove potentially dangerous operations
            if any(op in expression for op in ['import', 'exec', 'eval', '__']):
                raise ValueError("Invalid expression: contains forbidden operations")
            
            # Simple evaluation (in production, use a proper math parser)
            # Only allow basic math operations
            allowed_names = {
                'abs': abs, 'round': round, 'min': min, 'max': max,
                'sum': sum, 'pow': pow, 'len': len
            }
            
            # Evaluate the expression
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            
            return f"Result: {expression} = {result}"
        
        except SyntaxError:
            raise ValueError(f"Invalid mathematical expression: {expression}")
        except ZeroDivisionError:
            raise ValueError("Division by zero error")
        except Exception as e:
            raise ValueError(f"Calculation error: {str(e)}")


def create_tools(tracer: Optional[ExecutionTracer] = None, 
                api_base_url: str = "http://localhost:8000") -> list:
    """Create all available tools with optional tracer"""
    
    # Create tool instances
    weather_tool = WeatherTool()
    weather_tool.tracer = tracer
    weather_tool.api_base_url = api_base_url
    
    customer_tool = CustomerTool()
    customer_tool.tracer = tracer
    customer_tool.api_base_url = api_base_url
    
    summarize_tool = SummarizeTool()
    summarize_tool.tracer = tracer
    
    calculator_tool = CalculatorTool()
    calculator_tool.tracer = tracer
    
    return [weather_tool, customer_tool, summarize_tool, calculator_tool]


# For testing individual tools
if __name__ == "__main__":
    # Test tools without tracing
    tools = create_tools()
    
    # Test weather tool
    weather_tool = tools[0]
    print(weather_tool._execute("London", "celsius"))
    
    # Test calculator
    calc_tool = tools[3]
    print(calc_tool._execute("2 + 2 * 3")) 