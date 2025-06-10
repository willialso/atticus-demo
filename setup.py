from setuptools import setup, find_packages

setup(
    name="atticus-demo",
    version="2.2",
    packages=find_packages(),
    install_requires=[
        "fastapi==0.104.1",
        "uvicorn==0.24.0",
        "websockets==11.0.3",
        "numpy==1.24.3",
        "pandas==2.0.3",
        "scipy==1.11.4",
        "python-multipart==0.0.6",
        "requests==2.31.0",
        "scikit-learn==1.3.0",
        "hmmlearn==0.3.0",
        "pytest==7.4.3",
        "pytest-asyncio==0.21.1",
        "pydantic==2.5.0",
        "python-dateutil==2.8.2",
        "aiofiles==23.2.0",
        "websocket-client==1.6.4",
    ],
    python_requires=">=3.9",
) 