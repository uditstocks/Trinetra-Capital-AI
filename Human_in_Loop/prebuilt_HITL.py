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
    
    
@tool("fetch_stock_data")
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
    

@tool("place_order")
def place_order(
symbol: str,
action: str,
shares: int,
limit_price: float,
order_type: str = "limit"
) -> dict:
    
    """
    Execute a stock order.

    Parameters:
    - symbol: Ticker
    - action: "buy" or "sell"
    - shares: Number of shares to trade (pre-computed by the agent)
    - limit_price: Limit price per share
    - order_type: Order type, default "limit"

    Returns:
    - status: Execution result (simulated)
    - symbol
    - shares
    - limit_price
    - total_spent
    - type: Order type used
    - action

    """
    total_spent = round(int(shares) * limit_price, 2)
    return {
        "status": "filled",
        "symbol": symbol,
        "shares": int(shares),
        "limit_price": limit_price,
        "total_spent": total_spent,
        "type": order_type,
        "action": action
    }


# SYSTEM PROMPT

system_message = """
You are an expert stock trading assistant with access to live market tools.

You can: lookup stock symbols, fetch real-time price data, and execute buy/sell orders.

Behavior:
- Always ground decisions in real tool data — never hallucinate prices or symbols.
- Be decisive: if you have enough data, act immediately with tool calls.
- If critical info is missing, ask exactly ONE clarifying question.
- Always assess risk before placing any order.
- Think step-by-step: lookup → analyze → execute.
- For budget-based orders, always round DOWN to nearest whole share and proceed immediately.
"""


# LLM
llm = ChatNVIDIA(
  model="nvidia/nemotron-3-super-120b-a12b",
  api_key="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", 
  temperature=1,
  model_kwargs={
        "chat_template_kwargs": {
            "enable_thinking": True
        }
    }
)




RISKY_TOOLS = {"place_order"}

def halt_on_risky_tools(state):
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        for tc in last.tool_calls:
            if tc.get("name") in RISKY_TOOLS:
                # LangGraph interrupt — pauses the graph and sends this dict to the caller (UI/CLI) so human can approve before executing risky tool
                decision = interrupt({"awaiting": tc["name"], "args": tc.get("args", {})})

                # tool aproved
                if isinstance(decision, dict) and decision.get("approved"):
                    return {}
                
                # tool rejected
                tool_msg = ToolMessage(
                    content = f"Cancelled by human. Continue without executing that tool and provide next steps.",
                    tool_call_id = tc["id"],
                    name = tc["name"]
                )
                return {"messages": [tool_msg]}

    return {}


interrupt_on = {tool: True for tool in RISKY_TOOLS}

agent = create_agent(
    model = llm,
    tools = [lookup_stock_symbol, fetch_stock_data_raw, place_order],
    system_prompt = system_message,
    middleware=[HumanInTheLoopMiddleware(interrupt_on = interrupt_on)],
    checkpointer = InMemorySaver()
             
)


config = {"configurable": {"thread_id": "1"}}

# ── Step 1: Run until interrupt ──
result = agent.invoke(
    {"messages": [HumanMessage(content="Buy $1000 of Apple stock at the current price.")]},
    config=config,
)

interrupts = result.get("__interrupt__", [])

# ── Step 2: Show interrupt details ──
def print_tool_approval(interrupts):
    for intr in interrupts:
        print("--- Approval needed ---")
        action_requests = intr.value.get("action_requests", [])
        for action in action_requests:
            print(f"Tool: {action['name']}")
            args = action.get("arguments", {})
            if args:
                print("Parameters:")
                for k, v in args.items():
                    print(f"  - {k}: {v}")

print_tool_approval(interrupts)

# ── Step 3: Approve or Reject ──

# APPROVE:
response = agent.invoke(
    Command(resume={"decisions": [{"type": "approve"}]}),
    config=config,
)

# REJECT (uncomment to use):
# response = agent.invoke(
#     Command(resume={"decisions": [{"type": "reject", "message": "Too risky."}]}),
#     config=config,
#     version="v2"
# )

for message in response["messages"]:
    message.pretty_print()

