"""
Mock API server simulating external SaaS tools with configurable failure scenarios.
"""

import random
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import uvicorn


class WeatherRequest(BaseModel):
    location: str
    units: str = "celsius"


class WeatherResponse(BaseModel):
    location: str
    temperature: float
    conditions: str
    humidity: int
    timestamp: str


class CustomerRequest(BaseModel):
    customer_id: str
    include_history: bool = False


class CustomerResponse(BaseModel):
    customer_id: str
    name: str
    email: str
    status: str
    created_at: str
    last_order: Optional[str] = None
    total_orders: int = 0


class MockAPIConfig:
    """Configuration for mock API behavior"""
    def __init__(self):
        self.failure_rate = 0.2  # 20% chance of failure
        self.timeout_rate = 0.1  # 10% chance of timeout
        self.invalid_response_rate = 0.05  # 5% chance of invalid response
        self.min_delay_ms = 100
        self.max_delay_ms = 500
        self.timeout_delay_ms = 5000


app = FastAPI(title="Mock SaaS API", version="1.0.0")
config = MockAPIConfig()


async def simulate_delay():
    """Simulate API processing delay"""
    delay = random.randint(config.min_delay_ms, config.max_delay_ms) / 1000
    await asyncio.sleep(delay)


async def maybe_fail():
    """Randomly fail based on configuration"""
    rand = random.random()
    
    if rand < config.timeout_rate:
        # Simulate timeout
        await asyncio.sleep(config.timeout_delay_ms / 1000)
        raise HTTPException(status_code=504, detail="Gateway timeout")
    
    elif rand < (config.timeout_rate + config.failure_rate):
        # Simulate various API errors
        error_scenarios = [
            (500, "Internal server error"),
            (503, "Service temporarily unavailable"),
            (429, "Rate limit exceeded"),
            (401, "Invalid API key"),
            (400, "Bad request: Invalid parameters")
        ]
        status_code, detail = random.choice(error_scenarios)
        raise HTTPException(status_code=status_code, detail=detail)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Mock SaaS API"}


@app.post("/api/weather", response_model=WeatherResponse)
async def get_weather(request: WeatherRequest):
    """Mock weather API endpoint"""
    await simulate_delay()
    await maybe_fail()
    
    # Sometimes return invalid data
    if random.random() < config.invalid_response_rate:
        return {
            "location": request.location,
            "temperature": "invalid",  # This will cause validation error
            "conditions": None,
            "humidity": -1,
            "timestamp": datetime.now().isoformat()
        }
    
    # Normal response
    weather_conditions = ["sunny", "cloudy", "rainy", "stormy", "foggy", "snowy"]
    
    return WeatherResponse(
        location=request.location,
        temperature=round(random.uniform(-10, 35), 1),
        conditions=random.choice(weather_conditions),
        humidity=random.randint(30, 90),
        timestamp=datetime.now().isoformat()
    )


@app.post("/api/customer", response_model=CustomerResponse)
async def get_customer(request: CustomerRequest):
    """Mock customer data API endpoint"""
    await simulate_delay()
    await maybe_fail()
    
    # Simulate customer not found
    if request.customer_id.startswith("invalid"):
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Sometimes return incomplete data
    if random.random() < config.invalid_response_rate:
        return CustomerResponse(
            customer_id=request.customer_id,
            name="",  # Empty name
            email="invalid-email",  # Invalid email format
            status="unknown",
            created_at=datetime.now().isoformat(),
            total_orders=-1  # Invalid order count
        )
    
    # Normal response
    customer_names = ["John Doe", "Jane Smith", "Bob Johnson", "Alice Brown"]
    statuses = ["active", "inactive", "premium", "suspended"]
    
    response = CustomerResponse(
        customer_id=request.customer_id,
        name=random.choice(customer_names),
        email=f"customer{request.customer_id}@example.com",
        status=random.choice(statuses),
        created_at=datetime(2023, random.randint(1, 12), random.randint(1, 28)).isoformat(),
        total_orders=random.randint(0, 100)
    )
    
    if request.include_history:
        response.last_order = datetime(2024, random.randint(1, 12), random.randint(1, 28)).isoformat()
    
    return response


@app.post("/api/config")
async def update_config(
    failure_rate: Optional[float] = None,
    timeout_rate: Optional[float] = None,
    invalid_response_rate: Optional[float] = None,
    min_delay_ms: Optional[int] = None,
    max_delay_ms: Optional[int] = None,
    timeout_delay_ms: Optional[int] = None
):
    """Update mock API configuration for testing different scenarios"""
    if failure_rate is not None:
        config.failure_rate = max(0, min(1, failure_rate))
    if timeout_rate is not None:
        config.timeout_rate = max(0, min(1, timeout_rate))
    if invalid_response_rate is not None:
        config.invalid_response_rate = max(0, min(1, invalid_response_rate))
    if min_delay_ms is not None:
        config.min_delay_ms = max(0, min_delay_ms)
    if max_delay_ms is not None:
        config.max_delay_ms = max(config.min_delay_ms, max_delay_ms)
    if timeout_delay_ms is not None:
        config.timeout_delay_ms = max(0, timeout_delay_ms)
    
    return {
        "failure_rate": config.failure_rate,
        "timeout_rate": config.timeout_rate,
        "invalid_response_rate": config.invalid_response_rate,
        "min_delay_ms": config.min_delay_ms,
        "max_delay_ms": config.max_delay_ms,
        "timeout_delay_ms": config.timeout_delay_ms
    }


@app.get("/api/config")
async def get_config():
    """Get current mock API configuration"""
    return {
        "failure_rate": config.failure_rate,
        "timeout_rate": config.timeout_rate,
        "invalid_response_rate": config.invalid_response_rate,
        "min_delay_ms": config.min_delay_ms,
        "max_delay_ms": config.max_delay_ms,
        "timeout_delay_ms": config.timeout_delay_ms
    }


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the mock API server"""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server() 