#!/usr/bin/env python3
"""
Standalone Flinks API Test Script
Test API credentials and endpoints directly without MCP server
"""

import requests
import json
import os
from datetime import datetime

# Load environment variables
def load_env():
    """Load environment variables from .env file"""
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    env_vars[key] = value.strip('"')
    except FileNotFoundError:
        print("❌ .env file not found")
    return env_vars

def test_flinks_api():
    """Test Flinks API with different authentication methods"""
    
    print("🔍 FLINKS API CREDENTIAL TEST")
    print("=" * 50)
    
    # Load credentials
    env_vars = load_env()
    
    print("📋 LOADED CREDENTIALS:")
    print(f"FLINKS_CUSTOMER_ID: {env_vars.get('FLINKS_CUSTOMER_ID', 'NOT SET')}")
    print(f"FLINKS_API_URL: {env_vars.get('FLINKS_API_URL', 'NOT SET')}")
    print(f"FLINKS_BEARER_TOKEN: {env_vars.get('FLINKS_BEARER_TOKEN', 'NOT SET')}")
    print(f"FLINKS_AUTH_KEY: {env_vars.get('FLINKS_AUTH_KEY', 'NOT SET')}")
    print(f"FLINKS_X_API_KEY: {env_vars.get('FLINKS_X_API_KEY', 'NOT SET')}")
    print()
    
    api_url = env_vars.get('FLINKS_API_URL', 'https://toolbox-api.private.fin.ag')
    
    # Test data for connection
    test_payload = {
        'username': 'Greatday',
        'password': 'Greatday',
        'institution': 'FlinksCapital',
        'save': True,
        'schedule_refresh': False
    }
    
    # Test different authentication methods
    auth_methods = [
        {
            'name': 'Bearer Token',
            'headers': {
                'Content-Type': 'application/json',
                'Instance': env_vars.get('FLINKS_CUSTOMER_ID', ''),
                'Authorization': f"Bearer {env_vars.get('FLINKS_BEARER_TOKEN', '')}"
            }
        },
        {
            'name': 'Auth Key',
            'headers': {
                'Content-Type': 'application/json',
                'Instance': env_vars.get('FLINKS_CUSTOMER_ID', ''),
                'Auth-Key': env_vars.get('FLINKS_AUTH_KEY', '')
            }
        },
        {
            'name': 'X-API-Key',
            'headers': {
                'Content-Type': 'application/json',
                'Instance': env_vars.get('FLINKS_CUSTOMER_ID', ''),
                'X-API-Key': env_vars.get('FLINKS_X_API_KEY', '')
            }
        },
        {
            'name': 'All Headers Combined',
            'headers': {
                'Content-Type': 'application/json',
                'Instance': env_vars.get('FLINKS_CUSTOMER_ID', ''),
                'Authorization': f"Bearer {env_vars.get('FLINKS_BEARER_TOKEN', '')}",
                'Auth-Key': env_vars.get('FLINKS_AUTH_KEY', ''),
                'X-API-Key': env_vars.get('FLINKS_X_API_KEY', '')
            }
        }
    ]
    
    # Test endpoints
    endpoints = [
        {
            'name': 'BankingServices/Authorize',
            'url': f"{api_url}/v3/BankingServices/Authorize",
            'method': 'POST',
            'payload': test_payload
        },
        {
            'name': 'BankingServices/GenerateAuthorizeToken',
            'url': f"{api_url}/v3/BankingServices/GenerateAuthorizeToken",
            'method': 'POST',
            'payload': {
                'institution': 'FlinksCapital',
                'username': 'Greatday',
                'password': 'Greatday'
            }
        }
    ]
    
    # Test each combination
    for auth_method in auth_methods:
        print(f"🔐 TESTING AUTHENTICATION: {auth_method['name']}")
        print("-" * 40)
        
        for endpoint in endpoints:
            print(f"📡 Testing endpoint: {endpoint['name']}")
            print(f"   URL: {endpoint['url']}")
            
            try:
                if endpoint['method'] == 'POST':
                    response = requests.post(
                        endpoint['url'],
                        json=endpoint['payload'],
                        headers=auth_method['headers'],
                        timeout=30
                    )
                else:
                    response = requests.get(
                        endpoint['url'],
                        headers=auth_method['headers'],
                        timeout=30
                    )
                
                print(f"   Status Code: {response.status_code}")
                print(f"   Response Headers: {dict(response.headers)}")
                
                # Try to parse JSON response
                try:
                    response_json = response.json()
                    print(f"   Response JSON: {json.dumps(response_json, indent=2)}")
                except:
                    print(f"   Response Text: {response.text[:500]}...")
                
                if response.status_code == 200:
                    print("   ✅ SUCCESS!")
                elif response.status_code == 502:
                    print("   ⚠️  502 Bad Gateway - API server issue")
                elif response.status_code == 401:
                    print("   ❌ 401 Unauthorized - Authentication failed")
                elif response.status_code == 403:
                    print("   ❌ 403 Forbidden - Access denied")
                else:
                    print(f"   ❌ Unexpected status: {response.status_code}")
                    
            except requests.exceptions.Timeout:
                print("   ❌ Request timeout")
            except requests.exceptions.ConnectionError:
                print("   ❌ Connection error")
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
            
            print()
        
        print()
    
    # Test a simple ping/health check if available
    print("🏥 TESTING API HEALTH:")
    print("-" * 30)
    health_endpoints = [
        f"{api_url}/health",
        f"{api_url}/v3/health", 
        f"{api_url}/ping",
        f"{api_url}/status"
    ]
    
    for health_url in health_endpoints:
        try:
            response = requests.get(health_url, timeout=10)
            print(f"   {health_url}: {response.status_code}")
            if response.status_code == 200:
                print(f"      Response: {response.text[:200]}")
        except:
            print(f"   {health_url}: No response")
    
    print("\n" + "=" * 50)
    print("TEST COMPLETE")

if __name__ == "__main__":
    test_flinks_api() 