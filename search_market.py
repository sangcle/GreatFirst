import ccxt 

binance = ccxt.binance()
markets= binance.load_markets()

print(markets.keys())
print(len(markets))