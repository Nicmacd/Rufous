# Rufous - Financial Health MCP Server

A **Model Context Protocol (MCP) server** for financial health tracking using **Flinks** to connect with Canadian banks. Built as a modern replacement for Mint, this server provides Claude Desktop with powerful financial analysis capabilities.

## 🌟 Features

- **🏦 Bank Connectivity**: Connect to Canadian banks via Flinks API
- **📊 Transaction Analysis**: Fetch and analyze transaction data
- **💰 Spending Insights**: Detailed spending pattern analysis
- **📈 Period Comparisons**: Compare spending across different time periods
- **🏷️ Category Breakdown**: Intelligent expense categorization
- **🎯 Financial Health**: Comprehensive financial health scoring
- **🚨 Smart Alerts**: Automated insights and recommendations

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Claude Desktop
- Flinks API credentials (get them at [flinks.com](https://flinks.com))

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Rufous
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp env.example .env
   # Edit .env with your Flinks credentials
   ```

4. **Configure Claude Desktop:**
   Add to your Claude Desktop MCP settings:
   ```json
   {
     "mcpServers": {
       "rufous-financial": {
         "command": "python",
         "args": ["/path/to/Rufous/rufous_mcp/server.py"],
         "env": {
           "FLINKS_CUSTOMER_ID": "your_customer_id",
           "FLINKS_API_URL": "https://toolbox-api.private.fin.ag/v3"
         }
       }
     }
   }
   ```

## 🛠️ Available Tools

### 1. Connect Bank Account
Connect to Canadian banks securely through Flinks:
```
connect_bank_account(institution="RBC", username="...", password="...")
```

### 2. Fetch Transactions
Retrieve transaction data for analysis:
```
fetch_transactions(login_id="...", days=30)
```

### 3. Analyze Spending
Get detailed spending pattern analysis:
```
analyze_spending(login_id="...", days=30)
```

### 4. Compare Periods
Compare spending across different time periods:
```
compare_periods(login_id="...", current_period_days=30, previous_period_days=30)
```

### 5. Categorize Expenses
Detailed breakdown by spending categories:
```
categorize_expenses(login_id="...", days=30, include_subcategories=false)
```

### 6. Financial Summary
Comprehensive financial health overview:
```
get_financial_summary(login_id="...", days=30, include_comparisons=true)
```

## 💬 Example Usage with Claude

Once configured, you can ask Claude questions like:

- *"Connect to my RBC account and show me my spending for the last month"*
- *"How much did I spend on dining out compared to last month?"*
- *"Give me a complete financial health summary"*
- *"What categories am I spending the most on?"*
- *"Compare my spending this month to last month"*

## 🏗️ Architecture

```
Claude Desktop ←→ Rufous MCP Server ←→ Flinks API ←→ Canadian Banks
                      ↓
                 Data Analysis
                      ↓
              Structured JSON Response
```

### Key Components

- **MCP Server Core**: Handles Claude Desktop communication
- **Flinks Client**: Manages bank connections and data retrieval
- **Analysis Engine**: Processes financial data and generates insights
- **Tools**: Individual MCP tools for specific financial operations

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `FLINKS_CUSTOMER_ID` | Your Flinks Customer ID | Yes | - |
| `FLINKS_API_URL` | Flinks API endpoint | No | Sandbox URL |
| `USE_PERSISTENT_STORAGE` | Enable persistent data storage | No | `false` |
| `SESSION_TIMEOUT_MINUTES` | Session timeout for cached data | No | `30` |
| `LOG_LEVEL` | Logging level | No | `INFO` |
| `MAX_TRANSACTION_DAYS` | Maximum days of transaction history | No | `365` |

### Supported Canadian Banks

- Royal Bank of Canada (RBC)
- Toronto-Dominion Bank (TD)
- Bank of Montreal (BMO)
- Scotiabank
- Canadian Imperial Bank of Commerce (CIBC)
- And many more through Flinks...

## 🔒 Security & Privacy

- **No Credential Storage**: Bank credentials are never stored
- **Session-Based**: Data is cached temporarily for performance
- **Encrypted Transport**: All communications use HTTPS
- **Rate Limited**: Respects API rate limits
- **Minimal Data**: Only retrieves necessary financial data

## 📊 Data Models

### Transaction
```python
{
  "id": "transaction_id",
  "amount": -45.67,
  "date": "2024-01-15T10:30:00Z",
  "description": "Coffee Shop Purchase",
  "category": "Dining",
  "account_id": "account_123"
}
```

### Financial Summary
```python
{
  "overview": {...},
  "spending_analysis": {...},
  "category_insights": {...},
  "financial_health": {...},
  "health_score": 85,
  "recommendations": [...],
  "alerts": [...]
}
```

## 🔧 Development

### Project Structure
```
Rufous/
├── rufous_mcp/
│   ├── __init__.py
│   ├── server.py           # Main MCP server
│   ├── config.py           # Configuration management
│   ├── flinks_client.py    # Flinks API client
│   ├── models.py           # Data models
│   └── tools/              # MCP tools
│       ├── connect_bank.py
│       ├── fetch_transactions.py
│       ├── analyze_spending.py
│       ├── compare_periods.py
│       ├── category_breakdown.py
│       └── financial_summary.py
├── requirements.txt
├── env.example
└── README.md
```

### Running in Development

1. Set up development environment:
   ```bash
   pip install -r requirements.txt
   export FLINKS_CUSTOMER_ID="your_test_id"
   export LOG_LEVEL="DEBUG"
   ```

2. Run the server:
   ```bash
   python rufous_mcp/server.py
   ```

3. Test with Claude Desktop in sandbox mode

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines for details.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Issues**: Use GitHub Issues for bugs and feature requests
- **Documentation**: Check our [Wiki](wiki-link) for detailed guides
- **Community**: Join our [Discord](discord-link) for discussions

## 🔗 Related Projects

- [Flinks API Documentation](https://docs.flinks.com/)
- [Model Context Protocol](https://github.com/modelcontextprotocol)
- [Claude Desktop](https://claude.ai/desktop)

---

**Built with ❤️ for the financial health community**

> **Note**: This project is in active development. Features and APIs may change. Always test in sandbox mode first! 