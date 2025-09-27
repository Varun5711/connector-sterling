import clr
from System import Activator

# Path to your SterlingWrapper.dll
dll_path = r"C:\Users\Administrator\Desktop\connector-sterling\SterlingWrapper\SterlingWrapper.dll"
clr.AddReference(dll_path)

import SterlingWrapper

# Create instance of the .NET connector
conn = SterlingWrapper.Connector()
print("Connector instance created:", conn)

# Example usage:
account = "YOUR_ACCOUNT"    # replace with your live Sterling account ID
symbol = "AAPL"
side = "BUY"
route = "DEFAULT"           # adjust based on your Sterling routes
tif = "DAY"

# Send a market order
order_id = conn.Sendmarket(account, symbol, 100, 0, route, side, tif)
print("Market order id:", order_id)

# Query position
pos = conn.Position(account, symbol)
print("Current position:", pos)

# Cancel order (example)
conn.CancelOrder(account, order_id)
print("Cancelled order", order_id)
