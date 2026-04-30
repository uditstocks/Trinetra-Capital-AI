import os
from dotenv import load_dotenv
load_dotenv()
from langchain_nvidia import ChatNVIDIA
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain.agents import create_agent
from langgraph_supervisor import create_supervisor
from langchain_core.tools import tool
import uuid
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage, HumanMessage
from langgraph.types import interrupt
import yfinance as yf
from pprint import pformat
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.types import Command
import json
from datetime import datetime
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from textblob import TextBlob

'''------------------------------------------------------------------------------------------------------------'''

llm = ChatNVIDIA(
    model="nvidia/nemotron-3-super-120b-a12b",
    api_key=os.getenv("NVIDIA_API_KEY"),
    temperature=0,
)

# llm = ChatOllama(model = "llama3.1:8b")

# # deterministic routing
# llm = ChatGroq(
#     model="llama-3.3-70b-versatile",
#     api_key=os.getenv("GROQ_API_KEY"),
#     temperature=0,
# )

'''------------------------------------------------------------------------------------------------------------'''

# ___TOOLS___

@tool("analyze_stock_sentiment")
def analyze_stock_sentiment(ticker: str) -> str:
    """
    Analyzes a stock's technical indicators and news sentiment.
    Computes RSI-14, MACD, Bollinger Bands from price history.
    Scrapes Yahoo Finance headlines and scores them with TextBlob.
    Returns a BUY / SELL / HOLD signal with composite score and ATR-based risk levels.
    Use this when the user asks 'should I buy X?', 'what's the outlook for X?', etc.
    """
    ticker = ticker.upper().strip()
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="30d", interval="1d")
    except Exception as e:
        return f"Error fetching data for {ticker}: {e}"

    if hist.empty or len(hist) < 30:
        return f"Not enough price history for {ticker}."

    close = hist["Close"]
    high  = hist["High"]
    low   = hist["Low"]
    # RSI-14
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
    rsi_series = 100 - (100 / (1 + gain / loss.replace(0, float("nan"))))
    rsi = round(float(rsi_series.iloc[-1]), 2)

    # MACD
    ema12      = close.ewm(span=12, adjust=False).mean()
    ema26      = close.ewm(span=26, adjust=False).mean()
    macd_line  = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram  = round(float((macd_line - signal_line).iloc[-1]), 4)
    macd_cross = "bullish" if histogram > 0 else "bearish"

    # Bollinger Bands %B
    sma20  = close.rolling(20).mean()
    std20  = close.rolling(20).std()
    pct_b  = round(float(((close - (sma20 - 2*std20)) / (4*std20 + 1e-9)).iloc[-1]), 3)

    # ATR-14
    tr  = pd.concat([high-low, (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = round(float(tr.ewm(com=13, min_periods=14).mean().iloc[-1]), 4)

    price = round(float(close.iloc[-1]), 2)

    # News sentiment via BeautifulSoup + TextBlob
    headlines = []
    try:
        url  = f"https://finance.yahoo.com/quote/{ticker}/news/"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup.find_all("h3")[:10]:
            text = tag.get_text(strip=True)
            if len(text) > 20:
                headlines.append(text)
    except Exception:
        pass  # silently skip if scraping fails

    sentiment_scores = [TextBlob(h).sentiment.polarity for h in headlines] if headlines else [0.0]
    avg_sentiment    = round(float(np.mean(sentiment_scores)), 3)
    sentiment_label  = "bullish" if avg_sentiment > 0.15 else "bearish" if avg_sentiment < -0.15 else "neutral"

    # Composite signal score (0–100, baseline 50)
    score = 50
    score += 20 if rsi < 30 else 10 if rsi < 40 else -20 if rsi > 70 else -10 if rsi > 60 else 0
    score += 15 if histogram > 0 else -15
    score += 10 if pct_b < 0.2 else -10 if pct_b > 0.8 else 0
    score += round(avg_sentiment * 15)
    score  = max(0, min(100, score))

    action     = "BUY" if score >= 65 else "SELL" if score <= 35 else "HOLD"
    confidence = "high" if score >= 80 or score <= 20 else "moderate"

    result = {
        "ticker":          ticker,
        "price":           price,
        "rsi":             rsi,
        "rsi_signal":      "oversold" if rsi < 30 else "overbought" if rsi > 70 else "neutral",
        "macd_crossover":  macd_cross,
        "macd_histogram":  histogram,
        "bollinger_pct_b": pct_b,
        "atr":             atr,
        "sentiment_score": avg_sentiment,
        "sentiment_label": sentiment_label,
        "headlines_used":  len(headlines),
        "composite_score": score,
        "signal":          action,
        "confidence":      confidence,
        "stop_loss":       round(price - 1.5 * atr, 2),
        "target_1":        round(price + 2.0 * atr, 2),
        "target_2":        round(price + 3.5 * atr, 2),
    }
    return pformat(result)

# UPDATED LOOKUP_STOCKS_TOOL
@tool("lookup_stocks")
def lookup_stocks_symbol(comany_name: str) -> str:
    """
    Converts a company name to its stock symbol using Yahoo Finance.
    Supports both Indian (NSE/BSE) and US stocks.
    """

    try:
        results = yf.Search(comany_name, max_results = 10).quotes
        if not results:
            return f"Symbol not found {comany_name}."
        
        # if user mentions NSE specifically → prefer .NS
        if "nse" in comany_name.lower():
            for r in results:
                if r.get("symbol", "").endswith(".NS"):
                    return r["symbol"]
           
        # if user mentions BSE specifically → prefer .BO
        if "bse" in comany_name.lower():
            for r in results:
                if r.get("symbol", "").endswith(".BO"):
                    return r["symbol"]
        # default → prefer NSE over BSE over US
        for suffix in [".NS", ".BO"]:
            for r in results:
                if r.get("symbol", "").endswith(suffix):
                    return r["symbol"]


         # fallback to first result
        return results[0]["symbol"]
    
    except Exception as e:
        return f"Error searching for {comany_name}: {str(e)}"


# OLD lookup stock Tool
'''
Advantage: Official and very stable for US/Global markets.
Drawback: Needs an API key and often misses Indian exchange suffixes (NSE/BSE).'''

'''@tool("C")
def lookup_stock_symbol(company_name: str) -> str:
    """
    converts a company name to its stock symbol using a financial API.
    """

    api_url = "https://www.alphavantage.co/query"
    params = {
        "function": "SYMBOL_SEARCH",
        "keywords": company_name,
        "apikey": os.getenv("ALPHA_VANTAGE_KEY")
    }

    response = requests.get(api_url, params = params)
    data = response.json()

    # learning 
    # When you pass params=parameters, the library takes your dictionary and automatically appends it to the URL as a query string, like:
    # https://www.alphavantage.co/query?
    # function=SYMBOL_SEARCH&key_word=Apple&apikey=FWPXO31AYP17JABO

    if "bestMatches" in data and data["bestMatches"]:  # the bestMatch checks Does the key "bestMatches" even exist in the response which is provided in JSON formate 
        return data["bestMatches"][0]["1. symbol"]  
    else:
        return f"symbol not found for {company_name}."'''



@tool("fetch_stock_data")
def fetch_stock_data_raw(stock_symbol: str) -> dict:
    """
    Fetches stock data for a given symbol and returns it as a combined dictionary.
    """

    period = "5d"

    try:
        stock = yf.Ticker(stock_symbol)

        # Retrieve general stock info and historical market data
        info = stock.info
        history = stock.history(period=period)

        combined_data = {
            "stock_symbol": stock_symbol,
            "company_name": info.get("longName"),
            "currency": "INR" if stock_symbol.endswith((".NS", ".BO")) else "USD",
            "sector": info.get("sector"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "latest_price": round(history["Close"].iloc[-1], 2),
            "prev_close": round(history["Close"].iloc[-2], 2),
            "change_pct": round(((history["Close"].iloc[-1] - history["Close"].iloc[-2]) / history["Close"].iloc[-2]) * 100, 2),
            "5d_high": round(history["High"].max(), 2),
            "5d_low": round(history["Low"].min(), 2), 
        }

        return pformat(combined_data)
    
    except Exception as e:
        return {"error": f"ERROR fetching stock data for {stock_symbol}: {str(e)}"}
    

PORTFOLIO_FILE = "portfolio.json"

def load_portfolio():
    if not os.path.exists(PORTFOLIO_FILE):
        return []
    with open(PORTFOLIO_FILE, "r") as f:
        return json.load(f)
    
def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2)


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
    - currency
    - shares
    - limit_price
    - total_spent
    - type: Order type used
    - action

    """
    total_spent = round(int(shares) * limit_price, 2)
    currency = "INR" if symbol.endswith((".NS", ".BO")) else "USD"

    # log the trade
    portfolio = load_portfolio()
    portfolio.append({
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "action": action,
        "currency": currency,
        "shares": int(shares),
        "price": limit_price,
        "total": total_spent
    })
    save_portfolio(portfolio)

    return {
        "status": "filled",
        "symbol": symbol,
        "shares": int(shares),
        "currency": currency,
        "limit_price": limit_price,
        "total_spent": total_spent,
        "type": order_type,
        "action": action
    }

@tool("view_portfolio")
def view_portfolio() -> str:
    """View all current holdings and trade history."""
    portfolio = load_portfolio()
    if not portfolio:
        return "Portfolio is empty."
    return pformat(portfolio)

RISKY_TOOLS = {"place_order"}
interrupt_on = {t: True for t in RISKY_TOOLS}

# ___AGENTS___

research_agent = create_agent(
    model = llm,
    tools = [lookup_stocks_symbol, fetch_stock_data_raw],
    name = "research_agent",
    system_prompt = """
                    You are a stock research expert.
                    STRICT RULE: You MUST always call these tools lookup_stocks tool, fetch_stock_data tool to solve/answer query.
                    NEVER provide stock data without calling these tools!
                    Your job is to lookup stock symbols and fetch real-time market data Using tools
                    Always verify the correct symbol before fetching data.
                    Support US, Indian NSE (.NS) and BSE (.BO) stocks.
                    """
)

trading_agent = create_agent(
    model = llm,
    tools = [place_order, view_portfolio],
    name = "trading_agent",
    system_prompt = """
                    # FOR view PORTFOLIO ORDER please call the tool: view_portfolio (please make tool call), dont check the history, just do tool call please
                    # Your job is to execute buy/sell orders and if ask to show portfolio then use your tool to respond.
                    # STRICT RULE: You MUST always call these tools place_order, view_portfolio tool to solve/answer query
                    # Always use real price data provided by the research agent.
                    # For budget-based orders, round DOWN to nearest whole share.
                    """,
    middleware = [HumanInTheLoopMiddleware(interrupt_on = interrupt_on)]
)

sentiment_agent = create_agent(
    model=llm,
    tools=[analyze_stock_sentiment],
    name="sentiment_agent",
    system_prompt="""
    You are a market sentiment and technical analysis expert.
    STRICT RULE: ALWAYS call the analyze_stock_sentiment tool first — never guess.
    When user asks 'should I buy X?', 'what's the outlook for X?', or 'is X a good buy?':
      1. Call analyze_stock_sentiment with the ticker symbol.
      2. Format the result as:
         📊 TICKER — SIGNAL (confidence)
         Price: X | RSI: X (signal) | MACD: crossover
         Sentiment: label (score, N headlines)
         Composite Score: X/100
         Stop-loss: X | Target 1: X | Target 2: X
         Summary: 2-sentence synthesis.
         ⚠️ Not financial advice.
    """,
)



# __SUPERVISOR__

supervisor = create_supervisor(
    agents = [research_agent, trading_agent,sentiment_agent],
    model = llm,
    prompt = """You are a stock trading supervisor coordinating a research team.
                
                Route tasks as follows:
                - use sentiment_agent for question like should i buy a stock 
                - your employ research_agent will do Stock lookup, price data, market analysis
                - your employ trading_agent will do Buy/sell orders, portfolio view 
                - you are not allowed to use directly. first understand the command then assign the work to the respected agents
                Think step by step before routing.
                """,
    output_mode="last_message",
    add_handoff_messages=False, 
    add_handoff_back_messages=False,
).compile(checkpointer = InMemorySaver())


def print_tool_approval(interrupts):
    for intr in interrupts:
        print("--- Approval needed ---")
        action_requests = intr.value.get("action_requests", [])
        for action in action_requests:
            print(f"Tool: {action['name']}")
            print(f"Description: {action.get('description', '')}")  
            args = action.get("args", {})       
            if args:
                print("Parameters:")
                for k, v in args.items():
                    print(f"  - {k}: {v}")




print("\n🤖 Stock Trading Agent ready! Type 'exit' to quit.\n")

while True:

    command = input("yes sir! what's on your mind: ")

    if command.lower() in ("exit", "quit"):
        print("Jai Mahakal! 🔱")
        break

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    # ── Step 1: Run until interrupt ──
    result = supervisor.invoke(
        {"messages": [HumanMessage(content = command )]},
        config=config,
    )

    interrupts = result.get("__interrupt__", [])

    # ── Step 2: Show interrupt details ──
    print_tool_approval(interrupts)

    # ── Step 3: Approve or Reject ──
    if interrupts:
        user_input = input("\n⚠️ Approve this action? (yes/no): ").strip().lower()

        if user_input == "yes":
            decision = {"type": "approve"}
            print("✅ Order approved. Executing...")

        else:
            decision = {"type": "reject"}
            print("❌ Order rejected.")

        response = supervisor.invoke(Command(resume = {"decisions": [decision]}), config = config)

        response["messages"][-1].pretty_print()

    else:
        # No interrupt happened (no risky tool was called)
        for message in result["messages"]:
            message.pretty_print()




