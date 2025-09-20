#!/usr/bin/env python3
"""
Setup script for local PDF processing with Ollama
"""

import subprocess
import sys
import requests
import time
from pathlib import Path

def check_ollama_installed():
    """Check if Ollama is installed"""
    try:
        result = subprocess.run(['ollama', '--version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def check_ollama_running():
    """Check if Ollama service is running"""
    try:
        response = requests.get('http://localhost:11434/api/tags', timeout=5)
        return response.status_code == 200
    except:
        return False

def install_model(model_name="llama3.2"):
    """Install a model in Ollama"""
    print(f"📥 Installing {model_name} model...")
    print("⏳ This may take several minutes for first-time download...")
    
    try:
        result = subprocess.run(['ollama', 'pull', model_name], check=True)
        print(f"✅ {model_name} installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print(f"❌ Failed to install {model_name}")
        return False

def main():
    print("🏠 Rufous Local Processing Setup")
    print("=" * 40)
    
    # Check Ollama installation
    if not check_ollama_installed():
        print("❌ Ollama not installed")
        print("\n📥 Please install Ollama:")
        print("   1. Visit: https://ollama.ai")
        print("   2. Download and install for your OS")
        print("   3. Run this script again")
        return False
    
    print("✅ Ollama installed")
    
    # Check if running
    if not check_ollama_running():
        print("🔄 Starting Ollama service...")
        try:
            # Try to start Ollama
            subprocess.Popen(['ollama', 'serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)  # Wait for startup
            
            if not check_ollama_running():
                print("⚠️  Please start Ollama manually:")
                print("   Run: ollama serve")
                print("   Then run this script again")
                return False
        except:
            print("⚠️  Please start Ollama manually:")
            print("   Run: ollama serve")
            return False
    
    print("✅ Ollama service running")
    
    # Install recommended model
    print("\n🤖 Installing recommended model for financial parsing...")
    if install_model("llama3.2"):
        print("\n🎉 Setup complete!")
        print("\n📄 Usage:")
        print("   python local_statement_processor.py your_statement.pdf")
        print("\n🔒 Privacy: All processing happens locally on your computer")
        return True
    else:
        print("\n⚠️  Model installation failed, but you can try manually:")
        print("   ollama pull llama3.2")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)