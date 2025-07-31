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
        
        # Order filling mode (will be detected)
        self.preferred_filling = mt5.ORDER_FILLING_IOC
        
        # Available symbols cache
        self.available_symbols = []
        
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
            
            # Auto-detect available symbols
            working_symbols = self.detect_available_symbols()
            
            if not working_symbols:
                print("❌ No symbols available for trading")
                print("\n🔍 Let's try to debug this...")
                self.debug_symbols()
                return False
            
            print(f"✅ Found {len(working_symbols)} available symbols:")
            for symbol in working_symbols[:10]:  # Show first 10
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info:
                    print(f"   📊 {symbol}: Spread={symbol_info.spread} points, Digits={symbol_info.digits}")
            
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
            
            # Test order capabilities
            self.test_order_filling_modes(test_symbol)
            
            print("✅ All basic functions working!")
            return True
            
        except Exception as e:
            print(f"❌ Error testing functionality: {e}")
            return False
    
    def detect_available_symbols(self) -> List[str]:
        """Auto-detect available currency symbols"""
        try:
            print("🔍 Auto-detecting available currency symbols...")
            
            # Get all symbols
            all_symbols = mt5.symbols_get()
            if not all_symbols:
                print("❌ Could not retrieve symbols list")
                return []
            
            print(f"📊 Total symbols found: {len(all_symbols)}")
            
            # Show first 20 symbols for debugging
            print("🔍 First 20 symbols from broker:")
            for i, symbol in enumerate(all_symbols[:20]):
                print(f"   {i+1:2d}. {symbol.name} (Path: {getattr(symbol, 'path', 'N/A')})")
            
            # Step 1: Find any tradeable symbols first
            working_symbols = []
            forex_symbols = []
            all_tradeable = []
            
            for symbol in all_symbols:
                symbol_name = symbol.name
                
                # Test if tradeable first
                if self.test_symbol_tradeable(symbol_name):
                    all_tradeable.append(symbol_name)
                    
                    # Check if it's forex-like
                    if self.is_forex_symbol(symbol_name):
                        forex_symbols.append(symbol_name)
                        working_symbols.append(symbol_name)
            
            print(f"✅ Found {len(all_tradeable)} tradeable symbols")
            print(f"✅ Found {len(forex_symbols)} forex-like symbols")
            
            # If we found forex symbols, great!
            if forex_symbols:
                print("🎯 Using detected forex symbols:")
                for symbol in forex_symbols[:15]:  # Show up to 15
                    symbol_info = mt5.symbol_info(symbol)
                    if symbol_info:
                        print(f"   📊 {symbol}: Spread={symbol_info.spread}, Digits={symbol_info.digits}")
                
                self.available_symbols = forex_symbols
                return forex_symbols
            
            # If no forex symbols, try any tradeable symbols that look like currency pairs
            print("🔍 No standard forex symbols found, checking all tradeable symbols...")
            potential_forex = []
            
            for symbol_name in all_tradeable:
                if self.could_be_forex(symbol_name):
                    potential_forex.append(symbol_name)
            
            if potential_forex:
                print(f"✅ Found {len(potential_forex)} potential forex symbols:")
                for symbol in potential_forex[:15]:
                    symbol_info = mt5.symbol_info(symbol)
                    if symbol_info:
                        print(f"   📊 {symbol}: Spread={symbol_info.spread}, Digits={symbol_info.digits}")
                
                self.available_symbols = potential_forex
                return potential_forex
            
            # Last resort: use any tradeable symbols
            if all_tradeable:
                print(f"⚠️ Using any tradeable symbols ({len(all_tradeable)} found):")
                symbols_to_use = all_tradeable[:10]  # Limit to 10
                for symbol in symbols_to_use:
                    symbol_info = mt5.symbol_info(symbol)
                    if symbol_info:
                        print(f"   📊 {symbol}: Spread={symbol_info.spread}, Digits={symbol_info.digits}")
                
                self.available_symbols = symbols_to_use
                return symbols_to_use
            
            print("❌ No tradeable symbols found at all")
            return []
            
        except Exception as e:
            print(f"❌ Error detecting symbols: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def is_forex_symbol(self, symbol_name: str) -> bool:
        """Check if symbol is a forex pair"""
        symbol_upper = symbol_name.upper()
        
        # Common currency codes (expanded list)
        currencies = [
            'USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD',
            'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'ZAR', 'SGD',
            'HKD', 'MXN', 'CNH', 'TRY', 'RUB', 'BRL', 'INR', 'KRW'
        ]
        
        # Remove common suffixes/prefixes and special characters
        clean_symbol = symbol_upper
        suffixes_to_remove = ['.M', 'M', '.', '_', '-', '#', '!', 'C', '.C', '.FX']
        for suffix in suffixes_to_remove:
            clean_symbol = clean_symbol.replace(suffix, '')
        
        # Remove forex category prefixes
        prefixes_to_remove = ['FX', 'FOREX', 'FX_', 'C_']
        for prefix in prefixes_to_remove:
            if clean_symbol.startswith(prefix):
                clean_symbol = clean_symbol[len(prefix):]
        
        # Check if it's 6 characters and contains currencies
        if len(clean_symbol) == 6:
            base_currency = clean_symbol[:3]
            quote_currency = clean_symbol[3:]
            if base_currency in currencies and quote_currency in currencies:
                return True
        
        # Check for slash notation (EUR/USD)
        if '/' in symbol_name:
            parts = symbol_name.split('/')
            if len(parts) == 2:
                base = parts[0].strip().upper()
                quote = parts[1].strip().upper()
                for suffix in suffixes_to_remove:
                    base = base.replace(suffix, '')
                    quote = quote.replace(suffix, '')
                if base in currencies and quote in currencies:
                    return True
        
        # Check for underscore notation (EUR_USD)
        if '_' in symbol_name:
            parts = symbol_name.split('_')
            if len(parts) == 2:
                base = parts[0].strip().upper()
                quote = parts[1].strip().upper()
                for suffix in suffixes_to_remove:
                    base = base.replace(suffix, '')
                    quote = quote.replace(suffix, '')
                if base in currencies and quote in currencies:
                    return True
        
        return False
    
    def could_be_forex(self, symbol_name: str) -> bool:
        """Check if symbol could potentially be forex (more lenient)"""
        symbol_upper = symbol_name.upper()
        
        # Expanded currency list
        currencies = [
            'USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD',
            'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'ZAR', 'SGD',
            'HKD', 'MXN', 'CNH', 'TRY', 'RUB', 'BRL', 'INR', 'KRW',
            'THB', 'MYR', 'PHP', 'ILS', 'CLP', 'COP', 'PEN', 'ARS'
        ]
        
        # Check if symbol contains at least 2 currency codes
        currency_count = 0
        for currency in currencies:
            if currency in symbol_upper:
                currency_count += 1
        
        if currency_count >= 2:
            return True
        
        # Check symbol length (typical forex symbols are 6-8 characters)
        clean_symbol = symbol_upper.replace('.', '').replace('_', '').replace('/', '').replace('-', '').replace('#', '').replace('!', '').replace('M', '').replace('C', '')
        if 6 <= len(clean_symbol) <= 8:
            # Check if first 3 and last 3 characters could be currencies
            if len(clean_symbol) >= 6:
                first_part = clean_symbol[:3]
                last_part = clean_symbol[-3:]
                if first_part in currencies or last_part in currencies:
                    return True
        
        # Check for forex-like patterns
        forex_patterns = ['FX', 'FOREX', 'CCY', 'CURR']
        for pattern in forex_patterns:
            if pattern in symbol_upper:
                return True
        
        return False
    
    def test_symbol_tradeable(self, symbol: str) -> bool:
        """Test if symbol is tradeable (more lenient)"""
        try:
            # First check if symbol exists
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return False
            
            # Check basic trading permissions
            trade_mode = getattr(symbol_info, 'trade_mode', None)
            if trade_mode is not None and trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
                return False
            
            # Try to get tick data
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                # If can't get tick, try to select symbol first
                if not mt5.symbol_select(symbol, True):
                    return False
                
                # Try tick again
                tick = mt5.symbol_info_tick(symbol)
                if not tick:
                    return False
            
            # Check if prices are reasonable
            if tick.bid <= 0 or tick.ask <= 0:
                return False
            
            # Allow equal bid/ask for some symbols (crypto, indices)
            if tick.ask < tick.bid:
                return False
            
            # Check if symbol has reasonable spread (not too wide)
            spread = tick.ask - tick.bid
            if spread > tick.ask * 0.1:  # Spread more than 10% of price is suspicious
                return False
            
            return True
            
        except Exception as e:
            # Debug print for troubleshooting
            print(f"   ⚠️ Error testing {symbol}: {e}")
            return False
    
    def test_order_filling_modes(self, symbol: str):
        """Test available order filling modes for symbol"""
        try:
            print(f"🧪 Testing order filling modes for {symbol}...")
            
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return
            
            # Get filling mode from symbol info
            filling_mode = symbol_info.filling_mode
            
            # Determine best filling mode
            if filling_mode & mt5.ORDER_FILLING_FOK:
                self.preferred_filling = mt5.ORDER_FILLING_FOK
                print(f"✅ Using ORDER_FILLING_FOK for {symbol}")
            elif filling_mode & mt5.ORDER_FILLING_IOC:
                self.preferred_filling = mt5.ORDER_FILLING_IOC
                print(f"✅ Using ORDER_FILLING_IOC for {symbol}")
            elif filling_mode & mt5.ORDER_FILLING_RETURN:
                self.preferred_filling = mt5.ORDER_FILLING_RETURN
                print(f"✅ Using ORDER_FILLING_RETURN for {symbol}")
            else:
                self.preferred_filling = mt5.ORDER_FILLING_IOC  # Default fallback
                print(f"⚠️ Using default ORDER_FILLING_IOC for {symbol}")
                
        except Exception as e:
            print(f"⚠️ Could not determine filling mode: {e}")
            self.preferred_filling = mt5.ORDER_FILLING_IOC
    
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
        """Place trading order with auto-detected filling mode"""
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
            
            # Determine best filling mode for this symbol
            filling_mode = self.get_filling_mode(symbol)
            
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
                "type_filling": filling_mode,
            }
            
            # Send order
            result = mt5.order_send(request)
            if result is None:
                error = mt5.last_error()
                print(f"❌ Order send failed: {error}")
                return None
            
            result_dict = result._asdict()
            
            if result_dict.get('retcode') != mt5.TRADE_RETCODE_DONE:
                # Try alternative filling modes if first attempt fails
                if result_dict.get('retcode') == mt5.TRADE_RETCODE_INVALID_FILL:
                    print(f"⚠️ Trying alternative filling mode...")
                    alternative_modes = [
                        mt5.ORDER_FILLING_IOC,
                        mt5.ORDER_FILLING_FOK,
                        mt5.ORDER_FILLING_RETURN
                    ]
                    
                    for alt_mode in alternative_modes:
                        if alt_mode != filling_mode:
                            request["type_filling"] = alt_mode
                            result = mt5.order_send(request)
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                result_dict = result._asdict()
                                break
                    else:
                        print(f"❌ Order failed with all filling modes: {result_dict.get('comment', 'Unknown error')}")
                        return None
                else:
                    print(f"❌ Order failed: {result_dict.get('comment', 'Unknown error')}")
                    return None
            
            print(f"✅ Order successful: {symbol} {lots} lots, Ticket: {result_dict.get('order')}")
            return result_dict
            
        except Exception as e:
            print(f"❌ Error placing order: {e}")
            return None
    
    def get_filling_mode(self, symbol: str) -> int:
        """Get best filling mode for symbol"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return mt5.ORDER_FILLING_IOC
            
            filling_mode = symbol_info.filling_mode
            
            # Prefer FOK, then IOC, then RETURN
            if filling_mode & mt5.ORDER_FILLING_FOK:
                return mt5.ORDER_FILLING_FOK
            elif filling_mode & mt5.ORDER_FILLING_IOC:
                return mt5.ORDER_FILLING_IOC
            elif filling_mode & mt5.ORDER_FILLING_RETURN:
                return mt5.ORDER_FILLING_RETURN
            else:
                return mt5.ORDER_FILLING_IOC  # Default fallback
                
        except Exception:
            return mt5.ORDER_FILLING_IOC
    
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
    
    def get_available_symbols(self) -> List[str]:
        """Get cached available symbols"""
        return self.available_symbols.copy()
    
    def debug_symbols(self):
        """Debug symbol detection issues"""
        try:
            print("\n🐛 SYMBOL DEBUG MODE")
            print("="*50)
            
            # Get all symbols
            all_symbols = mt5.symbols_get()
            if not all_symbols:
                print("❌ mt5.symbols_get() returned None")
                return
            
            print(f"📊 Total symbols from broker: {len(all_symbols)}")
            
            # Show more symbols for debugging
            print("\n📋 All available symbols (first 50):")
            for i, symbol in enumerate(all_symbols[:50]):
                symbol_name = symbol.name
                
                # Try to get basic info
                try:
                    symbol_info = mt5.symbol_info(symbol_name)
                    tick = mt5.symbol_info_tick(symbol_name)
                    
                    status = "✅" if (symbol_info and tick) else "❌"
                    trade_mode = getattr(symbol_info, 'trade_mode', 'Unknown') if symbol_info else 'No Info'
                    
                    print(f"   {i+1:2d}. {status} {symbol_name:15s} (Trade Mode: {trade_mode})")
                    
                    # If it's working, show more details
                    if symbol_info and tick and i < 5:
                        print(f"       Bid: {tick.bid:.5f}, Ask: {tick.ask:.5f}, Spread: {symbol_info.spread}")
                
                except Exception as e:
                    print(f"   {i+1:2d}. ❌ {symbol_name:15s} (Error: {str(e)[:30]})")
            
            # Try to manually test some common symbols
            print(f"\n🧪 Manual testing of common symbols:")
            test_symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'GOLD', 'XAUUSD', 'BTCUSD', 'US30', 'SPX500']
            
            for symbol in test_symbols:
                try:
                    # Try to select symbol
                    selected = mt5.symbol_select(symbol, True)
                    symbol_info = mt5.symbol_info(symbol)
                    tick = mt5.symbol_info_tick(symbol)
                    
                    if symbol_info and tick:
                        print(f"   ✅ {symbol}: Bid={tick.bid:.5f}, Ask={tick.ask:.5f}")
                    else:
                        print(f"   ❌ {symbol}: Not available")
                
                except Exception as e:
                    print(f"   ❌ {symbol}: Error - {e}")
            
            print("="*50)
            
        except Exception as e:
            print(f"❌ Debug error: {e}")
            import traceback
            traceback.print_exc()

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
        available_symbols = mt5_conn.get_available_symbols()
        if available_symbols:
            symbols_to_show = available_symbols[:5]  # Show first 5 available symbols
            ticks = mt5_conn.get_multiple_ticks(symbols_to_show)
            for symbol, tick in ticks.items():
                if tick:
                    spread = (tick['ask'] - tick['bid']) * (10000 if 'JPY' not in symbol else 100)
                    print(f"   {symbol}: {tick['bid']:.5f}/{tick['ask']:.5f} (Spread: {spread:.1f})")
        else:
            print("   No symbols available")
        
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