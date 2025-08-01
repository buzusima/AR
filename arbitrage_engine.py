import MetaTrader5 as mt5
import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging
import math
import statistics
import random

class SmartArbitrageEngine:
    def __init__(self, mt5_connection, config_path: str = "config.json"):
        """Initialize DEBUG Arbitrage Engine - FORCE SIGNALS FOR TESTING"""
        self.mt5_conn = mt5_connection
        self.config = self.load_config(config_path)
        self.running = False
        self.scan_thread = None
        
        # ULTRA AGGRESSIVE SETTINGS FOR TESTING
        self.min_profit_pips = 0.1  # Very low (was 0.5)
        self.min_confidence = 25    # Very low (was 50)
        self.scan_interval = 3.0    # Reasonable speed
        self.force_signals = True   # DEBUG: Force create signals
        
        # Position tracking
        self.active_positions_by_pair = {}
        self.pair_direction = {}
        self.last_trade_time = {}
        
        # Market data
        self.market_data = {}
        self.price_history = {}
        
        # Get available pairs with debug
        print("🔍 DEBUG: Getting available pairs...")
        self.currency_pairs = self.get_available_pairs_debug()
        print(f"✅ DEBUG: Got {len(self.currency_pairs)} pairs: {self.currency_pairs[:5]}...")
        
        self.triangular_pairs = self.create_simple_triangles_debug()
        print(f"✅ DEBUG: Created {len(self.triangular_pairs)} triangles")
        
        # Trading statistics
        self.position_history = []
        self.total_signals = 0
        self.successful_trades = 0
        self.debug_scan_count = 0
        
        # Market sessions
        self.active_sessions = []
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Callbacks
        self.on_signal_callback = None
        self.on_trade_callback = None
        self.on_error_callback = None
        
        print(f"🔥 DEBUG ARBITRAGE ENGINE INITIALIZED")
        print(f"   - ULTRA LOW THRESHOLDS FOR TESTING")
        print(f"   - Min profit: {self.min_profit_pips} pips")
        print(f"   - Min confidence: {self.min_confidence}%")
        print(f"   - Force signals: {self.force_signals}")
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Config load error: {e}")
            return {}
    
    def get_available_pairs_debug(self) -> List[str]:
        """Get available pairs with DEBUG info"""
        try:
            print("🔍 DEBUG: Checking MT5 connection...")
            if not self.mt5_conn:
                print("❌ DEBUG: No MT5 connection!")
                return self.get_fallback_pairs()
            
            if not self.mt5_conn.connected:
                print("❌ DEBUG: MT5 not connected!")
                return self.get_fallback_pairs()
            
            print("✅ DEBUG: MT5 connected, getting symbols...")
            
            if hasattr(self.mt5_conn, 'get_available_symbols'):
                all_symbols = self.mt5_conn.get_available_symbols()
                print(f"🔍 DEBUG: MT5 returned {len(all_symbols) if all_symbols else 0} symbols")
                
                if all_symbols:
                    forex_pairs = []
                    print("🔍 DEBUG: Testing first 10 symbols:")
                    
                    for i, symbol in enumerate(all_symbols[:10]):
                        tick = self.test_symbol_debug(symbol)
                        if tick:
                            forex_pairs.append(symbol)
                            print(f"   ✅ {symbol}: Bid={tick.get('bid', 0):.5f}")
                        else:
                            print(f"   ❌ {symbol}: No tick data")
                    
                    if forex_pairs:
                        print(f"✅ DEBUG: Found {len(forex_pairs)} working symbols")
                        return forex_pairs[:10]  # Limit to 10 for testing
            
            print("⚠️ DEBUG: No symbols from MT5, using fallback...")
            return self.get_fallback_pairs()
            
        except Exception as e:
            print(f"❌ DEBUG: Error getting pairs: {e}")
            return self.get_fallback_pairs()
    
    def test_symbol_debug(self, symbol: str) -> Optional[Dict]:
        """Test symbol with debug info"""
        try:
            tick = self.mt5_conn.get_tick(symbol)
            if tick and tick.get('bid', 0) > 0 and tick.get('ask', 0) > 0:
                return tick
            return None
        except Exception as e:
            print(f"   ❌ {symbol}: Error - {e}")
            return None
    
    def get_fallback_pairs(self) -> List[str]:
        """Fallback pairs for testing"""
        pairs = [
            'EURUSD.v', 'GBPUSD.v', 'USDJPY.v', 'USDCHF.v', 'AUDUSD.v', 
            'EURGBP.v', 'EURJPY.v', 'GBPJPY.v', 'AUDCAD.v', 'CADCHF.v'
        ]
        print(f"📋 DEBUG: Using fallback pairs: {pairs}")
        return pairs
    
    def create_simple_triangles_debug(self) -> List[Dict]:
        """Create triangles with debug info"""
        triangles = []
        
        if len(self.currency_pairs) >= 3:
            # Create simple triangles for testing
            for i in range(0, min(len(self.currency_pairs), 9), 3):
                if i + 2 < len(self.currency_pairs):
                    triangle = {
                        'name': f'DEBUG_TRI_{i//3 + 1}',
                        'pairs': [self.currency_pairs[i], self.currency_pairs[i+1], self.currency_pairs[i+2]]
                    }
                    triangles.append(triangle)
                    print(f"🔺 DEBUG: Created triangle {triangle['name']}: {triangle['pairs']}")
        
        return triangles[:3]  # Max 3 for testing
    
    def set_callbacks(self, signal_callback=None, trade_callback=None, error_callback=None):
        """Set GUI callbacks"""
        self.on_signal_callback = signal_callback
        self.on_trade_callback = trade_callback
        self.on_error_callback = error_callback
    
    def start_engine(self) -> bool:
        """Start the debug engine"""
        if not self.mt5_conn or not self.mt5_conn.connected:
            print("❌ DEBUG: MT5 not connected")
            return False
        
        if self.running:
            return True
        
        self.running = True
        self.scan_thread = threading.Thread(target=self._debug_trading_loop, daemon=True)
        self.scan_thread.start()
        
        print("🚀 DEBUG ENGINE STARTED - FORCE SIGNAL MODE")
        if self.on_signal_callback:
            self.on_signal_callback("🚀 DEBUG ENGINE: FORCE SIGNALS")
        
        return True
    
    def stop_engine(self):
        """Stop the engine"""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=2)
        
        print("⏹️ DEBUG ENGINE STOPPED")
        if self.on_signal_callback:
            self.on_signal_callback("⏹️ DEBUG ENGINE STOPPED")
    
    def _debug_trading_loop(self):
        """DEBUG trading loop with detailed logging"""
        print(f"🔥 DEBUG TRADING LOOP STARTED")
        print(f"   - Pairs: {len(self.currency_pairs)}")
        print(f"   - Triangles: {len(self.triangular_pairs)}")
        print(f"   - Force signals: {self.force_signals}")
        
        while self.running:
            try:
                self.debug_scan_count += 1
                print(f"\n📊 DEBUG SCAN #{self.debug_scan_count}")
                
                # Update market data with debug
                market_data_count = self.update_market_data_debug()
                print(f"   📈 Market data: {market_data_count} pairs updated")
                
                # Update position tracking
                self.update_position_tracking_debug()
                
                # Update sessions
                if self.debug_scan_count % 10 == 1:
                    self.update_sessions_debug()
                
                # FORCE CREATE OPPORTUNITIES FOR TESTING
                opportunities = self.create_debug_opportunities()
                print(f"   🎯 Opportunities found: {len(opportunities)}")
                
                # Process opportunities
                executed_count = 0
                for i, opportunity in enumerate(opportunities):
                    print(f"   🔍 Testing opportunity {i+1}: {opportunity['type']}")
                    
                    if self.should_execute_debug(opportunity):
                        print(f"   ✅ Executing opportunity {i+1}")
                        success = self.execute_debug_trade(opportunity)
                        if success:
                            executed_count += 1
                            self.successful_trades += 1
                    else:
                        print(f"   ❌ Opportunity {i+1} failed validation")
                
                print(f"   📊 Executed: {executed_count}/{len(opportunities)}")
                
                # Show status every scan
                self.show_debug_status()
                
                time.sleep(self.scan_interval)
                
            except Exception as e:
                print(f"❌ DEBUG: Trading loop error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)
    
    def update_market_data_debug(self) -> int:
        """Update market data with debug info"""
        try:
            current_data = {}
            successful_updates = 0
            
            for symbol in self.currency_pairs:
                try:
                    tick = self.mt5_conn.get_tick(symbol)
                    if tick:
                        bid, ask = tick['bid'], tick['ask']
                        if bid > 0 and ask > 0 and ask > bid:
                            current_data[symbol] = {
                                'bid': bid,
                                'ask': ask,
                                'spread': ask - bid,
                                'spread_pips': (ask - bid) * (100 if 'JPY' in symbol else 10000),
                                'time': tick.get('time', time.time())
                            }
                            successful_updates += 1
                        else:
                            print(f"   ⚠️ {symbol}: Invalid prices - Bid:{bid} Ask:{ask}")
                    else:
                        print(f"   ❌ {symbol}: No tick data")
                        
                except Exception as e:
                    print(f"   ❌ {symbol}: Tick error - {e}")
            
            self.market_data = current_data
            return successful_updates
            
        except Exception as e:
            print(f"❌ DEBUG: Market data error: {e}")
            return 0
    
    def update_position_tracking_debug(self):
        """Update position tracking with debug"""
        try:
            all_positions = self.mt5_conn.get_positions()
            position_count = len(all_positions) if all_positions else 0
            
            if position_count > 0:
                print(f"   📍 Current positions: {position_count}")
            
            # Reset tracking
            self.active_positions_by_pair = {}
            self.pair_direction = {}
            
            # Track positions (simplified for debug)
            for position in all_positions:
                symbol = position.get('symbol', '')
                pos_type = position.get('type', 0)
                volume = position.get('volume', 0)
                
                direction = 'long' if pos_type == 0 else 'short'
                self.pair_direction[symbol] = direction
                print(f"     {symbol}: {direction.upper()} {volume} lots")
            
        except Exception as e:
            print(f"❌ DEBUG: Position tracking error: {e}")
    
    def update_sessions_debug(self):
        """Update sessions with debug"""
        try:
            from datetime import datetime
            import pytz
            
            now_utc = datetime.now(pytz.UTC)
            hour = now_utc.hour
            
            sessions = []
            if 22 <= hour or hour < 8:
                sessions.append('Asian')
            if 7 <= hour < 16:
                sessions.append('European')
            if 13 <= hour < 22:
                sessions.append('American')
            
            self.active_sessions = sessions
            print(f"   🌍 Active sessions: {sessions} (Hour: {hour} UTC)")
            
        except Exception as e:
            print(f"❌ DEBUG: Session update error: {e}")
            self.active_sessions = ['Unknown']
    
    def create_debug_opportunities(self) -> List[Dict]:
        """FORCE CREATE opportunities for testing"""
        opportunities = []
        
        try:
            print(f"   🔍 Creating debug opportunities...")
            print(f"   📊 Market data available: {len(self.market_data)} pairs")
            
            # STRATEGY 1: Force create opportunities from any available data
            for symbol, data in list(self.market_data.items())[:3]:  # Test first 3 pairs
                
                # Create random opportunity
                profit_pips = random.uniform(0.5, 3.0)
                action = random.choice(['buy', 'sell'])
                confidence = random.uniform(30, 70)
                
                opportunity = {
                    'type': 'debug_forced',
                    'target_pair': symbol,
                    'action': action,
                    'profit_pips': profit_pips,
                    'confidence': confidence,
                    'reason': f'DEBUG: Forced signal for testing'
                }
                opportunities.append(opportunity)
                print(f"     🎯 Forced {symbol} {action.upper()}: {profit_pips:.1f}p")
            
            # STRATEGY 2: If no market data, create fake opportunities
            if not opportunities and self.currency_pairs:
                for i, symbol in enumerate(self.currency_pairs[:2]):  # First 2 pairs
                    opportunity = {
                        'type': 'debug_fake',
                        'target_pair': symbol,
                        'action': 'buy' if i % 2 == 0 else 'sell',
                        'profit_pips': 1.0 + i,
                        'confidence': 50 + i * 10,
                        'reason': f'DEBUG: Fake signal (no market data)'
                    }
                    opportunities.append(opportunity)
                    print(f"     🎯 Fake {symbol} {opportunity['action'].upper()}: {opportunity['profit_pips']:.1f}p")
            
            print(f"   ✅ Created {len(opportunities)} debug opportunities")
            return opportunities
            
        except Exception as e:
            print(f"❌ DEBUG: Opportunity creation error: {e}")
            return []
    
    def should_execute_debug(self, opportunity: Dict) -> bool:
        """DEBUG execution decision - VERY LENIENT"""
        try:
            target_pair = opportunity.get('target_pair', '')
            action = opportunity.get('action', '')
            confidence = opportunity.get('confidence', 0)
            profit_pips = opportunity.get('profit_pips', 0)
            
            print(f"     🔍 Validating: {target_pair} {action} | {profit_pips:.1f}p | {confidence:.0f}%")
            
            # ULTRA LOW validation for testing
            if confidence < self.min_confidence:  # 25%
                print(f"       ❌ Confidence too low: {confidence} < {self.min_confidence}")
                return False
            
            if profit_pips < self.min_profit_pips:  # 0.1 pips
                print(f"       ❌ Profit too low: {profit_pips} < {self.min_profit_pips}")
                return False
            
            # Check position conflict (simplified)
            current_direction = self.pair_direction.get(target_pair, 'neutral')
            
            if current_direction == 'long' and action == 'buy':
                print(f"       ❌ Already LONG {target_pair}")
                return False
            
            if current_direction == 'short' and action == 'sell':
                print(f"       ❌ Already SHORT {target_pair}")
                return False
            
            # Simple time check (10 seconds for testing)
            current_time = time.time()
            last_trade = self.last_trade_time.get(target_pair, 0)
            if current_time - last_trade < 10:  # 10 seconds only
                print(f"       ❌ Too soon: {current_time - last_trade:.1f}s < 10s")
                return False
            
            # Position limit (5 for testing)
            total_positions = len(self.mt5_conn.get_positions())
            if total_positions >= 5:
                print(f"       ❌ Too many positions: {total_positions} >= 5")
                return False
            
            print(f"       ✅ Validation passed!")
            return True
            
        except Exception as e:
            print(f"❌ DEBUG: Validation error: {e}")
            return False
    
    def execute_debug_trade(self, opportunity: Dict) -> bool:
        """Execute trade with DEBUG info"""
        try:
            target_pair = opportunity.get('target_pair', '')
            action = opportunity.get('action', '')
            profit_pips = opportunity.get('profit_pips', 0)
            confidence = opportunity.get('confidence', 50)
            
            self.total_signals += 1
            self.last_trade_time[target_pair] = time.time()
            
            # Show signal
            signal_msg = f"🎯 DEBUG {opportunity['type'].upper()}: {target_pair} {action.upper()} | {profit_pips:+.1f}p | {confidence:.0f}%"
            print(f"     {signal_msg}")
            
            if self.on_signal_callback:
                self.on_signal_callback(signal_msg)
            
            # DEBUG position sizing
            lot_size = 0.01  # Fixed small size for testing
            
            # Get market data or use fake price
            if target_pair in self.market_data:
                tick = self.market_data[target_pair]
                if action == 'buy':
                    execution_price = tick['ask']
                else:
                    execution_price = tick['bid']
                
                print(f"     💰 Using real price: {execution_price:.5f}")
            else:
                # Fake execution for testing
                execution_price = 1.0000 + random.uniform(-0.001, 0.001)
                print(f"     💰 Using fake price: {execution_price:.5f}")
            
            # Determine order type
            if action == 'buy':
                order_type = mt5.ORDER_TYPE_BUY
            else:
                order_type = mt5.ORDER_TYPE_SELL
            
            print(f"     🔥 EXECUTING DEBUG: {action.upper()} {target_pair} {lot_size} lots at {execution_price:.5f}")
            
            # Try real execution - MINIMAL PARAMETERS ONLY
            result = self.mt5_conn.place_order(
                symbol=target_pair,
                order_type=order_type,
                lots=lot_size,
                price=execution_price,
                comment=f"DEBUG-{opportunity['type']}"
                # NO sl=0, tp=0 - Broker doesn't accept these!
            )
            
            if result and result.get('retcode') == mt5.TRADE_RETCODE_DONE:
                ticket = result.get('order')
                trade_msg = f"✅ DEBUG EXECUTED: {target_pair} {action.upper()} | Ticket: {ticket}"
                print(f"     {trade_msg}")
                
                if self.on_trade_callback:
                    self.on_trade_callback(trade_msg)
                
                return True
            else:
                error_msg = result.get('comment', 'Unknown error') if result else 'No result'
                print(f"     ❌ DEBUG FAILED: {target_pair} - {error_msg}")
                return False
                
        except Exception as e:
            print(f"❌ DEBUG: Execution error: {e}")
            return False
    
    def show_debug_status(self):
        """Show detailed debug status"""
        try:
            success_rate = (self.successful_trades / max(self.total_signals, 1)) * 100
            active_pairs = len([d for d in self.pair_direction.values() if d != 'neutral'])
            
            session_info = '/'.join(self.active_sessions) if self.active_sessions else 'Off-hours'
            
            status_msg = f"📊 DEBUG: {session_info} | Signals: {self.total_signals} | Success: {self.successful_trades} | Rate: {success_rate:.1f}% | Active: {active_pairs}"
            print(f"   {status_msg}")
            
            if self.on_signal_callback:
                self.on_signal_callback(status_msg)
            
        except Exception as e:
            print(f"❌ DEBUG: Status error: {e}")
    
    def get_engine_status(self) -> Dict:
        """Get debug engine status"""
        try:
            success_rate = (self.successful_trades / max(self.total_signals, 1)) * 100
            active_pairs = len([d for d in self.pair_direction.values() if d != 'neutral'])
            
            return {
                'running': self.running,
                'mode': 'DEBUG FORCE SIGNALS',
                'total_signals': self.total_signals,
                'successful_trades': self.successful_trades,
                'success_rate': f"{success_rate:.1f}%",
                'active_pairs': active_pairs,
                'market_data_pairs': len(self.market_data),
                'total_pairs': len(self.currency_pairs),
                'triangles': len(self.triangular_pairs),
                'active_sessions': self.active_sessions,
                'scan_count': self.debug_scan_count,
                'last_update': datetime.now().strftime('%H:%M:%S') if self.running else 'Stopped'
            }
        except Exception:
            return {'running': False, 'error': 'Status unavailable'}

# Maintain backward compatibility
ArbitrageEngine = SmartArbitrageEngine

if __name__ == "__main__":
    print("🔥 DEBUG ARBITRAGE ENGINE")
    print("🚨 FORCE SIGNAL MODE FOR TESTING")
    print("📊 DETAILED DEBUG LOGS")
    print("⚡ ULTRA LOW THRESHOLDS")
    print("🎯 GUARANTEED SIGNALS FOR TROUBLESHOOTING")