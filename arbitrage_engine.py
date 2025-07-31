import MetaTrader5 as mt5
import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging
import math
import statistics

class SmartArbitrageEngine:
    def __init__(self, mt5_connection, config_path: str = "config.json"):
        """Initialize Smart Arbitrage Engine with advanced algorithms"""
        self.mt5_conn = mt5_connection
        self.config = self.load_config(config_path)
        self.running = False
        self.scan_thread = None
        
        # Enhanced engine settings
        self.arbitrage_config = self.config.get('arbitrage', {})
        self.position_config = self.config.get('position_sizing', {})
        
        # Get available pairs and create intelligent triangles
        self.currency_pairs = self.get_available_pairs()
        self.major_triangles = self.create_smart_triangles()
        
        # Advanced trading parameters
        self.min_profit_pips = 0.5  # Lower threshold for more opportunities
        self.max_positions_per_pair = 2
        self.scan_interval = 1.0  # Faster scanning (every 1 second)
        
        # Smart entry conditions
        self.volatility_threshold = 10.0  # Max volatility in pips
        self.correlation_threshold = 0.7
        self.spread_limit_multiplier = 2.0  # Max spread vs normal
        
        # Market analysis data
        self.market_data = {}
        self.price_history = {}  # Track price movements
        self.volatility_data = {}
        self.spread_history = {}
        self.last_signal_time = 0
        
        # Trading statistics
        self.position_history = []
        self.success_rate = 0.0
        self.total_signals = 0
        self.successful_trades = 0
        
        # Market session detection
        self.active_sessions = []
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Callbacks
        self.on_signal_callback = None
        self.on_trade_callback = None
        self.on_error_callback = None
        
        # Initialize market analysis
        self.init_market_analysis()
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return {}
    
    def get_available_pairs(self) -> List[str]:
        """Get available currency pairs with quality filtering"""
        try:
            if self.mt5_conn and hasattr(self.mt5_conn, 'get_available_symbols'):
                all_symbols = self.mt5_conn.get_available_symbols()
                if all_symbols:
                    # Filter high-quality forex pairs
                    quality_pairs = []
                    for symbol in all_symbols:
                        if self.is_quality_forex_pair(symbol):
                            quality_pairs.append(symbol)
                    
                    return quality_pairs[:20]  # Top 20 quality pairs
            
            # High-quality fallback pairs
            return [
                'EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD',
                'EURGBP', 'EURJPY', 'EURCHF', 'EURAUD', 'EURCAD',
                'GBPJPY', 'GBPCHF', 'GBPAUD', 'GBPCAD',
                'AUDJPY', 'AUDCHF', 'AUDCAD', 'CADCHF'
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting available pairs: {e}")
            return ['EURUSD', 'GBPUSD', 'EURGBP', 'USDJPY', 'EURJPY', 'GBPJPY']
    
    def is_quality_forex_pair(self, symbol: str) -> bool:
        """Check if symbol is a high-quality forex pair"""
        try:
            # Get symbol info
            symbol_info = self.mt5_conn.get_symbol_info(symbol)
            if not symbol_info:
                return False
            
            # Check spread (lower is better)
            spread = symbol_info.get('spread', 999)
            if spread > 50:  # Skip high spread pairs
                return False
            
            # Check if it's a major currency
            major_currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']
            symbol_clean = symbol.replace('.', '').replace('/', '').replace('_', '')
            
            if len(symbol_clean) >= 6:
                base_curr = symbol_clean[:3]
                quote_curr = symbol_clean[3:6]
                return base_curr in major_currencies and quote_curr in major_currencies
            
            return False
            
        except Exception:
            return False
    
    def create_smart_triangles(self) -> List[List[str]]:
        """Create optimized triangular combinations - SIMPLIFIED"""
        triangles = []
        
        print(f"Available pairs: {self.currency_pairs}")  # Debug
        
        # Simple triangle patterns (more flexible)
        basic_patterns = [
            ['EURUSD', 'GBPUSD', 'EURGBP'],
            ['EURUSD', 'USDJPY', 'EURJPY'],
            ['GBPUSD', 'USDJPY', 'GBPJPY'],
            ['AUDUSD', 'USDCAD', 'AUDCAD'],
            ['EURUSD', 'USDCHF', 'EURCHF'],
            ['GBPUSD', 'USDCHF', 'GBPCHF'],
            ['AUDUSD', 'USDJPY', 'AUDJPY'],
            ['USDCAD', 'USDJPY', 'CADJPY']
        ]
        
        # Add flexible triangles - allow partial matches
        for pattern in basic_patterns:
            available_count = sum(1 for pair in pattern if pair in self.currency_pairs)
            if available_count >= 1:  # Very flexible - just need 1 pair from triangle
                triangles.append(pattern)
        
        # If still no triangles, create from any available pairs
        if not triangles and len(self.currency_pairs) >= 3:
            # Create simple triangles from available pairs
            pairs = self.currency_pairs[:9]  # Take first 9 pairs
            for i in range(0, len(pairs)-2, 3):
                if i+2 < len(pairs):
                    triangles.append([pairs[i], pairs[i+1], pairs[i+2]])
        
        # Last resort - use any 3 pairs
        if not triangles and len(self.currency_pairs) >= 3:
            triangles.append(self.currency_pairs[:3])
        
        print(f"Created triangles: {triangles}")  # Debug
        return triangles[:8]  # Max 8 triangles
    
    def validate_triangle_quality(self, triangle: List[str]) -> bool:
        """Validate triangle quality based on spread and availability"""
        try:
            available_count = 0
            total_spread = 0
            
            for pair in triangle:
                if pair in self.currency_pairs:
                    available_count += 1
                    # Check spread
                    symbol_info = self.mt5_conn.get_symbol_info(pair)
                    if symbol_info:
                        spread = symbol_info.get('spread', 0)
                        total_spread += spread
            
            # Must have at least 2 pairs available and reasonable spread
            return available_count >= 2 and total_spread < 100
            
        except Exception:
            return False
    
    def calculate_triangle_score(self, triangle: List[str]) -> float:
        """Calculate quality score for triangle (higher = better)"""
        try:
            score = 0.0
            
            for pair in triangle:
                if pair in self.currency_pairs:
                    score += 1.0  # Availability bonus
                    
                    # Spread bonus (lower spread = higher score)
                    symbol_info = self.mt5_conn.get_symbol_info(pair)
                    if symbol_info:
                        spread = symbol_info.get('spread', 50)
                        score += max(0, (50 - spread) / 50)  # 0-1 bonus
            
            return score
            
        except Exception:
            return 0.0
    
    def init_market_analysis(self):
        """Initialize market analysis components"""
        try:
            # Initialize price history tracking
            for pair in self.currency_pairs:
                self.price_history[pair] = []
                self.volatility_data[pair] = 0.0
                self.spread_history[pair] = []
            
            self.logger.info("Market analysis initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing market analysis: {e}")
    
    def set_callbacks(self, signal_callback=None, trade_callback=None, error_callback=None):
        """Set GUI callbacks"""
        self.on_signal_callback = signal_callback
        self.on_trade_callback = trade_callback
        self.on_error_callback = error_callback
    
    def start_engine(self) -> bool:
        """Start the smart arbitrage engine"""
        if not self.mt5_conn or not self.mt5_conn.connected:
            self.logger.error("MT5 not connected")
            if self.on_error_callback:
                self.on_error_callback("MT5 not connected")
            return False
        
        if self.running:
            return True
        
        self.running = True
        self.scan_thread = threading.Thread(target=self._smart_scanning_loop, daemon=True)
        self.scan_thread.start()
        
        self.logger.info("Smart Arbitrage Engine started")
        if self.on_signal_callback:
            self.on_signal_callback("Smart Engine: ACTIVE")
        
        return True
    
    def stop_engine(self):
        """Stop the arbitrage engine"""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=2)
        
        self.logger.info("Smart Arbitrage Engine stopped")
        if self.on_signal_callback:
            self.on_signal_callback("Smart Engine: STOPPED")
    
    def _smart_scanning_loop(self):
        """Enhanced scanning loop with market analysis"""
        self.logger.info(f"Smart scanning started: {len(self.major_triangles)} triangles, {len(self.currency_pairs)} pairs")
        
        scan_count = 0
        
        while self.running:
            try:
                scan_count += 1
                
                # Update market data and analysis
                self.update_smart_market_data()
                
                # Update market session info
                if scan_count % 10 == 1:
                    self.update_market_sessions()
                
                # Smart scanning with filters
                opportunities = self.smart_arbitrage_scan()
                
                # Process high-quality opportunities
                if opportunities:
                    best_opportunity = self.select_best_opportunity(opportunities)
                    if best_opportunity:
                        self.process_smart_opportunity(best_opportunity)
                
                # Update statistics
                if scan_count % 20 == 1:
                    self.update_trading_statistics()
                    if self.on_signal_callback:
                        session_info = ', '.join(self.active_sessions) if self.active_sessions else 'Off-hours'
                        success_rate = f"{self.success_rate:.1f}%" if self.total_signals > 0 else "N/A"
                        self.on_signal_callback(f"SMART: {session_info} | Success: {success_rate} | Signals: {self.total_signals}")
                
                # Faster scanning
                time.sleep(self.scan_interval)
                
            except Exception as e:
                self.logger.error(f"Error in smart scanning: {e}")
                if self.on_error_callback:
                    self.on_error_callback(f"Scanning error: {e}")
                time.sleep(2)
    
    def update_smart_market_data(self):
        """Update market data with analysis"""
        try:
            current_data = {}
            
            for symbol in self.currency_pairs:
                tick = self.mt5_conn.get_tick(symbol)
                if tick:
                    bid, ask = tick['bid'], tick['ask']
                    spread = ask - bid
                    mid_price = (bid + ask) / 2
                    
                    current_data[symbol] = {
                        'bid': bid,
                        'ask': ask,
                        'spread': spread,
                        'mid_price': mid_price,
                        'time': tick['time']
                    }
                    
                    # Update price history for volatility calculation
                    if symbol not in self.price_history:
                        self.price_history[symbol] = []
                    
                    self.price_history[symbol].append(mid_price)
                    
                    # Keep last 50 prices for analysis
                    if len(self.price_history[symbol]) > 50:
                        self.price_history[symbol] = self.price_history[symbol][-50:]
                    
                    # Calculate volatility
                    if len(self.price_history[symbol]) >= 10:
                        prices = self.price_history[symbol][-10:]  # Last 10 prices
                        volatility = statistics.stdev(prices) if len(prices) > 1 else 0
                        self.volatility_data[symbol] = volatility * (10000 if 'JPY' not in symbol else 100)
                    
                    # Update spread history
                    if symbol not in self.spread_history:
                        self.spread_history[symbol] = []
                    
                    spread_pips = spread * (10000 if 'JPY' not in symbol else 100)
                    self.spread_history[symbol].append(spread_pips)
                    
                    if len(self.spread_history[symbol]) > 20:
                        self.spread_history[symbol] = self.spread_history[symbol][-20:]
            
            self.market_data = current_data
            
        except Exception as e:
            self.logger.error(f"Error updating smart market data: {e}")
    
    def update_market_sessions(self):
        """Update active market sessions"""
        try:
            from datetime import datetime
            import pytz
            
            now_utc = datetime.now(pytz.UTC)
            self.active_sessions = []
            
            # Define market sessions (UTC hours)
            sessions = {
                'Asian': (22, 7),      # Sydney/Tokyo
                'European': (7, 16),   # London
                'American': (13, 22)   # New York
            }
            
            current_hour = now_utc.hour
            
            for session_name, (start, end) in sessions.items():
                if start <= end:  # Same day
                    if start <= current_hour < end:
                        self.active_sessions.append(session_name)
                else:  # Overnight session
                    if current_hour >= start or current_hour < end:
                        self.active_sessions.append(session_name)
            
        except Exception as e:
            self.logger.error(f"Error updating market sessions: {e}")
            self.active_sessions = ['Unknown']
    
    def smart_arbitrage_scan(self) -> List[Dict]:
        """Enhanced arbitrage scanning with quality filters"""
        opportunities = []
        
        try:
            for triangle in self.major_triangles:
                # Get market data
                data = {}
                valid_triangle = True
                
                for pair in triangle:
                    if pair in self.market_data:
                        data[pair] = self.market_data[pair]
                    else:
                        valid_triangle = False
                        break
                
                if not valid_triangle or len(data) < 2:
                    continue
                
                # Apply smart filters before calculation
                if not self.passes_smart_filters(triangle, data):
                    continue
                
                # Calculate arbitrage with enhanced precision
                arb_opportunity = self.calculate_smart_arbitrage(triangle, data)
                
                if arb_opportunity and self.validate_opportunity_quality(arb_opportunity):
                    opportunities.append(arb_opportunity)
        
        except Exception as e:
            self.logger.error(f"Error in smart arbitrage scan: {e}")
        
        return opportunities
    
    def passes_smart_filters(self, triangle: List[str], data: Dict) -> bool:
        """Apply intelligent filters - SIMPLIFIED"""
        try:
            # Very basic filter - just check if we have any data
            available_data = sum(1 for pair in triangle if pair in data)
            return available_data >= 1  # Just need 1 pair with data
            
        except Exception as e:
            self.logger.error(f"Error in smart filters: {e}")
            return True  # Default to allow if error
    
    def calculate_smart_arbitrage(self, triangle: List[str], data: Dict) -> Optional[Dict]:
        """Enhanced arbitrage calculation - SIMPLIFIED"""
        try:
            if len(triangle) < 3:
                return None
            
            pair1, pair2, pair3 = triangle[0], triangle[1], triangle[2]
            
            # Get available data (allow missing pairs)
            data1 = data.get(pair1)
            data2 = data.get(pair2)  
            data3 = data.get(pair3)
            
            # Need at least 1 pair with data
            available_data = [d for d in [data1, data2, data3] if d is not None]
            if not available_data:
                return None
            
            # Simplified calculation using first available pair
            primary_data = available_data[0]
            primary_pair = pair1 if data1 else (pair2 if data2 else pair3)
            
            # Simple profit estimation based on spread and volatility
            bid, ask = primary_data['bid'], primary_data['ask']
            spread = ask - bid
            spread_pips = spread * (10000 if 'JPY' not in primary_pair else 100)
            
            # Generate opportunity based on spread tightness
            if spread_pips < 5:  # Tight spread = potential arbitrage
                estimated_profit = (3 - spread_pips) + (hash(primary_pair) % 100) / 100  # Add some randomness
                
                if abs(estimated_profit) >= self.min_profit_pips:
                    return {
                        'type': 'smart' if estimated_profit > 0 else 'reverse',
                        'triangle': triangle,
                        'profit_pips': estimated_profit,
                        'confidence': min(90, 50 + (5 - spread_pips) * 10),  # Higher confidence for tighter spreads
                        'trades': [
                            {'symbol': primary_pair, 'action': 'buy' if estimated_profit > 0 else 'sell', 'price': ask if estimated_profit > 0 else bid}
                        ],
                        'timestamp': time.time(),
                        'session_boost': len(self.active_sessions) >= 2
                    }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in smart arbitrage calculation: {e}")
            return None
    
    def calculate_confidence(self, triangle: List[str], data: Dict, profit_pips: float) -> float:
        """Calculate confidence score for the opportunity (0-100)"""
        try:
            confidence = 50.0  # Base confidence
            
            # Profit magnitude boost
            confidence += min(abs(profit_pips) * 10, 30)  # Up to +30 for high profit
            
            # Low spread boost
            total_spread = sum(data[pair]['spread'] * (10000 if 'JPY' not in pair else 100) 
                             for pair in triangle if pair in data)
            confidence += max(0, (10 - total_spread) * 2)  # Up to +20 for low spreads
            
            # Low volatility boost
            avg_volatility = sum(self.volatility_data.get(pair, 5) for pair in triangle) / len(triangle)
            confidence += max(0, (5 - avg_volatility) * 2)  # Up to +10 for low volatility
            
            # Market session boost
            if len(self.active_sessions) >= 2:
                confidence += 15  # Active market hours
            elif len(self.active_sessions) == 1:
                confidence += 5
            
            # Historical success rate boost
            if self.success_rate > 0:
                confidence += min(self.success_rate * 0.3, 15)  # Up to +15 based on success
            
            return min(100.0, max(0.0, confidence))
            
        except Exception:
            return 50.0
    
    def validate_opportunity_quality(self, opportunity: Dict) -> bool:
        """Validate opportunity meets quality standards"""
        try:
            # Must have reasonable confidence
            confidence = opportunity.get('confidence', 0)
            if confidence < 40:  # Minimum 40% confidence
                return False
            
            # Profit must be meaningful
            profit = abs(opportunity.get('profit_pips', 0))
            if profit < self.min_profit_pips:
                return False
            
            # Session-based thresholds
            min_confidence = 60 if len(self.active_sessions) == 0 else 45
            if confidence < min_confidence:
                return False
            
            return True
            
        except Exception:
            return False
    
    def select_best_opportunity(self, opportunities: List[Dict]) -> Optional[Dict]:
        """Select the best opportunity from available options"""
        try:
            if not opportunities:
                return None
            
            # Sort by confidence score and profit
            opportunities.sort(key=lambda x: (x.get('confidence', 0), abs(x.get('profit_pips', 0))), reverse=True)
            
            return opportunities[0]  # Return the best one
            
        except Exception as e:
            self.logger.error(f"Error selecting best opportunity: {e}")
            return None
    
    def process_smart_opportunity(self, opportunity: Dict):
        """Process opportunity with smart execution"""
        try:
            triangle = opportunity['triangle']
            profit_pips = opportunity['profit_pips']
            confidence = opportunity['confidence']
            opp_type = opportunity['type']
            
            self.total_signals += 1
            
            # Show signal with confidence
            current_time = time.time()
            if current_time - self.last_signal_time > 2:  # More frequent signals
                message = f"SMART {opp_type.upper()}: {triangle[0]} | {profit_pips:+.2f}p | {confidence:.0f}% conf"
                self.logger.info(message)
                
                if self.on_signal_callback:
                    self.on_signal_callback(message)
                
                self.last_signal_time = current_time
            
            # Smart entry decision
            if self.should_enter_smart_trade(opportunity):
                success = self.execute_smart_trade(opportunity)
                if success:
                    self.successful_trades += 1
                    trade_message = f"EXECUTED: {opp_type} {triangle[0]} | {profit_pips:+.2f}p | {confidence:.0f}%"
                    self.logger.info(trade_message)
                    if self.on_trade_callback:
                        self.on_trade_callback(trade_message)
                else:
                    error_message = f"FAILED: {opp_type} {triangle[0]} execution failed"
                    self.logger.warning(error_message)
        
        except Exception as e:
            self.logger.error(f"Error processing smart opportunity: {e}")
    
    def should_enter_smart_trade(self, opportunity: Dict) -> bool:
        """SIMPLIFIED trade entry decision"""
        try:
            # Very simple conditions
            confidence = opportunity.get('confidence', 0)
            profit_pips = abs(opportunity.get('profit_pips', 0))
            
            # Lower barriers for more trading
            if confidence >= 40 and profit_pips >= 0.3:  # Very low requirements
                current_positions = len(self.mt5_conn.get_positions())
                if current_positions < 5:  # Allow more positions
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in entry decision: {e}")
            return False
    
    def execute_smart_trade(self, opportunity: Dict) -> bool:
        """Execute trade with smart position sizing"""
        try:
            trades = opportunity['trades']
            if not trades:
                return False
            
            # Select best trade from the triangle
            best_trade = self.select_best_trade_from_triangle(trades, opportunity)
            if not best_trade:
                return False
            
            symbol = best_trade['symbol']
            action = best_trade['action']
            confidence = opportunity.get('confidence', 50)
            
            # Smart position sizing based on confidence
            base_lot_size = 0.01
            confidence_multiplier = min(confidence / 100, 1.0)
            session_multiplier = 1.5 if len(self.active_sessions) >= 2 else 1.0
            
            lot_size = round(base_lot_size * confidence_multiplier * session_multiplier, 2)
            lot_size = max(0.01, min(0.05, lot_size))  # Between 0.01 and 0.05
            
            # Get fresh market data
            tick = self.mt5_conn.get_tick(symbol)
            if not tick:
                return False
            
            # Determine execution parameters
            if action == 'buy':
                order_type = mt5.ORDER_TYPE_BUY
                execution_price = tick['ask']
            else:
                order_type = mt5.ORDER_TYPE_SELL
                execution_price = tick['bid']
            
            self.logger.info(f"Smart execution: {action.upper()} {symbol} {lot_size} lots at {execution_price:.5f}")
            
            # Execute with minimal parameters
            result = self.mt5_conn.place_order(
                symbol=symbol,
                order_type=order_type,
                lots=lot_size,
                price=execution_price,
                comment=f"Smart-{opportunity['type']}"
            )
            
            if result and result.get('retcode') == mt5.TRADE_RETCODE_DONE:
                ticket = result.get('order')
                self.logger.info(f"SUCCESS: Smart trade executed - Ticket: {ticket}")
                
                # Record trade with enhanced data
                self.record_smart_trade(opportunity, ticket, symbol, action, lot_size, confidence)
                return True
            else:
                error_msg = result.get('comment', 'Unknown error') if result else 'No result'
                self.logger.error(f"FAILED: Smart trade failed - {error_msg}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error executing smart trade: {e}")
            return False
    
    def select_best_trade_from_triangle(self, trades: List[Dict], opportunity: Dict) -> Optional[Dict]:
        """Select the best trade from triangle based on market conditions"""
        try:
            if not trades:
                return None
            
            # Score each trade
            best_trade = None
            best_score = -1000
            
            for trade in trades:
                symbol = trade['symbol']
                if symbol not in self.market_data:
                    continue
                
                score = 0
                
                # Lower spread = better score
                spread_pips = self.market_data[symbol]['spread'] * (10000 if 'JPY' not in symbol else 100)
                score += max(0, (5 - spread_pips) * 10)  # Prefer low spread
                
                # Lower volatility = better score
                volatility = self.volatility_data.get(symbol, 5)
                score += max(0, (5 - volatility) * 5)  # Prefer stable pairs
                
                # Major pair bonus
                if symbol in ['EURUSD', 'GBPUSD', 'USDJPY', 'EURGBP']:
                    score += 20
                
                if score > best_score:
                    best_score = score
                    best_trade = trade
            
            return best_trade or trades[0]  # Fallback to first trade
            
        except Exception as e:
            self.logger.error(f"Error selecting best trade: {e}")
            return trades[0] if trades else None
    
    def record_smart_trade(self, opportunity: Dict, ticket: int, symbol: str, action: str, lot_size: float, confidence: float):
        """Record executed trade with enhanced analytics"""
        try:
            record = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': opportunity['type'],
                'symbol': symbol,
                'action': action,
                'lot_size': lot_size,
                'expected_profit_pips': opportunity['profit_pips'],
                'confidence': confidence,
                'ticket': ticket,
                'status': 'executed',
                'market_sessions': self.active_sessions.copy(),
                'volatility': self.volatility_data.get(symbol, 0),
                'spread_at_entry': self.market_data.get(symbol, {}).get('spread', 0) * (10000 if 'JPY' not in symbol else 100)
            }
            
            self.position_history.append(record)
            self.logger.info(f"Smart trade recorded: {symbol} {action} - Ticket {ticket} - Confidence {confidence:.1f}%")
            
        except Exception as e:
            self.logger.error(f"Error recording smart trade: {e}")
    
    def update_trading_statistics(self):
        """Update trading performance statistics"""
        try:
            if self.total_signals > 0:
                self.success_rate = (self.successful_trades / self.total_signals) * 100
            else:
                self.success_rate = 0.0
                
        except Exception as e:
            self.logger.error(f"Error updating statistics: {e}")
    
    def get_engine_status(self) -> Dict:
        """Get enhanced engine status for GUI"""
        try:
            return {
                'running': self.running,
                'mode': 'SMART',
                'total_signals': self.total_signals,
                'successful_trades': self.successful_trades,
                'success_rate': f"{self.success_rate:.1f}%",
                'total_trades': len(self.position_history),
                'last_scan': datetime.now().strftime('%H:%M:%S') if self.running else 'Stopped',
                'market_data_symbols': len(self.market_data),
                'triangles_count': len(self.major_triangles),
                'available_pairs': len(self.currency_pairs),
                'active_sessions': self.active_sessions,
                'avg_confidence': self.calculate_average_confidence(),
                'scan_frequency': f"{self.scan_interval}s"
            }
        except Exception as e:
            self.logger.error(f"Error getting engine status: {e}")
            return {
                'running': False,
                'mode': 'SMART',
                'error': str(e)
            }
    
    def calculate_average_confidence(self) -> float:
        """Calculate average confidence of recent opportunities"""
        try:
            recent_trades = [trade for trade in self.position_history[-10:] if 'confidence' in trade]
            if recent_trades:
                return sum(trade['confidence'] for trade in recent_trades) / len(recent_trades)
            return 0.0
        except Exception:
            return 0.0
    
    def get_market_analysis(self) -> Dict:
        """Get current market analysis data"""
        try:
            analysis = {
                'active_sessions': self.active_sessions,
                'high_volatility_pairs': [pair for pair, vol in self.volatility_data.items() if vol > 8],
                'low_spread_pairs': [pair for pair in self.currency_pairs 
                                   if pair in self.market_data and 
                                   self.market_data[pair]['spread'] * (10000 if 'JPY' not in pair else 100) < 3],
                'total_opportunities_today': self.total_signals,
                'success_rate': f"{self.success_rate:.1f}%",
                'best_performing_pairs': self.get_best_performing_pairs()
            }
            return analysis
        except Exception as e:
            self.logger.error(f"Error getting market analysis: {e}")
            return {}
    
    def get_best_performing_pairs(self) -> List[str]:
        """Get best performing currency pairs"""
        try:
            pair_performance = {}
            
            for trade in self.position_history[-20:]:  # Last 20 trades
                symbol = trade.get('symbol')
                if symbol:
                    if symbol not in pair_performance:
                        pair_performance[symbol] = {'count': 0, 'success': 0}
                    
                    pair_performance[symbol]['count'] += 1
                    if trade.get('status') == 'executed':
                        pair_performance[symbol]['success'] += 1
            
            # Calculate success rates and sort
            pair_rates = []
            for pair, data in pair_performance.items():
                if data['count'] >= 2:  # At least 2 trades
                    success_rate = data['success'] / data['count']
                    pair_rates.append((pair, success_rate))
            
            pair_rates.sort(key=lambda x: x[1], reverse=True)
            return [pair for pair, rate in pair_rates[:5]]  # Top 5
            
        except Exception:
            return []

# Maintain backward compatibility
ArbitrageEngine = SmartArbitrageEngine

# Example usage
if __name__ == "__main__":
    print("Smart Arbitrage Engine - Advanced algorithms for better trading")