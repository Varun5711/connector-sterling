# connector/sterling_connector.py
import os
import clr
from System import Activator, Reflection


class SterlingConnector:
    def __init__(self):
        dll_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),  # go up one dir from connector/
            "SterlingWrapper",
            "SterlingWrapper.dll"
        )
        if not os.path.exists(dll_path):
            raise FileNotFoundError("SterlingWrapper.dll not found at " + dll_path)

        asm = Reflection.Assembly.LoadFile(dll_path)
        ConnectorType = asm.GetType("SterlingWrapper.Connector")
        if ConnectorType is None:
            raise RuntimeError("SterlingWrapper.Connector type not found in DLL")

        self.conn = Activator.CreateInstance(ConnectorType)

    # === wrapper methods ===
    def send_limit(self, account, ticker, size, disp, route, price, side, tif):
        return self.conn.Sendlimit(account, ticker, size, disp, route, price, side, tif)

    def send_market(self, account, ticker, size, disp, route, side, tif):
        return self.conn.Sendmarket(account, ticker, size, disp, route, side, tif)

    def send_stop(self, account, ticker, size, disp, route, price, side, tif):
        return self.conn.Sendstop(account, ticker, size, disp, route, price, side, tif)

    def send_stoplimit(self, account, ticker, size, disp, route, stp_price, lmt_price, side, tif):
        return self.conn.Sendstoplimit(account, ticker, size, disp, route, stp_price, lmt_price, side, tif)

    def cancel_order(self, account, order_id):
        return self.conn.CancelOrder(account, order_id)

    def cancel_all(self, account):
        return self.conn.CancellAll(account)

    def cancel_all_symbol(self, symbol, account):
        return self.conn.CancellAllSymbol(symbol, account)

    def replace_order(self, order_id, qty, new_price):
        return self.conn.ReplaceOrder(order_id, qty, new_price)

    def position(self, account, symbol):
        return self.conn.Position(account, symbol)

    def position_price(self, account, symbol):
        return self.conn.GetPositionPrice(account, symbol)

    def all_positions(self, account):
        return self.conn.AllPositions(account)

    def order_status(self, order_id):
        return self.conn.OrderStatus(order_id)

    def get_orders(self):
        return self.conn.GetOrders()
