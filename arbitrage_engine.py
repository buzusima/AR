import MetaTrader5 as mt5
import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging
import math

class ArbitrageEngine:
    def __init__(self, mt5_connection, config_path: str = "config.json"):
        """Initialize Arbitrage Engine"""
        self.mt5_conn = mt5_connection
        self.config = self.load_config(config_path)
        self.running = False
        self.scan_thread = None
        
        # Engine settings
        self.arbitrage_config = self.config.get('arbitrage', {})
        self.position_config = self.config.get('position_sizing', {})
        self.profit_config = self.config.get('profit_management', {})
        
        # Currency pairs and triangles
        self.currency_pairs = self.arbitrage_config.get('currency_pairs', [])
        self.major_triangles = self.arbitrage_config.get('major_triangles', [])
        
        # Trading parameters
        self.min_profit_pips = self.arbitrage_config.get('min_profit_pips', 5)
        self.max_positions_per_pair = self.arbitrage_config.get('max_positions_per_pair', 3)
        self.scan_interval = self.arbitrage_config.get('scan_interval_ms', 500) / 1000
        self.loose_entry = self.arbitrage_config.get('entry_conditions', {}).get('loose_entry', True)
        
        # Active positions tracking
        self.active_positions = {}
        self.position_history = []
        
        # Market data cache
        self.market_data = {}
        self.correlations = {}
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Callbacks for GUI updates
        self.on_signal_callback = None
        self.on_trade_callback = None
        self.on_error_callback = None
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
    
    def set_callbacks(self, signal_callback=None, trade_callback=None, error_callback=None):
        """Set GUI callbacks"""
        self.on_signal_callback = signal_callback
        self.on_trade_callback = trade_callback
        self.on_error_callback = error_callback
    
    def start_engine(self) -> bool:
        """Start the arbitrage engine"""
        if not self.mt5_conn or not self.mt5_conn.connected:
            self.logger.error("MT5 not connected - cannot start engine")
            if self.on_error_callback:
                self.on_error_callback("MT5 not connected")
            return False
        
        if self.running:
            self.logger.warning("Engine already running")
            return True
        
        self.running = True
        self.scan_thread = threading.Thread(target=self._scanning_loop, daemon=True)
        self.scan_thread.start()
        
        self.logger.info("🚀 Arbitrage engine started")
        if self.on_signal_callback:
            self.on_signal_callback("🚀 Arbitrage engine started")
        
        return True
    
    def stop_engine(self):
        """Stop the arbitrage engine"""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=2)
        
        self.logger.info("⏹️ Arbitrage engine stopped")
        if self.on_signal_callback:
            self.on_signal_callback("⏹️ Arbitrage engine stopped")
    
    def _scanning_loop(self):
        """Main scanning loop for arbitrage opportunities"""
        self.logger.info("📊 Starting arbitrage scanning loop")
        
        while self.running:
            try:
                # Update market data
                self.update_market_data()
                
                # Scan for arbitrage opportunities
                opportunities = self.scan_triangular_arbitrage()
                
                # Process opportunities
                for opportunity in opportunities:
                    if self.running:  # Check if still running
                        self.process_arbitrage_opportunity(opportunity)
                
                # Update correlations periodically
                if int(time.time()) % 60 == 0:  # Every minute
                    self.update_correlations()
                
                # Check for profit taking opportunities
                self.check_profit_management()
                
                time.sleep(self.scan_interval)
                
            except Exception as e:
                self.logger.error(f"Error in scanning loop: {e}")
                if self.on_error_callback:
                    self.on_error_callback(f"Scanning error: {e}")
                time.sleep(1)
    
    def update_market_data(self):
        """Update market data for all currency pairs"""
        try:
            current_data = {}
            
            for symbol in self.currency_pairs:
                tick = self.mt5_conn.get_tick(symbol)
                if tick:
                    current_data[symbol] = {
                        'bid': tick['bid'],
                        'ask': tick['ask'],
                        'spread': tick['ask'] - tick['bid'],
                        'time': tick['time']
                    }
            
            self.market_data = current_data
            
        except Exception as e:
            self.logger.error(f"Error updating market data: {e}")
    
    def scan_triangular_arbitrage(self) -> List[Dict]:
        """Scan for triangular arbitrage opportunities"""
        opportunities = []
        
        try:
            for triangle in self.major_triangles:
                if len(triangle) != 3:
                    continue
                
                pair1, pair2, pair3 = triangle
                
                # Get market data for triangle
                data1 = self.market_data.get(pair1)
                data2 = self.market_data.get(pair2)
                data3 = self.market_data.get(pair3)
                
                if not all([data1, data2, data3]):
                    continue
                
                # Calculate arbitrage opportunities
                arb_opportunity = self.calculate_triangle_arbitrage(pair1, pair2, pair3, data1, data2, data3)
                
                if arb_opportunity and arb_opportunity['profit_pips'] >= self.min_profit_pips:
                    opportunities.append(arb_opportunity)
        
        except Exception as e:
            self.logger.error(f"Error scanning arbitrage: {e}")
        
        return opportunities
    
    def calculate_triangle_arbitrage(self, pair1: str, pair2: str, pair3: str, 
                                   data1: dict, data2: dict, data3: dict) -> Optional[Dict]:
        """Calculate triangular arbitrage opportunity"""
        try:
            # Example: EURUSD, GBPUSD, EURGBP
            # Forward: Buy EUR/USD -> Sell GBP/USD -> Buy EUR/GBP
            # Reverse: Sell EUR/USD -> Buy GBP/USD -> Sell EUR/GBP
            
            # Forward arbitrage calculation
            forward_rate = data1['ask'] / data2['bid'] * data3['bid']  # Simplified calculation
            forward_profit = (forward_rate - 1) * 10000  # Convert to pips
            
            # Reverse arbitrage calculation  
            reverse_rate = data1['bid'] / data2['ask'] * data3['ask']  # Simplified calculation
            reverse_profit = (1 - reverse_rate) * 10000  # Convert to pips
            
            # Determine best opportunity
            if forward_profit > reverse_profit and forward_profit >= self.min_profit_pips:
                return {
                    'type': 'forward',
                    'triangle': [pair1, pair2, pair3],
                    'profit_pips': forward_profit,
                    'trades': [
                        {'symbol': pair1, 'action': 'buy', 'price': data1['ask']},
                        {'symbol': pair2, 'action': 'sell', 'price': data2['bid']},
                        {'symbol': pair3, 'action': 'buy', 'price': data3['ask']}
                    ],
                    'timestamp': time.time()
                }
            elif reverse_profit >= self.min_profit_pips:
                return {
                    'type': 'reverse',
                    'triangle': [pair1, pair2, pair3],
                    'profit_pips': reverse_profit,
                    'trades': [
                        {'symbol': pair1, 'action': 'sell', 'price': data1['bid']},
                        {'symbol': pair2, 'action': 'buy', 'price': data2['ask']},
                        {'symbol': pair3, 'action': 'sell', 'price': data3['bid']}
                    ],
                    'timestamp': time.time()
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error calculating triangle arbitrage: {e}")
            return None
    
    def process_arbitrage_opportunity(self, opportunity: Dict):
        """Process and execute arbitrage opportunity"""
        try:
            triangle = opportunity['triangle']
            profit_pips = opportunity['profit_pips']
            trades = opportunity['trades']
            
            self.logger.info(f"🎯 Arbitrage opportunity: {triangle} - {profit_pips:.1f} pips")
            
            if self.on_signal_callback:
                self.on_signal_callback(f"📊 Signal: {triangle} - {profit_pips:.1f} pips")
            
            # Check position limits
            if not self.check_position_limits(triangle):
                self.logger.warning("Position limits exceeded - skipping opportunity")
                return
            
            # Execute trades if conditions are met
            if self.should_enter_trade(opportunity):
                success = self.execute_arbitrage_trades(opportunity)
                if success:
                    self.logger.info(f"✅ Executed arbitrage: {triangle}")
                    if self.on_trade_callback:
                        self.on_trade_callback(f"✅ Executed: {triangle}")
                else:
                    self.logger.warning(f"❌ Failed to execute: {triangle}")
        
        except Exception as e:
            self.logger.error(f"Error processing arbitrage opportunity: {e}")
    
    def should_enter_trade(self, opportunity: Dict) -> bool:
        """Determine if we should enter the trade"""
        try:
            # Loose entry conditions (as requested)
            if self.loose_entry:
                # Simple checks only
                profit_pips = opportunity['profit_pips']
                return profit_pips >= self.min_profit_pips
            
            # Strict entry conditions (if loose_entry = False)
            profit_pips = opportunity['profit_pips']
            triangle = opportunity['triangle']
            
            # Check minimum profit
            if profit_pips < self.min_profit_pips:
                return False
            
            # Check spread conditions
            max_spread = self.arbitrage_config.get('max_spread_pips', 50)
            for symbol in triangle:
                data = self.market_data.get(symbol)
                if data:
                    spread_pips = data['spread'] * (10000 if 'JPY' not in symbol else 100)
                    if spread_pips > max_spread:
                        return False
            
            # Check correlation (if available)
            min_correlation = self.arbitrage_config.get('correlation_threshold', 0.7)
            if self.correlations:
                # Add correlation checks here if needed
                pass
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in entry decision: {e}")
            return False
    
    def check_position_limits(self, triangle: List[str]) -> bool:
        """Check if position limits allow new trades"""
        try:
            # Check per-pair limits
            for symbol in triangle:
                current_positions = len([p for p in self.mt5_conn.get_positions(symbol)])
                if current_positions >= self.max_positions_per_pair:
                    return False
            
            # Check total positions
            total_positions = len(self.mt5_conn.get_positions())
            max_total = self.arbitrage_config.get('max_total_positions', 10)
            if total_positions >= max_total:
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking position limits: {e}")
            return False
    
    def execute_arbitrage_trades(self, opportunity: Dict) -> bool:
        """Execute the arbitrage trades"""
        try:
            trades = opportunity['trades']
            executed_tickets = []
            
            for trade in trades:
                symbol = trade['symbol']
                action = trade['action']
                price = trade['price']
                
                # Calculate lot size
                lot_size = self.calculate_lot_size(symbol)
                
                # Determine order type
                if action == 'buy':
                    order_type = mt5.ORDER_TYPE_BUY
                    execution_price = self.market_data[symbol]['ask']
                else:
                    order_type = mt5.ORDER_TYPE_SELL
                    execution_price = self.market_data[symbol]['bid']
                
                # Calculate TP and SL
                tp_pips = self.profit_config.get('individual_tp', {}).get('tp_pips', 15)
                sl_pips = self.config.get('recovery_system', {}).get('stop_loss', {}).get('individual_sl_pips', 50)
                
                tp_price = self.calculate_tp_price(symbol, execution_price, tp_pips, action)
                sl_price = self.calculate_sl_price(symbol, execution_price, sl_pips, action)
                
                # Place order
                result = self.mt5_conn.place_order(
                    symbol=symbol,
                    order_type=order_type,
                    lots=lot_size,
                    price=execution_price,
                    tp=tp_price,
                    sl=sl_price,
                    comment=f"Arbitrage-{opportunity['type']}"
                )
                
                if result and result.get('retcode') == mt5.TRADE_RETCODE_DONE:
                    ticket = result.get('order')
                    executed_tickets.append(ticket)
                    self.logger.info(f"✅ {action.upper()} {symbol} - Ticket: {ticket}")
                else:
                    self.logger.error(f"❌ Failed to execute {action} {symbol}")
                    # Close already opened positions if any failed
                    for ticket in executed_tickets:
                        self.mt5_conn.close_position(ticket)
                    return False
                
                time.sleep(0.1)  # Small delay between orders
            
            # Record successful arbitrage
            self.record_arbitrage_execution(opportunity, executed_tickets)
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing arbitrage trades: {e}")
            return False
    
    def calculate_lot_size(self, symbol: str) -> float:
        """Calculate appropriate lot size for position"""
        try:
            # Get account balance
            balance = self.mt5_conn.balance
            
            # Get risk percentage
            risk_percent = self.position_config.get('risk_percent', 2.0) / 100
            
            # Get position sizing settings
            max_lot = self.position_config.get('max_lot_size', 1.0)
            min_lot = self.position_config.get('min_lot_size', 0.01)
            dynamic_sizing = self.position_config.get('dynamic_sizing', True)
            
            if dynamic_sizing:
                # Dynamic lot size based on balance and risk
                symbol_info = self.mt5_conn.get_symbol_info(symbol)
                if not symbol_info:
                    return min_lot
                
                # Simple calculation (can be enhanced)
                contract_size = symbol_info.get('trade_contract_size', 100000)
                tick_value = symbol_info.get('trade_tick_value', 1.0)
                
                # Calculate lot size based on risk
                risk_amount = balance * risk_percent
                lot_size = risk_amount / (contract_size * tick_value * 0.0001)  # Simplified
                
                # Apply volatility adjustment if enabled
                if self.position_config.get('volatility_adjustment', True):
                    # Simple volatility factor (can be enhanced with ATR)
                    volatility_factor = self.get_volatility_factor(symbol)
                    lot_size = lot_size / volatility_factor
                
            else:
                # Fixed lot size
                lot_size = self.position_config.get('max_lot_size', 0.1)
            
            # Apply limits
            lot_size = max(min_lot, min(max_lot, lot_size))
            
            # Round to appropriate decimal places
            lot_size = round(lot_size, 2)
            
            return lot_size
            
        except Exception as e:
            self.logger.error(f"Error calculating lot size: {e}")
            return 0.01
    
    def get_volatility_factor(self, symbol: str) -> float:
        """Get volatility factor for position sizing"""
        try:
            # Simple volatility calculation based on spread
            data = self.market_data.get(symbol)
            if not data:
                return 1.0
            
            spread = data['spread']
            avg_spread = 0.0002  # Average spread assumption
            
            volatility_factor = max(0.5, min(2.0, spread / avg_spread))
            return volatility_factor
            
        except Exception as e:
            self.logger.error(f"Error calculating volatility factor: {e}")
            return 1.0
    
    def calculate_tp_price(self, symbol: str, entry_price: float, tp_pips: int, action: str) -> float:
        """Calculate take profit price"""
        try:
            pip_size = 0.0001 if 'JPY' not in symbol else 0.01
            
            if action == 'buy':
                return entry_price + (tp_pips * pip_size)
            else:
                return entry_price - (tp_pips * pip_size)
                
        except Exception as e:
            self.logger.error(f"Error calculating TP price: {e}")
            return 0.0
    
    def calculate_sl_price(self, symbol: str, entry_price: float, sl_pips: int, action: str) -> float:
        """Calculate stop loss price"""
        try:
            pip_size = 0.0001 if 'JPY' not in symbol else 0.01
            
            if action == 'buy':
                return entry_price - (sl_pips * pip_size)
            else:
                return entry_price + (sl_pips * pip_size)
                
        except Exception as e:
            self.logger.error(f"Error calculating SL price: {e}")
            return 0.0
    
    def record_arbitrage_execution(self, opportunity: Dict, tickets: List[int]):
        """Record executed arbitrage for tracking"""
        try:
            record = {
                'timestamp': datetime.now(),
                'type': opportunity['type'],
                'triangle': opportunity['triangle'],
                'expected_profit_pips': opportunity['profit_pips'],
                'tickets': tickets,
                'status': 'active'
            }
            
            self.position_history.append(record)
            
        except Exception as e:
            self.logger.error(f"Error recording arbitrage execution: {e}")
    
    def update_correlations(self):
        """Update currency pair correlations"""
        try:
            # Simple correlation calculation
            # In a real implementation, you would use historical price data
            correlations = {}
            
            pairs = self.currency_pairs
            for i, pair1 in enumerate(pairs):
                for pair2 in pairs[i+1:]:
                    # Simplified correlation calculation
                    # In practice, you'd use historical data and proper correlation formula
                    correlation = self.calculate_simple_correlation(pair1, pair2)
                    correlations[f"{pair1}-{pair2}"] = correlation
            
            self.correlations = correlations
            
        except Exception as e:
            self.logger.error(f"Error updating correlations: {e}")
    
    def calculate_simple_correlation(self, pair1: str, pair2: str) -> float:
        """Calculate simple correlation between two pairs"""
        try:
            # This is a placeholder - in real implementation,
            # you would use historical price data and proper correlation calculation
            
            # For now, return a mock correlation based on common currencies
            common_currencies = 0
            
            for currency in ['EUR', 'GBP', 'USD', 'JPY']:
                if currency in pair1 and currency in pair2:
                    common_currencies += 1
            
            # Mock correlation based on common currencies
            if common_currencies >= 1:
                return 0.7 + (common_currencies * 0.1)
            else:
                return 0.3
                
        except Exception as e:
            self.logger.error(f"Error calculating correlation: {e}")
            return 0.0
    
    def check_profit_management(self):
        """Check for profit management opportunities"""
        try:
            if not self.profit_config.get('portfolio_tp', {}).get('enable_cross_pair', False):
                return
            
            # Get current positions
            positions = self.mt5_conn.get_positions()
            if len(positions) < 2:
                return
            
            # Group positions by profitability
            profitable_positions = [p for p in positions if p.get('profit', 0) > 0]
            losing_positions = [p for p in positions if p.get('profit', 0) < 0]
            
            # Check for cross-pair profit taking opportunities
            for profit_pos in profitable_positions:
                for loss_pos in losing_positions:
                    if self.should_cross_pair_manage(profit_pos, loss_pos):
                        self.execute_cross_pair_management(profit_pos, loss_pos)
        
        except Exception as e:
            self.logger.error(f"Error in profit management: {e}")
    
    def should_cross_pair_manage(self, profit_pos: Dict, loss_pos: Dict) -> bool:
        """Check if cross-pair management should be executed"""
        try:
            profit_amount = profit_pos.get('profit', 0)
            loss_amount = abs(loss_pos.get('profit', 0))
            
            # Get correlation
            symbol1 = profit_pos.get('symbol')
            symbol2 = loss_pos.get('symbol')
            correlation_key = f"{symbol1}-{symbol2}"
            correlation = self.correlations.get(correlation_key, 0.0)
            
            # Check conditions
            min_correlation = self.profit_config.get('cross_pair_rules', {}).get('hedge_correlation_min', 0.8)
            profit_loss_ratio = self.profit_config.get('cross_pair_rules', {}).get('profit_loss_ratio', 2.0)
            
            if correlation >= min_correlation and profit_amount >= (loss_amount * profit_loss_ratio):
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking cross-pair management: {e}")
            return False
    
    def execute_cross_pair_management(self, profit_pos: Dict, loss_pos: Dict):
        """Execute cross-pair profit management"""
        try:
            profit_ticket = profit_pos.get('ticket')
            loss_symbol = loss_pos.get('symbol')
            
            # Close profitable position
            if self.mt5_conn.close_position(profit_ticket):
                self.logger.info(f"💰 Closed profitable position {profit_ticket} for cross-pair management")
                
                # Optional: Add hedge for losing position
                if self.profit_config.get('cross_pair_rules', {}).get('auto_hedge_loss_pips', 0) > 0:
                    # Implementation for hedging losing position
                    pass
            
        except Exception as e:
            self.logger.error(f"Error executing cross-pair management: {e}")
    
    def get_engine_status(self) -> Dict:
        """Get engine status for GUI"""
        return {
            'running': self.running,
            'active_positions': len(self.active_positions),
            'total_trades': len(self.position_history),
            'last_scan': datetime.now().strftime('%H:%M:%S') if self.running else 'Stopped',
            'market_data_symbols': len(self.market_data),
            'correlations_count': len(self.correlations)
        }

# Example usage
if __name__ == "__main__":
    # This would normally be used with MT5Connection
    print("Arbitrage Engine - Use with MT5Connection and GUI")