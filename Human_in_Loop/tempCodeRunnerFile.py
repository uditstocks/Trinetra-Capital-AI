import requests
from langchain_nvidia import ChatNVIDIA
from langchain.agents import create_agent
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, HumanMessage
from langgraph.types import interrupt
import yfinance as yf
from pprint import pformat
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.types import Command

# DEFINING TOOLS

@tool("lookup_stocks")
def lookup_stock_symbol(company_name: str) -> str:
    """
    converts a company name to its stock symbol using a financial API.
    """

    api_url = "https://www.alphavantage.co/query"
    params = {
        "function": "SYMBOL_SEARCH",
        "keywords": company_name,
        "apikey": "FWPXO31AYP17JABO"
    }

    response = requests.get(api_url, params = params)
    data = response.json()

    # learning 
    '''When you pass params=parameters, the library takes your dictionary and automatically appends it to the URL as a query string, like:
    https://www.alphavantage.co/query?
    function=SYMBOL_SEARCH&key_word=Apple&apikey=FWPXO31AYP17JABO'''

    if "bestMatches" in data and data["bestMatches"]:  # the bestMatch checks Does the key "bestMatches" even exist in the response which is provided in JSON formate 
        return data["bestMatches"][0]["1. symbol"]  
    else:
        return f"symbol not found for {company_name}."
    
result = lookup_stock_symbol.invoke("Tesla")
print(result)