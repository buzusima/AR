import MetaTrader5 as mt5
import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import os
import sys

class MT5Connection:
    def __init__(self, config_path: str = "config.json"):
        """Initialize MT5 Connection Manager - Auto-detect logged in account"""
        self.config = self.load_config(config_path)
        self.connected = False
        self.account_info = None
        self.positions = []
        self.balance = 0.0
        self.equity = 0.0
        self.margin = 0.0
        self.free_margin = 0.0
        self.last_update = None
        self.connection_thread = None
        self.running = False
        
        # Setup logging
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        
        # Create logs directory if not exists
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/mt5_connection.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
    def load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        try:
            if not os.path.exists(config_path):
                print(f"⚠️ Config file not found: {config_path}")
                print("Creating minimal config.json...")
                self.create_minimal_config(config_path)
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"✅ Config loaded from {config_path}")
                return config
                
        except Exception as e:
            print(f"⚠️ Error loading config: {e}")
            return self.get_minimal_config()
    
    def create_minimal_config(self, config_path: str):
        """Create minimal configuration file (no login needed)"""
        minimal_config = self.get_minimal_config()
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(minimal_config, f, indent=2)
            print(f"✅ Created minimal config: {config_path}")
        except Exception as e:
            print(f"❌ Failed to create config: {e}")
    
    def get_minimal_config(self) -> dict:
        """Get minimal configuration (auto-detect account)"""
        return {
            "mt5": {
                "auto_detect_account": True,
                "timeout": 60000
            },
            "position_sizing": {
                "risk_percent": 2.0,
                "max_lot_size": 1.0,
                "min_lot_size": 0.01,
                "dynamic_sizing": True
            },
            "arbitrage": {
                "currency_pairs": [
                    "EURUSD", "GBPUSD", "EURGBP",
                    "USDJPY", "EURJPY", "GBPJPY"
                ],
                "min_profit_pips": 5,
                "scan_interval_ms": 500
            },
            "logging": {
                "level": "INFO"
            }
        }
    
    def connect(self) -> bool:
        """Connect to MT5 Terminal and auto-detect logged in account"""
        try:
            print("🔌 Connecting to MT5 Terminal...")
            
            # Check if MetaTrader5 module is available
            try:
                import MetaTrader5 as mt5
                print("✅ MetaTrader5 module available")
            except ImportError as e:
                print(f"❌ MetaTrader5 module not found: {e}")
                print("💡 Install with: pip install MetaTrader5")
                return False
            
            # Initialize MT5 connection
            print("🔄 Initializing MT5...")
            if not mt5.initialize():
                # Try common installation paths
                common_paths = [
                    r"C:\Program Files\MetaTrader 5\terminal64.exe",
                    r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe"
                ]
                
                for path in common_paths:
                    if os.path.exists(path):
                        print(f"🔄 Trying path: {path}")
                        if mt5.initialize(path):
                            break
                else:
                    error = mt5.last_error()
                    print(f"❌ MT5 initialize failed: {error}")
                    print("💡 Make sure MT5 Terminal is running and try again")
                    return False
            
            print("✅ MT5 initialized successfully")
            self.connected = True
            
            # Get terminal info
            terminal_info = mt5.terminal_info()
            if terminal_info:
                print(f"📊 Terminal: {terminal_info.name}")
                print(f"📊 Build: {terminal_info.build}")
                print(f"📊 Connected to broker: {terminal_info.connected}")
                
                if not terminal_info.connected:
                    print("⚠️ MT5 Terminal is not connected to broker")
                    print("💡 Please connect to your broker in MT5 Terminal first")
                    return False
            
            # Auto-detect logged in account
            return self.detect_logged_account()
            
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def detect_logged_account(self) -> bool:
        """Auto-detect and use the currently logged in account"""
        try:
            print("🔍 Auto-detecting logged in account...")
            
            # Get account info from currently logged in session
            account = mt5.account_info()
            if account is None:
                print("❌ No account logged in MT5 Terminal")
                print("💡 Please log in to your account in MT5 Terminal first")
                return False
            
            # Successfully detected account
            self.account_info = account._asdict()
            
            print("✅ Account detected successfully!")
            print(f"📋 Account Details:")
            print(f"   👤 Name: {self.account_info.get('name', 'Unknown')}")
            print(f"   🔢 Login: {self.account_info.get('login', 'Unknown')}")
            print(f"   💰 Balance: ${self.account_info.get('balance', 0):,.2f}")
            print(f"   💱 Currency: {self.account_info.get('currency', 'Unknown')}")
            print(f"   📈 Leverage: 1:{self.account_info.get('leverage', 0)}")
            print(f"   🌐 Server: {self.account_info.get('server', 'Unknown')}")
            print(f"   📊 Account Type: {'Demo' if self.account_info.get('trade_mode') == 0 else 'Real'}")
            
            # Update balance info
            self.balance = self.account_info.get('balance', 0)
            self.equity = self.account_info.get('equity', 0)
            self.margin = self.account_info.get('margin', 0)
            self.free_margin = self.account_info.get('margin_free', 0)
            
            # Test basic functionality
            return self.test_basic_functionality()
            
        except Exception as e:
            print(f"❌ Error detecting account: {e}")
            return False
    
    def test_basic_functionality(self) -> bool:
        """Test basic MT5 functionality"""
        try:
            print("\n🧪 Testing basic functionality...")
            
            # Test symbol info
            test_symbols = ["EURUSD", "GBPUSD", "EURGBP"]
            working_symbols = []
            
            for symbol in test_symbols:
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info:
                    working_symbols.append(symbol)
                    print(f"✅ {symbol}: Available (Spread: {symbol_info.spread} points)")
                else:
                    print(f"⚠️ {symbol}: Not available")
            
            if not working_symbols:
                print("❌ No symbols available for trading")
                return False
            
            # Test tick data
            test_symbol = working_symbols[0]
            tick = mt5.symbol_info_tick(test_symbol)
            if tick:
                print(f"✅ Tick data: {test_symbol} Bid={tick.bid:.5f} Ask={tick.ask:.5f}")
            else:
                print(f"⚠️ Could not get tick data for {test_symbol}")
            
            # Test positions
            positions = mt5.positions_get()
            if positions is not None:
                print(f"✅ Positions: {len(positions)} open positions")
                if len(positions) > 0:
                    for i, pos in enumerate(positions[:3]):  # Show first 3
                        pips = self.calculate_pips(pos)
                        print(f"   {i+1}. {pos.symbol}: {pos.volume} lots, {pips:+.1f} pips, ${pos.profit:+.2f}")
            else:
                print("⚠️ Could not retrieve positions")
            
            # Test orders history (recent)
            from datetime import datetime, timedelta
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            
            deals = mt5.history_deals_get(yesterday, today)
            if deals is not None:
                print(f"✅ Recent deals: {len(deals)} deals in last 24h")
            
            print("✅ All basic functions working!")
            return True
            
        except Exception as e:
            print(f"❌ Error testing functionality: {e}")
            return False
    
    def calculate_pips(self, position) -> float:
        """Calculate pips for a position"""
        try:
            open_price = position.price_open
            current_price = position.price_current
            symbol = position.symbol
            
            # Determine pip factor
            if 'JPY' in symbol:
                pip_factor = 100
            else:
                pip_factor = 10000
            
            # Calculate pips based on position type
            if position.type == 0:  # BUY
                pips = (current_price - open_price) * pip_factor
            else:  # SELL
                pips = (open_price - current_price) * pip_factor
            
            return pips
            
        except Exception:
            return 0.0
    
    def disconnect(self):
        """Disconnect from MT5"""
        try:
            print("🔌 Disconnecting from MT5...")
            self.running = False
            
            if self.connection_thread:
                self.connection_thread.join(timeout=2)
            
            if self.connected:
                mt5.shutdown()
                print("✅ Disconnected from MT5")
            
            self.connected = False
            
        except Exception as e:
            print(f"❌ Error during disconnect: {e}")
    
    def start_monitoring(self) -> bool:
        """Start background monitoring thread"""
        if not self.connected:
            print("❌ Cannot start monitoring - not connected to MT5")
            return False
        
        if self.running:
            print("⚠️ Monitoring already running")
            return True
        
        self.running = True
        self.connection_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.connection_thread.start()
        print("📊 Started MT5 monitoring thread")
        return True
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        update_interval = 2  # Update every 2 seconds
        
        while self.running:
            try:
                if self.connected:
                    self.update_account_info()
                    self.update_positions()
                time.sleep(update_interval)
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
    
    def update_account_info(self) -> bool:
        """Update account information"""
        try:
            if not self.connected:
                return False
            
            account = mt5.account_info()
            if account is None:
                return False
            
            self.account_info = account._asdict()
            self.balance = self.account_info.get('balance', 0.0)
            self.equity = self.account_info.get('equity', 0.0)
            self.margin = self.account_info.get('margin', 0.0)
            self.free_margin = self.account_info.get('margin_free', 0.0)
            self.last_update = datetime.now()
            
            return True
        except Exception as e:
            self.logger.error(f"Error updating account info: {e}")
            return False
    
    def update_positions(self) -> bool:
        """Update open positions"""
        try:
            if not self.connected:
                return False
            
            positions = mt5.positions_get()
            if positions is None:
                self.positions = []
                return True
            
            self.positions = [pos._asdict() for pos in positions]
            return True
        except Exception as e:
            self.logger.error(f"Error updating positions: {e}")
            return False
    
    def get_positions(self, symbol: str = None) -> List[Dict]:
        """Get positions for specific symbol or all"""
        if symbol:
            return [pos for pos in self.positions if pos.get('symbol') == symbol]
        return self.positions.copy()
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Get symbol information"""
        try:
            if not self.connected:
                return None
                
            info = mt5.symbol_info(symbol)
            if info is None:
                return None
            return info._asdict()
        except Exception as e:
            self.logger.error(f"Error getting symbol info for {symbol}: {e}")
            return None
    
    def get_tick(self, symbol: str) -> Optional[Dict]:
        """Get current tick for symbol"""
        try:
            if not self.connected:
                return None
                
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None
            return tick._asdict()
        except Exception as e:
            self.logger.error(f"Error getting tick for {symbol}: {e}")
            return None
    
    def get_multiple_ticks(self, symbols: List[str]) -> Dict[str, Dict]:
        """Get ticks for multiple symbols efficiently"""
        ticks = {}
        for symbol in symbols:
            tick = self.get_tick(symbol)
            if tick:
                ticks[symbol] = tick
        return ticks
    
    def place_order(self, symbol: str, order_type: int, lots: float, 
                   price: float = 0.0, sl: float = 0.0, tp: float = 0.0,
                   deviation: int = 20, comment: str = "Arbitrage") -> Optional[Dict]:
        """Place trading order"""
        try:
            if not self.connected:
                print("❌ Not connected to MT5")
                return None
                
            symbol_info = self.get_symbol_info(symbol)
            if not symbol_info:
                print(f"❌ Symbol {symbol} not available")
                return None
            
            # Get current price if not provided
            if price == 0.0:
                tick = self.get_tick(symbol)
                if not tick:
                    print(f"❌ Could not get price for {symbol}")
                    return None
                
                if order_type == mt5.ORDER_TYPE_BUY:
                    price = tick['ask']
                else:
                    price = tick['bid']
            
            # Prepare request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lots,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": deviation,
                "magic": 234000,
                "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send order
            result = mt5.order_send(request)
            if result is None:
                error = mt5.last_error()
                print(f"❌ Order send failed: {error}")
                return None
            
            result_dict = result._asdict()
            
            if result_dict.get('retcode') != mt5.TRADE_RETCODE_DONE:
                print(f"❌ Order failed: {result_dict.get('comment', 'Unknown error')}")
                return None
            
            print(f"✅ Order successful: {symbol} {lots} lots, Ticket: {result_dict.get('order')}")
            return result_dict
            
        except Exception as e:
            print(f"❌ Error placing order: {e}")
            return None
    
    def close_position(self, ticket: int) -> bool:
        """Close position by ticket"""
        try:
            if not self.connected:
                return False
                
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                print(f"❌ Position {ticket} not found")
                return False
            
            position = positions[0]
            
            # Determine opposite order type and price
            if position.type == mt5.ORDER_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                tick = mt5.symbol_info_tick(position.symbol)
                price = tick.bid if tick else 0
            else:
                order_type = mt5.ORDER_TYPE_BUY
                tick = mt5.symbol_info_tick(position.symbol)
                price = tick.ask if tick else 0
            
            if price == 0:
                print(f"❌ Could not get closing price for {position.symbol}")
                return False
            
            # Close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "Close position",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ Position {ticket} closed successfully")
                return True
            else:
                error_msg = result.comment if result else "Unknown error"
                print(f"❌ Failed to close position {ticket}: {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ Error closing position {ticket}: {e}")
            return False
    
    def close_all_positions(self) -> int:
        """Close all open positions"""
        closed_count = 0
        positions = self.get_positions()
        
        print(f"🔄 Attempting to close {len(positions)} positions...")
        
        for position in positions:
            if self.close_position(position.get('ticket')):
                closed_count += 1
                time.sleep(0.1)  # Small delay between closes
        
        print(f"✅ Closed {closed_count} out of {len(positions)} positions")
        return closed_count
    
    def get_account_summary(self) -> Dict:
        """Get account summary for GUI"""
        return {
            'balance': self.balance,
            'equity': self.equity,
            'margin': self.margin,
            'free_margin': self.free_margin,
            'profit': self.equity - self.balance,
            'margin_level': (self.equity / self.margin * 100) if self.margin > 0 else 0,
            'positions_count': len(self.positions),
            'last_update': self.last_update,
            'connected': self.connected
        }
    
    def get_connection_status(self) -> Dict:
        """Get detailed connection status"""
        terminal_connected = False
        if self.connected:
            try:
                terminal_info = mt5.terminal_info()
                terminal_connected = terminal_info.connected if terminal_info else False
            except:
                terminal_connected = False
        
        return {
            'connected': self.connected,
            'mt5_terminal_connected': terminal_connected,
            'account_login': self.account_info.get('login') if self.account_info else 'None',
            'account_server': self.account_info.get('server') if self.account_info else 'None',
            'positions_count': len(self.positions),
            'last_update': self.last_update.strftime('%H:%M:%S') if self.last_update else 'Never',
            'monitoring_active': self.running
        }
    
    def is_market_open(self) -> bool:
        """Check if market is open (simple check)"""
        now = datetime.now()
        # Simple check - avoid weekends
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        return True

# Simple testing function
def test_mt5_auto_connection():
    """Test MT5 auto-connection"""
    print("="*60)
    print("🧪 MT5 AUTO-CONNECTION TEST")
    print("="*60)
    
    print("💡 Make sure MT5 Terminal is running and logged in!")
    input("Press Enter to continue...")
    
    # Initialize connection
    mt5_conn = MT5Connection()
    
    if mt5_conn.connect():
        print("\n✅ Connection successful!")
        
        # Start monitoring
        mt5_conn.start_monitoring()
        
        # Show account summary
        print("\n📊 Account Summary:")
        time.sleep(2)  # Let monitoring update
        summary = mt5_conn.get_account_summary()
        for key, value in summary.items():
            if key != 'last_update':
                print(f"   {key}: {value}")
        
        # Show some market data
        print("\n📈 Market Data:")
        symbols = ["EURUSD", "GBPUSD", "EURGBP"]
        ticks = mt5_conn.get_multiple_ticks(symbols)
        for symbol, tick in ticks.items():
            if tick:
                spread = (tick['ask'] - tick['bid']) * 10000
                print(f"   {symbol}: {tick['bid']:.5f}/{tick['ask']:.5f} (Spread: {spread:.1f})")
        
        print("\n✅ All tests passed! Ready to use.")
        
        # Keep running for a bit
        try:
            print("\n⏳ Running for 10 seconds...")
            time.sleep(10)
        except KeyboardInterrupt:
            print("\n⏹️ Test interrupted")
        
        mt5_conn.disconnect()
        
    else:
        print("❌ Connection failed!")
        print("\n💡 Troubleshooting:")
        print("1. Make sure MT5 Terminal is running")
        print("2. Make sure you're logged into an account in MT5")
        print("3. Make sure MT5 is connected to broker")
    
    print("\n" + "="*60)

# Example usage
if __name__ == "__main__":
    test_mt5_auto_connection()