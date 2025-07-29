#!/usr/bin/env python3
"""
Rufous MCP Server Setup Script

This script helps users configure their Rufous MCP server environment.
"""

import os
import sys
import json
from pathlib import Path


def print_header():
    """Print the setup header"""
    print("="*60)
    print("🦆 Rufous MCP Server Setup")
    print("Financial Health Tracking for Claude Desktop")
    print("="*60)


def check_python_version():
    """Check if Python version is supported"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    else:
        print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
        return True


def create_env_file():
    """Create .env file from template"""
    env_file = Path(".env")
    env_example = Path("env.example")
    
    if env_file.exists():
        overwrite = input("⚠️  .env file already exists. Overwrite? (y/N): ")
        if overwrite.lower() != 'y':
            print("📝 Skipping .env file creation")
            return
    
    if not env_example.exists():
        print("❌ env.example file not found")
        return
    
    # Copy template
    with open(env_example, 'r') as f:
        content = f.read()
    
    with open(env_file, 'w') as f:
        f.write(content)
    
    print("✅ .env file created from template")
    print("📝 Please edit .env with your Flinks credentials")


def get_flinks_credentials():
    """Get Flinks API credentials from user"""
    print("\n🔑 Flinks API Configuration")
    print("Get your credentials at: https://flinks.com/")
    
    customer_id = input("Enter your Flinks Customer ID: ").strip()
    if not customer_id:
        print("⚠️  Customer ID is required")
        return None
    
    api_url = input("API URL (press Enter for sandbox): ").strip()
    if not api_url:
        api_url = "https://toolbox-api.private.fin.ag/v3"
    
    return {
        "customer_id": customer_id,
        "api_url": api_url
    }


def update_env_file(credentials):
    """Update .env file with credentials"""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("❌ .env file not found")
        return
    
    # Read current content
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    # Update lines
    for i, line in enumerate(lines):
        if line.startswith("FLINKS_CUSTOMER_ID="):
            lines[i] = f"FLINKS_CUSTOMER_ID={credentials['customer_id']}\n"
        elif line.startswith("FLINKS_API_URL="):
            lines[i] = f"FLINKS_API_URL={credentials['api_url']}\n"
    
    # Write updated content
    with open(env_file, 'w') as f:
        f.writelines(lines)
    
    print("✅ .env file updated with credentials")


def find_claude_desktop_config():
    """Find Claude Desktop configuration directory"""
    home = Path.home()
    
    # Common paths for Claude Desktop config
    possible_paths = [
        home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",  # macOS
        home / ".config" / "claude" / "claude_desktop_config.json",  # Linux
        home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",  # Windows
    ]
    
    for path in possible_paths:
        if path.parent.exists():
            return path
    
    return None


def create_claude_config():
    """Create Claude Desktop configuration"""
    print("\n🖥️  Claude Desktop Configuration")
    
    config_path = find_claude_desktop_config()
    if not config_path:
        print("❌ Could not find Claude Desktop configuration directory")
        print("📝 Please manually configure Claude Desktop")
        return
    
    print(f"📍 Config location: {config_path}")
    
    # Get current directory
    current_dir = os.getcwd()
    server_path = os.path.join(current_dir, "rufous_mcp", "server.py")
    
    # Create MCP server configuration
    mcp_config = {
        "mcpServers": {
            "rufous-financial": {
                "command": "python",
                "args": [server_path],
                "env": {
                    "FLINKS_CUSTOMER_ID": "${FLINKS_CUSTOMER_ID}",
                    "FLINKS_API_URL": "${FLINKS_API_URL}"
                }
            }
        }
    }
    
    # Check if config file exists
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                existing_config = json.load(f)
            
            # Merge configurations
            if "mcpServers" in existing_config:
                existing_config["mcpServers"]["rufous-financial"] = mcp_config["mcpServers"]["rufous-financial"]
            else:
                existing_config["mcpServers"] = mcp_config["mcpServers"]
            
            mcp_config = existing_config
        except json.JSONDecodeError:
            print("⚠️  Existing config file is invalid JSON")
    
    # Write configuration
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(mcp_config, f, indent=2)
        
        print("✅ Claude Desktop configuration updated")
        print("🔄 Please restart Claude Desktop to apply changes")
    except Exception as e:
        print(f"❌ Error updating configuration: {e}")


def install_dependencies():
    """Install Python dependencies"""
    print("\n📦 Installing Dependencies")
    
    try:
        import subprocess
        result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Dependencies installed successfully")
        else:
            print("❌ Error installing dependencies:")
            print(result.stderr)
    except Exception as e:
        print(f"❌ Error installing dependencies: {e}")


def print_next_steps():
    """Print next steps for the user"""
    print("\n🎉 Setup Complete!")
    print("\n📋 Next Steps:")
    print("1. Edit .env file with your Flinks credentials")
    print("2. Restart Claude Desktop")
    print("3. Test the connection by asking Claude:")
    print("   'Connect to my bank account using Rufous'")
    print("\n📚 Documentation: See README.md for detailed usage")
    print("🐛 Issues: Report bugs on GitHub")


def main():
    """Main setup function"""
    print_header()
    
    # Check Python version
    if not check_python_version():
        return
    
    # Create .env file
    create_env_file()
    
    # Get credentials
    credentials = get_flinks_credentials()
    if credentials:
        update_env_file(credentials)
    
    # Install dependencies
    install_dependencies()
    
    # Create Claude Desktop config
    create_claude_config()
    
    # Print next steps
    print_next_steps()


if __name__ == "__main__":
    main() 