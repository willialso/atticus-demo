import subprocess
import sys
import os
import socket

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def test_deployment():
    print("🔍 Testing deployment setup...")
    
    # 1. Test Python version
    python_version = sys.version.split()[0]
    print(f"Python version: {python_version}")
    
    # 2. Test dependencies
    print("\n📦 Testing dependencies...")
    try:
        import fastapi
        print("✅ FastAPI installed")
    except ImportError:
        print("❌ FastAPI not installed")
        return False
        
    try:
        import uvicorn
        print("✅ Uvicorn installed")
    except ImportError:
        print("❌ Uvicorn not installed")
        return False
    
    # 3. Test module imports
    print("\n🔧 Testing module imports...")
    try:
        from backend.api import app
        print("✅ Successfully imported FastAPI app")
    except Exception as e:
        print(f"❌ Failed to import FastAPI app: {e}")
        return False
    
    # 4. Test uvicorn server
    print("\n🚀 Testing uvicorn server...")
    try:
        # Find a free port
        port = find_free_port()
        print(f"Using port: {port}")
        
        # Start uvicorn in a subprocess
        process = subprocess.Popen(
            ["uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait a bit for the server to start
        import time
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is None:
            print("✅ Uvicorn server started successfully")
            process.terminate()
            return True
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Uvicorn server failed to start: {stderr.decode()}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to start uvicorn server: {e}")
        return False

if __name__ == "__main__":
    success = test_deployment()
    if success:
        print("\n✨ All tests passed! Deployment should work.")
    else:
        print("\n❌ Some tests failed. Please fix the issues before deploying.")
        sys.exit(1) 