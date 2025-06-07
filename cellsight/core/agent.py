"""
LangChain agent with integrated tracing for debugging.
"""

import os
from typing import List, Optional, Dict, Any
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.schema import AgentAction, AgentFinish
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema.messages import BaseMessage

from cellsight.core.tracer import ExecutionTracer, StepType
from cellsight.tools.langchain_tools import create_tools


class TracingCallbackHandler(BaseCallbackHandler):
    """Callback handler that integrates with our tracer"""
    
    def __init__(self, tracer: ExecutionTracer):
        self.tracer = tracer
    
    def on_agent_action(self, action: AgentAction, **kwargs) -> None:
        """Log when agent decides to use a tool"""
        self.tracer.log_step(
            step_type=StepType.AGENT_DECISION,
            tool_name=action.tool,
            input_data={
                "tool": action.tool,
                "tool_input": action.tool_input,
                "log": action.log
            }
        )
    
    def on_agent_finish(self, finish: AgentFinish, **kwargs) -> None:
        """Log when agent finishes"""
        self.tracer.log_step(
            step_type=StepType.AGENT_DECISION,
            output_data={
                "output": finish.return_values,
                "log": finish.log
            }
        )


class TracedAgent:
    """LangChain agent with integrated execution tracing"""
    
    def __init__(self, 
                 tracer: ExecutionTracer,
                 model_name: str = "gpt-3.5-turbo",
                 temperature: float = 0.0,
                 api_base_url: str = "http://localhost:8000",
                 verbose: bool = True):
        self.tracer = tracer
        self.model_name = model_name
        self.temperature = temperature
        self.api_base_url = api_base_url
        self.verbose = verbose
        
        # Initialize components
        self._init_llm()
        self._init_tools()
        self._init_agent()
    
    def _init_llm(self):
        """Initialize the language model"""
        # Use OpenAI API key from environment or a dummy key for testing
        api_key = os.getenv("OPENAI_API_KEY", "sk-dummy-key-for-testing")
        
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            api_key=api_key
        )
    
    def _init_tools(self):
        """Initialize tools with tracer"""
        self.tools = create_tools(
            tracer=self.tracer,
            api_base_url=self.api_base_url
        )
    
    def _init_agent(self):
        """Initialize the agent with tools and prompt"""
        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful assistant with access to various tools.
            
Available tools:
- get_weather: Get current weather for a location
- get_customer: Look up customer information by ID
- summarize_text: Summarize long text
- calculate: Perform mathematical calculations

Use these tools to help answer user questions. Be precise and helpful."""),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Create agent
        agent = create_openai_tools_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        # Create executor with tracing callback
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=self.verbose,
            callbacks=[TracingCallbackHandler(self.tracer)],
            handle_parsing_errors=True,
            max_iterations=5
        )
    
    def run(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Run the agent on a query with full tracing"""
        # Start tracing
        run_id = self.tracer.start_run(query, metadata)
        
        try:
            # Execute agent
            result = self.agent_executor.invoke({"input": query})
            
            # End run successfully
            self.tracer.end_run(status="success")
            
            return result["output"]
        
        except Exception as e:
            # End run with error
            self.tracer.end_run(status="failed", error=e)
            raise
    
    async def arun(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Async version of run"""
        # For now, just use sync version
        return self.run(query, metadata)


class MockTracedAgent(TracedAgent):
    """Mock agent for testing without requiring OpenAI API"""
    
    def _init_llm(self):
        """Initialize with a mock LLM for testing"""
        from langchain.llms.fake import FakeListLLM
        
        # Predefined responses for testing
        responses = [
            "I'll help you with that. Let me check the weather.",
            "I'll look up that customer information for you.",
            "I'll summarize that text for you.",
            "I'll calculate that for you.",
            "Based on the information gathered, here's my response."
        ]
        
        self.llm = FakeListLLM(responses=responses)
    
    def run(self, query: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Simplified run for testing"""
        run_id = self.tracer.start_run(query, metadata)
        
        try:
            # Simulate agent behavior based on query
            query_lower = query.lower()
            
            if "weather" in query_lower:
                # Simulate weather tool usage
                self.tracer.log_step(
                    step_type=StepType.AGENT_DECISION,
                    tool_name="get_weather",
                    input_data={"query": query}
                )
                
                # Extract location (simple heuristic)
                location = "London"  # Default
                if "in " in query_lower:
                    location = query.split("in ")[-1].strip("?.")
                
                try:
                    tool = self.tools[0]  # Weather tool
                    result = tool._execute(location)
                    response = f"Based on the weather data: {result}"
                except Exception as e:
                    self.tracer.end_run(status="failed", error=e)
                    raise
            
            elif "customer" in query_lower:
                # Simulate customer tool usage
                self.tracer.log_step(
                    step_type=StepType.AGENT_DECISION,
                    tool_name="get_customer",
                    input_data={"query": query}
                )
                
                # Extract customer ID (simple heuristic)
                import re
                match = re.search(r'\b(\d+)\b', query)
                customer_id = match.group(1) if match else "12345"
                
                try:
                    tool = self.tools[1]  # Customer tool
                    result = tool._execute(customer_id)
                    response = f"Here's the customer information: {result}"
                except Exception as e:
                    self.tracer.end_run(status="failed", error=e)
                    raise
            
            elif "calculate" in query_lower or any(op in query for op in ['+', '-', '*', '/', '=']):
                # Simulate calculator tool usage
                self.tracer.log_step(
                    step_type=StepType.AGENT_DECISION,
                    tool_name="calculate",
                    input_data={"query": query}
                )
                
                # Extract expression (simple heuristic)
                import re
                match = re.search(r'[\d\s\+\-\*\/\(\)\.]+', query)
                expression = match.group(0).strip() if match else "1+1"
                
                try:
                    tool = self.tools[3]  # Calculator tool
                    result = tool._execute(expression)
                    response = result
                except Exception as e:
                    self.tracer.end_run(status="failed", error=e)
                    raise
            
            elif "summarize" in query_lower:
                # Simulate summarize tool usage
                self.tracer.log_step(
                    step_type=StepType.AGENT_DECISION,
                    tool_name="summarize_text",
                    input_data={"query": query}
                )
                
                # Extract text to summarize
                text = query.replace("summarize", "").strip()
                if not text:
                    text = "This is a sample text that needs to be summarized."
                
                try:
                    tool = self.tools[2]  # Summarize tool
                    result = tool._execute(text, max_length=20)
                    response = result
                except Exception as e:
                    self.tracer.end_run(status="failed", error=e)
                    raise
            
            else:
                response = "I understand your query, but I'm not sure which tool to use. Please be more specific."
            
            self.tracer.end_run(status="success")
            return response
        
        except Exception as e:
            self.tracer.end_run(status="failed", error=e)
            raise


def create_agent(tracer: ExecutionTracer, 
                use_mock: bool = False,
                **kwargs) -> TracedAgent:
    """Factory function to create appropriate agent"""
    if use_mock:
        return MockTracedAgent(tracer, **kwargs)
    else:
        return TracedAgent(tracer, **kwargs) 