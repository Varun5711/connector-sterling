```python -m connector.app```

```Perfect 👍 — let’s translate all those cURL calls into PowerShell Invoke-RestMethod format so you can test them directly.

⸻

1. ✅ Check Positions

Invoke-RestMethod -Uri "http://localhost:5000/positions/DEMOJKST012/AAPL" -Method GET


⸻

2. 🟢 Place a Limit Order

Invoke-RestMethod -Uri "http://localhost:5000/order" -Method POST -ContentType "application/json" -Body '{
  "account": "DEMOJKST012",
  "symbol": "AAPL",
  "ord_size": 1,
  "ord_disp": 1,
  "ord_route": "EDGX",
  "ord_price": 255.00,
  "ord_side": "B",
  "ord_tif": "D"
}'


⸻

3. 🔴 Place a Market Order (using ARCA to avoid -56 rejection in demo)

Invoke-RestMethod -Uri "http://localhost:5000/order/market" -Method POST -ContentType "application/json" -Body '{
  "account": "DEMOJKST012",
  "symbol": "AAPL",
  "ord_size": 1,
  "ord_disp": 0,
  "ord_route": "ARCA",
  "ord_side": "S",
  "ord_tif": "D"
}'


⸻

4. 🟡 Cancel an Order

Invoke-RestMethod -Uri "http://localhost:5000/order" -Method DELETE -ContentType "application/json" -Body '{
  "account": "DEMOJKST012",
  "order_id": "AAPLBMKT270935"
}'


⸻

5. 🟣 Get Order Status

Invoke-RestMethod -Uri "http://localhost:5000/order/status/AAPLBMKT270935" -Method GET


⸻

6. 🔵 Get All Open Orders

Invoke-RestMethod -Uri "http://localhost:5000/orders" -Method GET


⸻

⚡Tip: Replace AAPLBMKT270935 with whatever order_id you actually get back from the limit or market order responses.

Would you like me to bundle all of these into a single PowerShell script (test_end_to_end.ps1) so you can run it in one go and see the whole flow (place → check → cancel → re-check)?```
