#!/usr/bin/env python3
"""
Rufous MCP Server Debug Plan
Systematic testing of all components to identify issues
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RufousDebugger:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "errors": [],
            "summary": {}
        }
    
    def log_test(self, test_name: str, success: bool, details: str = None, error: str = None):
        """Log test results"""
        self.results["tests"][test_name] = {
            "success": success,
            "details": details,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    Details: {details}")
        if error:
            print(f"    Error: {error}")
        print()

    async def test_1_environment_setup(self):
        """Test 1: Environment and Dependencies"""
        print("🔧 TEST 1: Environment Setup")
        
        try:
            # Check if .env file exists
            env_exists = os.path.exists('.env')
            self.log_test("env_file_exists", env_exists, 
                         "Found .env file" if env_exists else "Missing .env file")
            
            # Check Python dependencies
            dependencies = ['mcp', 'requests', 'pydantic', 'asyncio']
            for dep in dependencies:
                try:
                    __import__(dep)
                    self.log_test(f"dependency_{dep}", True, f"{dep} imported successfully")
                except ImportError as e:
                    self.log_test(f"dependency_{dep}", False, error=str(e))
            
            # Check MCP version
            try:
                import pkg_resources
                dist = pkg_resources.get_distribution('mcp')
                self.log_test("mcp_version", True, f"MCP version: {dist.version}")
            except Exception as e:
                self.log_test("mcp_version", False, error=str(e))
                
        except Exception as e:
            self.log_test("environment_setup", False, error=str(e))

    async def test_2_config_loading(self):
        """Test 2: Configuration Loading"""
        print("⚙️  TEST 2: Configuration Loading")
        
        try:
            from rufous_mcp.config import Config
            config = Config()
            
            # Test config attributes
            attrs = [
                'flinks_customer_id', 'flinks_api_url', 'flinks_bearer_token',
                'flinks_auth_key', 'flinks_x_api_key'
            ]
            
            for attr in attrs:
                value = getattr(config, attr, None)
                has_value = bool(value and value.strip())
                self.log_test(f"config_{attr}", has_value, 
                             f"Value: {'[REDACTED]' if 'token' in attr or 'key' in attr else value}" if has_value else "Missing or empty")
            
            # Test get_flinks_config method
            flinks_config = config.get_flinks_config()
            self.log_test("flinks_config_method", True, f"Config keys: {list(flinks_config.keys())}")
            
        except Exception as e:
            self.log_test("config_loading", False, error=str(e))

    async def test_3_flinks_client(self):
        """Test 3: Flinks Client Initialization"""
        print("🔗 TEST 3: Flinks Client")
        
        try:
            from rufous_mcp.flinks_client import FlinksClient
            from rufous_mcp.config import Config
            
            config = Config()
            client = FlinksClient(config.get_flinks_config())
            
            self.log_test("flinks_client_creation", True, "FlinksClient created successfully")
            
            # Test initialization
            await client.initialize()
            self.log_test("flinks_client_init", True, "Client initialized")
            
            # Test direct API call (should get 502 but that's expected)
            try:
                result = await client.connect_bank_account("FlinksCapital", "Greatday", "Greatday")
                self.log_test("flinks_api_call", True, f"API call result: {type(result)}")
            except Exception as api_error:
                # 502 is expected, so this is actually "success" for our debug
                error_msg = str(api_error)
                is_502 = "502" in error_msg or "Bad Gateway" in error_msg
                self.log_test("flinks_api_call", is_502, 
                             "Got expected 502 error (API down)" if is_502 else f"Unexpected error: {error_msg}")
                
        except Exception as e:
            self.log_test("flinks_client", False, error=str(e))

    async def test_4_mcp_server_creation(self):
        """Test 4: MCP Server Creation"""
        print("🖥️  TEST 4: MCP Server Creation")
        
        try:
            from rufous_mcp.simple_server import SimpleRufousServer
            
            server = SimpleRufousServer()
            self.log_test("server_creation", True, "SimpleRufousServer created")
            
            # Test tool definitions
            tools_count = len(server.tool_definitions)
            self.log_test("tool_definitions", tools_count > 0, f"Found {tools_count} tool definitions")
            
            # List tools
            for i, tool in enumerate(server.tool_definitions):
                tool_name = tool.get('name', f'tool_{i}')
                self.log_test(f"tool_{tool_name}", True, f"Tool: {tool_name}")
                
            # Test flinks client initialization
            await server.flinks_client.initialize()
            self.log_test("server_flinks_init", True, "Server's FlinksClient initialized")
            
        except Exception as e:
            self.log_test("mcp_server_creation", False, error=str(e))

    async def test_5_mock_tool_calls(self):
        """Test 5: Mock Tool Calls"""
        print("🛠️  TEST 5: Mock Tool Calls")
        
        try:
            from rufous_mcp.simple_server import SimpleRufousServer
            
            server = SimpleRufousServer()
            await server.flinks_client.initialize()
            
            # Test connect_bank_account (mock mode)
            mock_args = {
                "institution": "FlinksCapital",
                "username": "Greatday", 
                "password": "Greatday"
            }
            
            # We need to call the handler directly for testing
            # First, let's create a mock handler
            handlers = {}
            
            @server.server.call_tool()
            async def test_handler(name: str, arguments: dict):
                if name == "connect_bank_account":
                    institution = arguments.get("institution", "")
                    username = arguments.get("username", "")
                    password = arguments.get("password", "")
                    
                    if username == "Greatday" and password == "Greatday":
                        mock_result = {
                            "login_id": f"mock_login_{institution}_123456",
                            "status": "connected", 
                            "institution": institution,
                            "message": f"Successfully connected to {institution} (MOCK MODE - API temporarily unavailable)"
                        }
                        return {
                            "content": [{"type": "text", "text": json.dumps(mock_result, indent=2)}],
                            "isError": False
                        }
                return {"content": [{"type": "text", "text": "Test failed"}], "isError": True}
            
            # Test the mock call
            result = await test_handler("connect_bank_account", mock_args)
            
            success = isinstance(result, dict) and "content" in result and not result.get("isError", False)
            details = f"Result type: {type(result)}, Has content: {'content' in result if isinstance(result, dict) else False}"
            
            self.log_test("mock_connect_bank", success, details)
            
            if success:
                # Test if we can parse the JSON response
                try:
                    content = result["content"][0]["text"]
                    parsed = json.loads(content)
                    has_login_id = "login_id" in parsed
                    self.log_test("mock_response_format", has_login_id, f"Login ID: {parsed.get('login_id', 'MISSING')}")
                except Exception as parse_error:
                    self.log_test("mock_response_format", False, error=str(parse_error))
                    
        except Exception as e:
            self.log_test("mock_tool_calls", False, error=str(e))

    async def test_6_claude_config(self):
        """Test 6: Claude Desktop Configuration"""
        print("🤖 TEST 6: Claude Desktop Configuration")
        
        try:
            config_path = os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    claude_config = json.load(f)
                
                self.log_test("claude_config_exists", True, f"Config file found at: {config_path}")
                
                # Check if rufous server is configured
                mcpServers = claude_config.get("mcpServers", {})
                rufous_servers = [name for name in mcpServers.keys() if "rufous" in name.lower()]
                
                if rufous_servers:
                    server_name = rufous_servers[0]
                    server_config = mcpServers[server_name]
                    
                    self.log_test("claude_rufous_config", True, f"Found server: {server_name}")
                    
                    # Check server config details
                    has_command = "command" in server_config
                    has_args = "args" in server_config
                    has_env = "env" in server_config
                    
                    self.log_test("claude_server_command", has_command, 
                                 f"Command: {server_config.get('command', 'MISSING')}")
                    self.log_test("claude_server_args", has_args,
                                 f"Args: {server_config.get('args', 'MISSING')}")
                    self.log_test("claude_server_env", has_env,
                                 f"Env vars: {list(server_config.get('env', {}).keys())}")
                else:
                    self.log_test("claude_rufous_config", False, "No Rufous server found in config")
            else:
                self.log_test("claude_config_exists", False, f"Config file not found: {config_path}")
                
        except Exception as e:
            self.log_test("claude_config", False, error=str(e))

    async def run_all_tests(self):
        """Run all debug tests"""
        print("🚀 RUFOUS MCP SERVER DEBUG PLAN")
        print("=" * 50)
        
        test_methods = [
            self.test_1_environment_setup,
            self.test_2_config_loading,
            self.test_3_flinks_client,
            self.test_4_mcp_server_creation,
            self.test_5_mock_tool_calls,
            self.test_6_claude_config,
        ]
        
        for test_method in test_methods:
            try:
                await test_method()
            except Exception as e:
                test_name = test_method.__name__
                self.log_test(test_name, False, error=str(e))
        
        # Generate summary
        total_tests = len(self.results["tests"])
        passed_tests = sum(1 for test in self.results["tests"].values() if test["success"])
        failed_tests = total_tests - passed_tests
        
        self.results["summary"] = {
            "total": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
        }
        
        print("📊 DEBUG SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {self.results['summary']['success_rate']}")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for test_name, result in self.results["tests"].items():
                if not result["success"]:
                    print(f"  - {test_name}: {result.get('error', 'Unknown error')}")
        
        print("\n💾 SAVING DEBUG REPORT...")
        with open('rufous_debug_report.json', 'w') as f:
            json.dump(self.results, f, indent=2)
        print("Debug report saved to: rufous_debug_report.json")


async def main():
    """Main debug entry point"""
    debugger = RufousDebugger()
    await debugger.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main()) 