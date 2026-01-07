import os
import clr
import time
from System import Activator, Reflection

class SterlingConnector:
    def __init__(self):
        self.dll_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "SterlingWrapper",
            "SterlingWrapper.dll"
        )
        if not os.path.exists(self.dll_path):
            raise FileNotFoundError(f"SterlingWrapper.dll not found at {self.dll_path}")

        # Load the assembly once at the start
        self.asm = Reflection.Assembly.LoadFile(self.dll_path)
        self.ConnectorType = self.asm.GetType("SterlingWrapper.Connector")
        if self.ConnectorType is None:
            raise RuntimeError("SterlingWrapper.Connector type not found in DLL")

        self._conn = None
        print("✅ Sterling Connector Module Loaded")

    def _get_conn(self):
        """Internal helper to ensure the COM object is instantiated."""
        if self._conn is None:
            print("🔗 Connecting to Sterling Trader Pro API...")
            try:
                self._conn = Activator.CreateInstance(self.ConnectorType)
            except Exception as e:
                print(f"❌ Failed to instantiate Sterling Wrapper: {e}")
                raise
        return self._conn

    def _execute_with_retry(self, func_name, *args):
        """
        Executes a method. If it fails with an RPC error (0x800706BA), 
        it resets the connection and retries once.
        """
        try:
            conn = self._get_conn()
            method = getattr(conn, func_name)
            return method(*args)
        except Exception as e:
            error_msg = str(e)
            # 0x800706BA is the code for 'The RPC server is unavailable'
            if "800706BA" in error_msg or "RPC" in error_msg:
                print(f"⚠️ RPC Error detected in {func_name}. Sterling may have closed. Retrying...")
                self._conn = None  # Force re-instantiation
                time.sleep(1)      # Short pause for Sterling to stabilize
                
                # Retry once
                conn = self._get_conn()
                method = getattr(conn, func_name)
                return method(*args)
            else:
                # If it's a different error, raise it normally
                print(f"❌ Execution Error in {func_name}: {error_msg}")
                raise

    # === Trading Methods ===
    def send_limit(self, account, ticker, size, disp, route, price, side, tif):
        return self._execute_with_retry("Sendlimit", account, ticker, size, disp, route, price, side, tif)

    def send_market(self, account, ticker, size, disp, route, side, tif):
        return self._execute_with_retry("Sendmarket", account, ticker, size, disp, route, side, tif)

    def send_stop(self, account, ticker, size, disp, route, price, side, tif):
        return self._execute_with_retry("Sendstop", account, ticker, size, disp, route, price, side, tif)

    def send_stoplimit(self, account, ticker, size, disp, route, stp_price, lmt_price, side, tif):
        return self._execute_with_retry("Sendstoplimit", account, ticker, size, disp, route, stp_price, lmt_price, side, tif)

    # === Order Management ===
    def cancel_order(self, account, order_id):
        return self._execute_with_retry("CancelOrder", account, order_id)

    def cancel_all(self, account):
        return self._execute_with_retry("CancellAll", account)

    def cancel_all_symbol(self, symbol, account):
        return self._execute_with_retry("CancellAllSymbol", symbol, account)

    def replace_order(self, order_id, qty, new_price):
        return self._execute_with_retry("ReplaceOrder", order_id, qty, new_price)

    # === Data/Position Methods ===
    def position(self, account, symbol):
        return self._execute_with_retry("Position", account, symbol)

    def position_price(self, account, symbol):
        return self._execute_with_retry("GetPositionPrice", account, symbol)

    def all_positions(self, account):
        return self._execute_with_retry("AllPositions", account)

    def order_status(self, order_id):
        return self._execute_with_retry("OrderStatus", order_id)

    def get_orders(self):
        return self._execute_with_retry("GetOrders")
