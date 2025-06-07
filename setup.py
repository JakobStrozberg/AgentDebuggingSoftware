"""
Setup script for CellSight
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cellsight",
    version="0.1.0",
    author="CellSight Team",
    description="Debug and evaluate LLM-powered agents with detailed execution tracing",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/cellsight",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Debuggers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "langchain>=0.1.0",
        "langchain-community>=0.0.10",
        "langchain-openai>=0.0.5",
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "pydantic>=2.0.0",
        "sqlalchemy>=2.0.0",
        "streamlit>=1.28.0",
        "plotly>=5.17.0",
        "pandas>=2.0.0",
        "python-dotenv>=1.0.0",
        "httpx>=0.25.0",
        "pytest>=7.4.0",
        "pytest-asyncio>=0.21.0",
        "rich>=13.6.0",
        "click>=8.1.0",
    ],
    entry_points={
        "console_scripts": [
            "cellsight=cellsight.cli:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "cellsight": ["data/*.json", "dashboard/*.py"],
    },
) 