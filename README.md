# Rufous MCP Server

A **Model Context Protocol (MCP) server** for PDF statement analysis and financial transaction storage. This server provides Claude Desktop with the ability to extract transaction data from PDF bank statements and store it locally for analysis.

## ✨ Current Features

- **📄 Transaction Storage**: Store transaction data extracted by Claude from PDF statements  
- **🔍 Transaction Retrieval**: Search and retrieve stored transactions from local database
- **💾 Local SQLite Database**: All financial data stays on your device - privacy focused
- **🔧 MCP Integration**: Works seamlessly with Claude Desktop
- **🏦 Multi-Account Support**: Handle both debit and credit account statements

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

3. **Set up configuration** (optional):
   ```bash
   cp env.example .env
   # Edit .env with your preferences - defaults work fine for most users
   ```

4. **Configure Claude Desktop**:
   Add this to your Claude Desktop configuration file (`claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "rufous": {
         "command": "python",
         "args": ["/path/to/your/rufous/rufous_mcp/minimal_server.py"]
       }
     }
   }
   ```

## 📊 How It Works

1. **Upload PDF**: Share a PDF bank statement with Claude Desktop
2. **Claude Extracts**: Claude automatically extracts transaction data from the PDF
3. **Store Data**: Claude calls the `store_transactions` tool to save data locally
4. **Query Data**: Use the `get_transactions` tool to search and analyze your data

## 🛠️ Available Tools

### `store_transactions`
Stores transaction data extracted by Claude from PDF statements.

**Parameters:**
- `statement_filename`: Name of the PDF file being processed
- `account_type`: Either "debit" or "credit"  
- `statement_date`: Date of the statement (optional)
- `transactions`: Array of transaction objects with date, description, amount, balance

### `get_transactions`  
Retrieves stored transactions with optional filtering.

**Parameters:**
- `search_term`: Search in transaction descriptions (optional)
- `start_date`: Filter transactions from this date (optional)
- `end_date`: Filter transactions until this date (optional)
- `account_type`: Filter by account type (optional)
- `limit`: Maximum number of results (default: 100)

## 🏗️ Architecture

```
Claude Desktop ←→ Rufous MCP Server ←→ Local SQLite Database
```

- **MCP Server**: Handles communication with Claude Desktop (`minimal_server.py`)
- **Database**: SQLite database for storing transaction data locally (`database.py`)
- **Config**: Environment-based configuration (`config.py`)

## ⚙️ Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `RUFOUS_DATABASE_PATH` | Path to SQLite database | `~/rufous_data.db` |
| `RUFOUS_STATEMENTS_DIRECTORY` | Directory for uploaded statements | `./statements` |
| `USE_PERSISTENT_STORAGE` | Use persistent storage | `false` |
| `SESSION_TIMEOUT_MINUTES` | Session timeout | `30` |
| `LOG_LEVEL` | Logging level | `INFO` |

## 📁 Project Structure

```
rufous/
├── rufous_mcp/
│   ├── __init__.py
│   ├── minimal_server.py   # Main MCP server
│   ├── config.py           # Configuration management  
│   └── database.py         # SQLite database operations
├── statements/             # Statement storage directory (created automatically)
├── view_database.py        # Database inspection utility
├── env.example            # Example environment configuration
├── requirements.txt       # Python dependencies
├── setup.py              # Package setup
└── README.md
```

## 🛠️ Development & Usage

### Running the Server
```bash
# Start the MCP server directly for testing
python rufous_mcp/minimal_server.py
```

### Viewing Your Data
```bash
# Inspect stored transactions  
python view_database.py
```

### Example Workflow
1. Upload a PDF bank statement to Claude Desktop
2. Ask Claude: "Extract the transactions from this statement and store them"
3. Claude will use the `store_transactions` tool automatically
4. Query your data: "Show me all transactions from last month"
5. Claude will use the `get_transactions` tool to retrieve results

## 🔒 Privacy & Security

- **100% Local**: All transaction data stays on your device
- **No Cloud Upload**: Financial data never leaves your computer  
- **SQLite Storage**: Lightweight, file-based database
- **Open Source**: Full transparency of data handling

## 📊 Database Schema

**Transactions Table:**
- `id`, `date`, `description`, `amount`, `balance`
- `account_type` (debit/credit), `category`, `statement_file`
- Indexed for fast searching by date, description, category

**Statements Table:**  
- Tracks processed PDF files to avoid duplicates
- `filename`, `statement_date`, `account_type`, `transaction_count`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`  
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 🔮 Future Enhancements

- Automatic transaction categorization using Claude
- Spending pattern analysis and insights  
- Multi-bank format support improvements
- Data export capabilities
- Advanced filtering and reporting

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- Create an [Issue](https://github.com/your-username/rufous/issues) for bug reports or feature requests
- Check the database with `python view_database.py` if you have data issues

## 🙏 Acknowledgments

- Built with the [Model Context Protocol](https://github.com/anthropics/mcp) by Anthropic
- Powered by Claude AI for intelligent PDF processing
- Designed for privacy-conscious financial data management