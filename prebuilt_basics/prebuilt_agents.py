'''
ReAct (a generic agent architecture)
act - take an action
observe - grab the response from the action
reason - analyze the response and determine what to do next
'''



# defining tools

import requests
import yfinance as yf
from pprint import pformat

def lookup_stock_symbol(company_name: str) -> str:
    """
    converts a company name to its stock symbol using a financial API.
    """

    api_url = "https://www.alphavantage.co/query"
    params = {
        "function": "SYMBOL_SEARCH",
        "keywords": company_name,
        "apikey": "ENTER_YOUR_APIKEY"
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
    


def fetch_stock_data_raw(stock_symbol: str) -> dict:
    """
    Fetches stock data for a given symbol and returns it as a combined dictionary.
    """

    period = "1mo"

    try:
        stock = yf.Ticker(stock_symbol)

        # Retrieve general stock info and historical market data
        stock_info = stock.info  # basic company and stock data
        stock_history = stock.history(period=period).to_dict()

        combined_data = {
            "stock_symbol": stock_symbol,
            "info": stock_info,
            "history": stock_history 
        }

        return pformat(combined_data)
    
    except Exception as e:
        return {"error": f"ERROR fetching stock data for {stock_symbol}: {str(e)}"}


# Building tools to LLM

from langchain_core.tools import Tool
from langchain_ollama import ChatOllama

'''creating tool bindings with additional attributes'''

lookup_stock = Tool.from_function(
    func = lookup_stock_symbol,
    name = "lookup_stock_symbol",
    description = "Converts a company name to its stock symbol using a financial API.",
    return_direct=False  # Return result to be processed by LLM
)

fetch_stock = Tool.from_function(
    func=fetch_stock_data_raw,
    name="fetch_stock_data_raw",
    description="Fetches comprehensive stock data including general info and historical market data for a given stock symbol.",
    return_direct=False
)

toolbox = [lookup_stock, fetch_stock]

llm = ChatOllama(model = "llama3.1:8b")
llm_with_tools = llm.bind_tools(toolbox)


# Defining Agent Node

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import MessagesState

# System message

assistant_system_message = SystemMessage(content=(""" 

###About you:
You are a friendly, conversational financial assistant. Your role is to help people understand how companies are doing financially.
You can explain things clearly, naturally, and in a relaxed tone, You have access to tools that fetch financial data: stock prices, revenue, profit, analyst sentiment, etc. Use this data to understand the situation                              

###How to respond:
Talk like a person. Say things like: “the stock is up a bit today,” “they’re still making money, but growth has slowed,” or “analysts seem cautious right now.”                                            
Never answer with a bullet list of metrics or a financial report format.
If the user wants more detail, you can go deeper — but only when they ask.
Your job is to make financial information feel easy, human, and open-ended                                                 

"""))

def assistant(state: MessagesState):
    return {"messages": [llm_with_tools.invoke([assistant_system_message] + state["messages"])]}



# Defining Graph

from langgraph.graph import START, StateGraph
from langgraph.prebuilt import tools_condition
from langgraph.prebuilt import ToolNode


# Graph
builder = StateGraph(MessagesState)

# Define nodes: these do the work
builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode(toolbox))

# Define edges: these determine how the control flow moves
builder.add_edge(START, "assistant")
builder.add_conditional_edges("assistant", tools_condition)
builder.add_edge("tools", "assistant")

react_graph = builder.compile()


messages = react_graph.invoke({"messages": [HumanMessage(content= input("ask the question related to stockmarket: "))]})
for messages in messages["messages"]:
    messages.pretty_print()















