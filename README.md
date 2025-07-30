# Rufous MCP Server

A **Model Context Protocol (MCP) server** for PDF statement analysis and financial health tracking. This server provides Claude Desktop with powerful financial analysis capabilities by processing uploaded bank statements and credit card statements.

## ✨ Features

- **📄 PDF Statement Processing**: Upload and analyze bank statements, credit card statements, and financial documents
- **🤖 AI-Powered Categorization**: Automatic transaction categorization using Claude's intelligence
- **📊 Financial Analysis**: Spending patterns, category breakdowns, and financial insights
- **💾 Local Data Storage**: All data stays on your device - privacy focused
- **🔧 MCP Integration**: Works seamlessly with Claude Desktop

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Claude Desktop application
- PDF financial statements to analyze

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/rufous.git
   cd rufous
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up configuration**:
   ```bash
   cp env.example .env
   # Edit .env with your preferences (optional - defaults work fine)
   ```

4. **Configure Claude Desktop**:
   Add this to your Claude Desktop configuration file:
   ```json
   {
     "mcpServers": {
       "rufous": {
         "command": "python",
         "args": ["/path/to/your/rufous/rufous_mcp/server.py"]
       }
     }
   }
   ```

## 📊 How It Works

Upload your PDF bank statements to Claude Desktop, and Rufous will:

1. **Extract Transaction Data**: Parse PDF statements to extract transaction details
2. **Categorize Spending**: Automatically categorize transactions (groceries, entertainment, utilities, etc.)
3. **Analyze Patterns**: Identify spending trends and patterns
4. **Generate Insights**: Provide financial health insights and recommendations

```
Claude Desktop ←→ Rufous MCP Server ←→ Local Database ←→ PDF Processing
```

## 🏗️ Architecture

- **MCP Server**: Handles communication with Claude Desktop
- **PDF Processor**: Extracts transaction data from PDF statements
- **Database**: SQLite database for storing transaction data locally
- **Analysis Engine**: Categorizes and analyzes financial data

## ⚙️ Configuration

| Environment Variable | Description | Required | Default |
|---------------------|-------------|----------|---------|
| `RUFOUS_DATABASE_PATH` | Path to SQLite database | No | `~/rufous_data.db` |
| `RUFOUS_STATEMENTS_DIRECTORY` | Directory for uploaded statements | No | `./statements` |
| `RUFOUS_AUTO_CATEGORIZE` | Auto-categorize transactions | No | `true` |
| `RUFOUS_PDF_PROCESSING` | Enable PDF processing | No | `true` |
| `USE_PERSISTENT_STORAGE` | Use persistent storage | No | `false` |
| `SESSION_TIMEOUT_MINUTES` | Session timeout | No | `30` |
| `LOG_LEVEL` | Logging level | No | `INFO` |

## 🏦 Supported Formats

Currently supports PDF statements from major Canadian banks and credit card companies:

- RBC (Royal Bank of Canada)
- TD Bank
- Bank of Montreal (BMO)
- Scotiabank
- CIBC
- And many more...

## 📁 Project Structure

```
rufous/
├── rufous_mcp/
│   ├── __init__.py
│   ├── server.py           # Main MCP server
│   ├── config.py           # Configuration management
│   ├── database.py         # Database operations
│   ├── models.py           # Data models
│   ├── minimal_server.py   # Minimal server implementation
│   └── tools/
│       ├── __init__.py
│       └── base.py         # Base tool class
├── statements/             # Statement storage directory
├── env.example            # Example environment configuration
├── requirements.txt       # Python dependencies
├── setup.py              # Package setup
└── README.md
```

## 🛠️ Development

### Running in Development Mode

```bash
# Start the server directly
python rufous_mcp/server.py

# Or use the minimal server for testing
python rufous_mcp/minimal_server.py
```

### Testing

```bash
# Test the MCP server functionality
python -m pytest tests/

# Test database operations
python view_database.py
```

## 🔒 Privacy & Security

- **Local Processing**: All data processing happens locally on your device
- **No Cloud Upload**: Your financial data never leaves your computer
- **Secure Storage**: Transaction data is stored in a local SQLite database
- **Optional Data Retention**: Configure data retention policies to your preference

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- Create an [Issue](https://github.com/your-username/rufous/issues) for bug reports or feature requests
- Check the [Wiki](https://github.com/your-username/rufous/wiki) for detailed documentation
- Join our community discussions

## 🙏 Acknowledgments

- Built with the [Model Context Protocol](https://github.com/anthropics/mcp) by Anthropic
- Powered by Claude AI for intelligent financial analysis
- Designed for Canadian banking and financial institutions