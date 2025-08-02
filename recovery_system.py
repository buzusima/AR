import MetaTrader5 as mt5
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
import math

class RecoverySystem:
    def __init__(self, mt5_connection, config_path: str = "config.json"):
        """Initialize Recovery System with 4 methods"""
        self.mt5_conn = mt5_connection
        self.config = self.load_config(config_path)
        self.running = False
        self.recovery_thread = None
        
        # Recovery settings
        self.recovery_config = self.config.get('recovery_system', {})
        self.methods_config = self.recovery_config.get('methods', {})
        
        # Recovery states for each method
        self.martingale_levels = {}  # symbol -> level
        self.grid_levels = {}        # symbol -> grid_data
        self.hedge_positions = {}    # symbol -> hedge_data
        self.correlation_pairs = {}  # symbol -> correlated_symbols
        
        # Position tracking
        self.losing_positions = {}
        self.recovery_groups = {}
        
        # Recovery statistics
        self.recovery_stats = {
            'martingale_recoveries': 0,
            'grid_recoveries': 0,
            'hedge_recoveries': 0,
            'correlation_recoveries': 0,
            'total_recovery_profit': 0.0
        }
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Callbacks
        self.on_recovery_callback = None
        self.on_error_callback = None
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
    
    def set_callbacks(self, recovery_callback=None, error_callback=None):
        """Set GUI callbacks"""
        self.on_recovery_callback = recovery_callback
        self.on_error_callback = error_callback
    
    def start_recovery_system(self) -> bool:
        """Start the recovery monitoring system"""
        if not self.mt5_conn or not self.mt5_conn.connected:
            self.logger.error("MT5 not connected - cannot start recovery system")
            return False
        
        if self.running:
            return True
        
        self.running = True
        self.recovery_thread = threading.Thread(target=self._recovery_loop, daemon=True)
        self.recovery_thread.start()
        
        self.logger.info(" Recovery system started")
        if self.on_recovery_callback:
            self.on_recovery_callback(" Recovery system started")
        
        return True
    
    def stop_recovery_system(self):
        """Stop the recovery system"""
        self.running = False
        if self.recovery_thread:
            self.recovery_thread.join(timeout=2)
        
        self.logger.info("⏹️ Recovery system stopped")
        if self.on_recovery_callback:
            self.on_recovery_callback("⏹️ Recovery system stopped")
    
    def _recovery_loop(self):
        """Main recovery monitoring loop"""
        while self.running:
            try:
                # Update losing positions
                self.update_losing_positions()
                
                # Check each recovery method
                if self.recovery_config.get('enable_recovery', True):
                    self.check_martingale_recovery()
                    self.check_grid_recovery()
                    self.check_hedge_recovery()
                    self.check_correlation_recovery()
                
                # Check stop loss conditions
                self.check_emergency_stops()
                
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                self.logger.error(f"Error in recovery loop: {e}")
                if self.on_error_callback:
                    self.on_error_callback(f"Recovery error: {e}")
                time.sleep(5)
    
    def update_losing_positions(self):
        """Update positions that are in loss and need recovery"""
        try:
            positions = self.mt5_conn.get_positions()
            current_losing = {}
            
            auto_hedge_threshold = self.methods_config.get('hedging', {}).get('auto_hedge_drawdown', 100)
            
            for position in positions:
                symbol = position.get('symbol')
                profit = position.get('profit', 0)
                ticket = position.get('ticket')
                
                # Calculate pips loss
                open_price = position.get('price_open', 0)
                current_price = position.get('price_current', 0)
                pos_type = position.get('type', 0)
                
                if 'JPY' in symbol:
                    pip_factor = 100
                else:
                    pip_factor = 10000
                
                if pos_type == 0:  # BUY
                    pips = (current_price - open_price) * pip_factor
                else:  # SELL
                    pips = (open_price - current_price) * pip_factor
                
                # Add to losing positions if loss exceeds threshold
                if profit < -10 or pips < -10:  # More than $10 loss or 10 pips
                    current_losing[ticket] = {
                        'symbol': symbol,
                        'profit': profit,
                        'pips': pips,
                        'open_price': open_price,
                        'current_price': current_price,
                        'type': pos_type,
                        'volume': position.get('volume', 0),
                        'time': position.get('time', 0)
                    }
            
            self.losing_positions = current_losing
            
        except Exception as e:
            self.logger.error(f"Error updating losing positions: {e}")
    
    def check_martingale_recovery(self):
        """Check and execute Martingale recovery"""
        if not self.methods_config.get('martingale', {}).get('enable', True):
            return
        
        try:
            martingale_config = self.methods_config.get('martingale', {})
            multiplier = martingale_config.get('multiplier', 1.5)
            max_levels = martingale_config.get('max_levels', 3)
            
            for ticket, pos_data in self.losing_positions.items():
                symbol = pos_data['symbol']
                pips_loss = abs(pos_data['pips'])
                
                # Check if Martingale recovery should be triggered
                if pips_loss >= 20:  # 20 pips loss threshold
                    current_level = self.martingale_levels.get(symbol, 0)
                    
                    if current_level < max_levels:
                        # Execute Martingale recovery
                        if self.execute_martingale_recovery(pos_data, current_level, multiplier):
                            self.martingale_levels[symbol] = current_level + 1
                            self.recovery_stats['martingale_recoveries'] += 1
                            
                            self.logger.info(f"📈 Martingale recovery executed: {symbol} Level {current_level + 1}")
                            if self.on_recovery_callback:
                                self.on_recovery_callback(f"📈 Martingale: {symbol} L{current_level + 1}")
        
        except Exception as e:
            self.logger.error(f"Error in Martingale recovery: {e}")
    
    def execute_martingale_recovery(self, pos_data: Dict, level: int, multiplier: float) -> bool:
        """Execute Martingale WITHOUT automatic SL/TP"""
        try:
            symbol = pos_data['symbol']
            original_volume = pos_data['volume']
            pos_type = pos_data['type']
            
            # Calculate new volume
            new_volume = original_volume * (multiplier ** (level + 1))
            new_volume = min(new_volume, 2.0)
            new_volume = round(new_volume, 2)
            
            # Same direction as losing position
            if pos_type == 0:  # BUY
                order_type = 0
                price = self.mt5_conn.get_tick(symbol)['ask']
            else:  # SELL
                order_type = 1
                price = self.mt5_conn.get_tick(symbol)['bid']
            
            # ✅ Place Martingale order WITHOUT SL/TP
            result = self.mt5_conn.place_order(
                symbol=symbol,
                order_type=order_type,
                lots=new_volume,
                price=price,
                comment=f"Martingale-L{level + 1}"
                # ❌ ไม่ใส่ tp=tp_price, sl=sl_price
            )
            
            return result is not None and result.get('retcode') == 10009
            
        except Exception as e:
            self.logger.error(f"Error executing Martingale recovery: {e}")
            return False


    def check_grid_recovery(self):
        """Check and execute Grid recovery"""
        if not self.methods_config.get('grid', {}).get('enable', True):
            return
        
        try:
            grid_config = self.methods_config.get('grid', {})
            step_pips = grid_config.get('step_pips', 15)
            max_levels = grid_config.get('max_levels', 5)
            lot_multiplier = grid_config.get('lot_multiplier', 1.2)
            
            for ticket, pos_data in self.losing_positions.items():
                symbol = pos_data['symbol']
                pips_loss = abs(pos_data['pips'])
                
                # Initialize grid if not exists
                if symbol not in self.grid_levels:
                    self.grid_levels[symbol] = {
                        'base_price': pos_data['open_price'],
                        'levels': [],
                        'direction': pos_data['type']
                    }
                
                grid_data = self.grid_levels[symbol]
                current_price = pos_data['current_price']
                base_price = grid_data['base_price']
                
                # Calculate grid levels needed
                levels_needed = int(pips_loss / step_pips)
                current_levels = len(grid_data['levels'])
                
                if levels_needed > current_levels and current_levels < max_levels:
                    # Execute grid recovery
                    if self.execute_grid_recovery(pos_data, grid_data, levels_needed, lot_multiplier):
                        self.recovery_stats['grid_recoveries'] += 1
                        
                        self.logger.info(f"🔲 Grid recovery executed: {symbol} Level {levels_needed}")
                        if self.on_recovery_callback:
                            self.on_recovery_callback(f"🔲 Grid: {symbol} L{levels_needed}")
        
        except Exception as e:
            self.logger.error(f"Error in Grid recovery: {e}")
    
    def execute_grid_recovery(self, pos_data: Dict, grid_data: Dict, levels_needed: int, multiplier: float) -> bool:
        """Execute Grid recovery trades"""
        try:
            symbol = pos_data['symbol']
            base_volume = pos_data['volume']
            pos_type = pos_data['type']
            current_levels = len(grid_data['levels'])
            
            for level in range(current_levels + 1, levels_needed + 1):
                # Calculate volume for this level
                level_volume = base_volume * (multiplier ** (level - 1))
                level_volume = min(level_volume, 1.5)  # Cap volume
                level_volume = round(level_volume, 2)
                
                # Same direction as original position
                if pos_type == 0:  # BUY
                    order_type = mt5.ORDER_TYPE_BUY
                    price = self.mt5_conn.get_tick(symbol)['ask']
                else:  # SELL
                    order_type = mt5.ORDER_TYPE_SELL
                    price = self.mt5_conn.get_tick(symbol)['bid']
                
                # Place grid order
                result = self.mt5_conn.place_order(
                    symbol=symbol,
                    order_type=order_type,
                    lots=level_volume,
                    price=price,
                    tp=0,  # No individual TP for grid
                    sl=0,  # No individual SL for grid
                    comment=f"Grid-L{level}"
                )
                
                if result and result.get('retcode') == mt5.TRADE_RETCODE_DONE:
                    grid_data['levels'].append({
                        'level': level,
                        'price': price,
                        'volume': level_volume,
                        'ticket': result.get('order')
                    })
                else:
                    return False
                
                time.sleep(0.1)  # Small delay between orders
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing Grid recovery: {e}")
            return False
    
    def check_hedge_recovery(self):
        """Check and execute Hedge recovery"""
        if not self.methods_config.get('hedging', {}).get('enable', True):
            return
        
        try:
            hedge_config = self.methods_config.get('hedging', {})
            hedge_ratio = hedge_config.get('hedge_ratio', 1.0)
            auto_hedge_threshold = hedge_config.get('auto_hedge_drawdown', 100)
            
            for ticket, pos_data in self.losing_positions.items():
                symbol = pos_data['symbol']
                loss_amount = abs(pos_data['profit'])
                
                # Check if hedge should be triggered
                if loss_amount >= auto_hedge_threshold:
                    if symbol not in self.hedge_positions:
                        # Execute hedge recovery
                        if self.execute_hedge_recovery(pos_data, hedge_ratio):
                            self.recovery_stats['hedge_recoveries'] += 1
                            
                            self.logger.info(f"🛡️ Hedge recovery executed: {symbol}")
                            if self.on_recovery_callback:
                                self.on_recovery_callback(f"🛡️ Hedge: {symbol}")
        
        except Exception as e:
            self.logger.error(f"Error in Hedge recovery: {e}")
    
    def execute_hedge_recovery(self, pos_data: Dict, hedge_ratio: float) -> bool:
        """Execute Hedge recovery trade"""
        try:
            symbol = pos_data['symbol']
            original_volume = pos_data['volume']
            pos_type = pos_data['type']
            
            # Calculate hedge volume
            hedge_volume = original_volume * hedge_ratio
            hedge_volume = round(hedge_volume, 2)
            
            # Opposite direction
            if pos_type == 0:  # Original was BUY, hedge with SELL
                order_type = mt5.ORDER_TYPE_SELL
                price = self.mt5_conn.get_tick(symbol)['bid']
            else:  # Original was SELL, hedge with BUY
                order_type = mt5.ORDER_TYPE_BUY
                price = self.mt5_conn.get_tick(symbol)['ask']
            
            # Place hedge order
            result = self.mt5_conn.place_order(
                symbol=symbol,
                order_type=order_type,
                lots=hedge_volume,
                price=price,
                tp=0,  # No TP for hedge
                sl=0,  # No SL for hedge
                comment="Hedge-Recovery"
            )
            
            if result and result.get('retcode') == mt5.TRADE_RETCODE_DONE:
                self.hedge_positions[symbol] = {
                    'original_ticket': pos_data.get('ticket'),
                    'hedge_ticket': result.get('order'),
                    'hedge_price': price,
                    'hedge_volume': hedge_volume,
                    'timestamp': time.time()
                }
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error executing Hedge recovery: {e}")
            return False
    
    def check_correlation_recovery(self):
        """Check and execute Correlation recovery"""
        if not self.methods_config.get('correlation', {}).get('enable', True):
            return
        
        try:
            corr_config = self.methods_config.get('correlation', {})
            min_correlation = corr_config.get('min_correlation', 0.75)
            hedge_strength = corr_config.get('hedge_strength', 0.8)
            
            # Define correlation pairs (simplified)
            correlation_map = {
                'EURUSD': ['GBPUSD', 'EURGBP'],
                'GBPUSD': ['EURUSD', 'EURGBP'],
                'USDJPY': ['EURJPY', 'GBPJPY'],
                'EURJPY': ['USDJPY', 'GBPJPY']
            }
            
            for ticket, pos_data in self.losing_positions.items():
                symbol = pos_data['symbol']
                loss_amount = abs(pos_data['profit'])
                
                # Check if correlation recovery should be triggered
                if loss_amount >= 50 and symbol in correlation_map:  # $50 loss threshold
                    correlated_symbols = correlation_map[symbol]
                    
                    for corr_symbol in correlated_symbols:
                        if self.execute_correlation_recovery(pos_data, corr_symbol, hedge_strength):
                            self.recovery_stats['correlation_recoveries'] += 1
                            
                            self.logger.info(f"🔗 Correlation recovery: {symbol} -> {corr_symbol}")
                            if self.on_recovery_callback:
                                self.on_recovery_callback(f"🔗 Correlation: {symbol}->{corr_symbol}")
                            break  # Only one correlation recovery per symbol
        
        except Exception as e:
            self.logger.error(f"Error in Correlation recovery: {e}")
    
    def execute_correlation_recovery(self, pos_data: Dict, corr_symbol: str, hedge_strength: float) -> bool:
        """Execute Correlation recovery trade"""
        try:
            original_symbol = pos_data['symbol']
            original_volume = pos_data['volume']
            pos_type = pos_data['type']
            
            # Check if correlated symbol is available
            tick = self.mt5_conn.get_tick(corr_symbol)
            if not tick:
                return False
            
            # Calculate correlation volume
            corr_volume = original_volume * hedge_strength
            corr_volume = round(corr_volume, 2)
            
            # Determine correlation direction (simplified)
            # In practice, you'd use actual correlation analysis
            if self.are_positively_correlated(original_symbol, corr_symbol):
                # Same direction for positive correlation
                order_type = mt5.ORDER_TYPE_BUY if pos_type == 0 else mt5.ORDER_TYPE_SELL
            else:
                # Opposite direction for negative correlation
                order_type = mt5.ORDER_TYPE_SELL if pos_type == 0 else mt5.ORDER_TYPE_BUY
            
            # Get execution price
            if order_type == mt5.ORDER_TYPE_BUY:
                price = tick['ask']
            else:
                price = tick['bid']
            
            # Place correlation recovery order
            result = self.mt5_conn.place_order(
                symbol=corr_symbol,
                order_type=order_type,
                lots=corr_volume,
                price=price,
                tp=0,
                sl=0,
                comment=f"Corr-{original_symbol}"
            )
            
            if result and result.get('retcode') == mt5.TRADE_RETCODE_DONE:
                # Record correlation recovery
                correlation_key = f"{original_symbol}-{corr_symbol}"
                self.correlation_pairs[correlation_key] = {
                    'original_ticket': pos_data.get('ticket'),
                    'correlation_ticket': result.get('order'),
                    'correlation_strength': hedge_strength,
                    'timestamp': time.time()
                }
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error executing Correlation recovery: {e}")
            return False
    
    def are_positively_correlated(self, symbol1: str, symbol2: str) -> bool:
        """Check if two symbols are positively correlated (simplified)"""
        # Simplified correlation logic
        positive_pairs = [
            ('EURUSD', 'GBPUSD'),
            ('USDJPY', 'EURJPY'),
            ('USDCHF', 'EURCHF')
        ]
        
        pair = (symbol1, symbol2)
        reverse_pair = (symbol2, symbol1)
        
        return pair in positive_pairs or reverse_pair in positive_pairs
    
    def check_emergency_stops(self):
        """Check emergency stop conditions"""
        try:
            stop_config = self.recovery_config.get('stop_loss', {})
            emergency_amount = stop_config.get('emergency_close_all', 1000)
            max_drawdown_percent = stop_config.get('max_drawdown_percent', 15)
            
            # Check total portfolio loss
            total_profit = sum([p.get('profit', 0) for p in self.mt5_conn.get_positions()])
            
            if abs(total_profit) >= emergency_amount:
                self.emergency_close_all()
                return
            
            # Check drawdown percentage
            balance = self.mt5_conn.balance
            if balance > 0:
                drawdown_percent = (abs(total_profit) / balance) * 100
                if drawdown_percent >= max_drawdown_percent:
                    self.emergency_close_all()
                    return
        
        except Exception as e:
            self.logger.error(f"Error checking emergency stops: {e}")
    
    def emergency_close_all(self):
        """Emergency close all positions"""
        try:
            self.logger.warning("🚨 EMERGENCY STOP TRIGGERED - Closing all positions")
            if self.on_recovery_callback:
                self.on_recovery_callback("🚨 EMERGENCY STOP - Closing all positions")
            
            closed_count = self.mt5_conn.close_all_positions()
            
            # Reset recovery states
            self.martingale_levels.clear()
            self.grid_levels.clear()
            self.hedge_positions.clear()
            self.correlation_pairs.clear()
            
            self.logger.warning(f"🚨 Emergency stop: Closed {closed_count} positions")
        
        except Exception as e:
            self.logger.error(f"Error in emergency stop: {e}")
    
    def reset_recovery_for_symbol(self, symbol: str):
        """Reset recovery state for a symbol (when position becomes profitable)"""
        try:
            # Reset Martingale
            if symbol in self.martingale_levels:
                del self.martingale_levels[symbol]
            
            # Reset Grid
            if symbol in self.grid_levels:
                del self.grid_levels[symbol]
            
            # Reset Hedge
            if symbol in self.hedge_positions:
                del self.hedge_positions[symbol]
            
            self.logger.info(f"✅ Recovery state reset for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Error resetting recovery for {symbol}: {e}")
    
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
    
    def get_recovery_stats(self) -> Dict:
        """Get recovery system statistics"""
        return {
            'running': self.running,
            'losing_positions': len(self.losing_positions),
            'martingale_active': len(self.martingale_levels),
            'grid_active': len(self.grid_levels),
            'hedge_active': len(self.hedge_positions),
            'correlation_active': len(self.correlation_pairs),
            'recovery_stats': self.recovery_stats.copy()
        }

# Example usage
if __name__ == "__main__":
    print("Recovery System - Use with MT5Connection and ArbitrageEngine")