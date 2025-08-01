import MetaTrader5 as mt5
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging
import math
import statistics
import numpy as np

class SmartArbitrageEngine:
    def __init__(self, mt5_connection, config_path: str = "config.json"):
        """Initialize Smart Arbitrage Engine V2.0 - Enhanced Intelligence"""
        # Load config first
        self.config = self.load_config(config_path)
        
        # Setup logging immediately after config
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Now initialize everything else
        self.mt5_conn = mt5_connection
        self.running = False
        self.scan_thread = None
        
        # Enhanced engine settings
        self.arbitrage_config = self.config.get('arbitrage', {})
        self.position_config = self.config.get('position_sizing', {})
        
        # Get available pairs and create REAL triangular arbitrage pairs
        self.currency_pairs = self.get_available_pairs()
        self.triangular_pairs = self.create_real_triangular_pairs()
        
        # SMART trading parameters (more realistic)
        self.min_profit_pips = 2.0  # Minimum 2 pips profit
        self.max_profit_pips = 50.0  # Maximum realistic profit
        self.max_positions_per_triangle = 1  # One position per triangle
        self.scan_interval = 5.0  # Scan every 5 seconds (less spam)
        
        # INTELLIGENT market conditions
        self.volatility_threshold = 15.0  # Max volatility in pips
        self.spread_quality_threshold = 3.0  # Max total spread for triangle
        self.signal_cooldown = 30.0  # 30 seconds between signals for same triangle
        self.min_confidence_score = 65.0  # Minimum confidence to trade
        
        # Market analysis data
        self.market_data = {}
        self.price_history = {}
        self.volatility_data = {}
        self.spread_history = {}
        self.signal_history = {}  # Track signal timing
        self.last_signal_time = {}  # Per triangle cooldown
        
        # Trading statistics
        self.position_history = []
        self.success_rate = 0.0
        self.total_signals = 0
        self.successful_trades = 0
        self.quality_signals = 0  # High-quality signals only
        
        # Market session detection
        self.active_sessions = []
        self.market_strength = 0.0  # 0-100 market quality score
        
        # Callbacks
        self.on_signal_callback = None
        self.on_trade_callback = None
        self.on_error_callback = None
        
        # Initialize market analysis
        self.init_market_analysis()
        
        self.logger.info("Smart Arbitrage Engine V2.0 Initialized")
        
    def setup_logging(self):
        """Setup logging configuration for Smart Arbitrage Engine"""
        try:
            import os
            
            # Get log level from config
            log_level = self.config.get('logging', {}).get('level', 'INFO')
            
            # Create logs directory if not exists
            if not os.path.exists('logs'):
                os.makedirs('logs')
            
            # Configure logging if not already configured
            logger = logging.getLogger(__name__)
            if not logger.handlers:
                # Create formatter (NO EMOJIS)
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                
                # File handler with UTF-8 encoding
                file_handler = logging.FileHandler('logs/arbitrage_engine.log', encoding='utf-8')
                file_handler.setFormatter(formatter)
                
                # Console handler with UTF-8 encoding
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                
                # Add handlers to logger
                logger.addHandler(file_handler)
                logger.addHandler(console_handler)
                logger.setLevel(getattr(logging, log_level, logging.INFO))
            
        except Exception as e:
            print(f"Error setting up logging: {e}")
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load config: {e}")  # Use print instead of logger here
            return {}
    
    def get_available_pairs(self) -> List[str]:
        """Get available currency pairs with enhanced quality filtering"""
        try:
            if self.mt5_conn and hasattr(self.mt5_conn, 'get_available_symbols'):
                all_symbols = self.mt5_conn.get_available_symbols()
                if all_symbols:
                    # Filter for MAJOR forex pairs only (highest liquidity)
                    major_pairs = []
                    for symbol in all_symbols:
                        if self.is_major_forex_pair(symbol):
                            major_pairs.append(symbol)
                    
                    self.logger.info(f"Found {len(major_pairs)} major forex pairs")
                    return major_pairs[:15]  # Top 15 major pairs only
            
            # Fallback to proven major pairs with .v suffix for your broker
            major_pairs = [
                'EURUSD.v', 'GBPUSD.v', 'USDJPY.v', 'USDCHF.v', 'AUDUSD.v', 'USDCAD.v', 'NZDUSD.v',
                'EURGBP.v', 'EURJPY.v', 'EURCHF.v', 'EURAUD.v', 'EURCAD.v', 'EURNZD.v',
                'GBPJPY.v', 'GBPCHF.v', 'GBPAUD.v', 'GBPCAD.v', 'GBPNZD.v',
                'AUDJPY.v', 'AUDCHF.v', 'AUDCAD.v', 'AUDNZD.v', 'CADCHF.v', 'CADJPY.v',
                'CHFJPY.v', 'NZDJPY.v', 'NZDCHF.v', 'NZDCAD.v'
            ]
            
            self.logger.info("Using fallback major forex pairs with .v suffix")
            return major_pairs
            
        except Exception as e:
            self.logger.error(f"Error getting available pairs: {e}")
            return ['EURUSD', 'GBPUSD', 'EURGBP', 'USDJPY', 'EURJPY', 'GBPJPY']
    
    def is_major_forex_pair(self, symbol: str) -> bool:
        """Check if symbol is a major forex pair with strict criteria"""
        try:
            # Get symbol info for quality check
            symbol_info = self.mt5_conn.get_symbol_info(symbol)
            if not symbol_info:
                return False
            
            # Check spread quality (must be reasonable)
            spread = symbol_info.get('spread', 999)
            if spread > 50:  # Allow higher spread for .v symbols
                return False
            
            # Check if it's a major currency pair
            major_currencies = ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD']
            symbol_clean = symbol.replace('.', '').replace('/', '').replace('_', '').upper()
            
            # Remove common suffixes including .v
            for suffix in ['.V', '.M', '.C', 'V', 'M', 'C']:
                if symbol_clean.endswith(suffix):
                    symbol_clean = symbol_clean[:-len(suffix)]
                    break
            
            if len(symbol_clean) >= 6:
                base_curr = symbol_clean[:3]
                quote_curr = symbol_clean[3:6]
                
                # Both currencies must be major
                if base_curr in major_currencies and quote_curr in major_currencies:
                    # Additional quality checks
                    tick = self.mt5_conn.get_tick(symbol)
                    if tick and tick.get('bid', 0) > 0 and tick.get('ask', 0) > 0:
                        return True
            
            return False
            
        except Exception:
            return False
    
    def create_real_triangular_pairs(self) -> List[Dict]:
        """Create REAL triangular arbitrage opportunities with proper math"""
        triangles = []
        
        self.logger.info(f"Creating triangular pairs from {len(self.currency_pairs)} available pairs")
        
        # Define REAL triangular relationships with .v suffix
        real_triangular_sets = [
            # Major triangular arbitrage opportunities
            {'base': 'EUR', 'quote': 'USD', 'cross': 'GBP', 
             'pairs': ['EURUSD.v', 'GBPUSD.v', 'EURGBP.v'], 'type': 'direct'},
            
            {'base': 'EUR', 'quote': 'USD', 'cross': 'JPY',
             'pairs': ['EURUSD.v', 'USDJPY.v', 'EURJPY.v'], 'type': 'indirect'},
            
            {'base': 'GBP', 'quote': 'USD', 'cross': 'JPY',
             'pairs': ['GBPUSD.v', 'USDJPY.v', 'GBPJPY.v'], 'type': 'indirect'},
            
            {'base': 'EUR', 'quote': 'USD', 'cross': 'CHF',
             'pairs': ['EURUSD.v', 'USDCHF.v', 'EURCHF.v'], 'type': 'indirect'},
            
            {'base': 'GBP', 'quote': 'USD', 'cross': 'CHF',
             'pairs': ['GBPUSD.v', 'USDCHF.v', 'GBPCHF.v'], 'type': 'indirect'},
            
            {'base': 'AUD', 'quote': 'USD', 'cross': 'JPY',
             'pairs': ['AUDUSD.v', 'USDJPY.v', 'AUDJPY.v'], 'type': 'indirect'},
            
            {'base': 'EUR', 'quote': 'GBP', 'cross': 'CHF',
             'pairs': ['EURGBP.v', 'GBPCHF.v', 'EURCHF.v'], 'type': 'direct'},
            
            {'base': 'AUD', 'quote': 'USD', 'cross': 'CAD',
             'pairs': ['AUDUSD.v', 'USDCAD.v', 'AUDCAD.v'], 'type': 'indirect'},
            
            # Additional triangles based on what we saw in your log
            {'base': 'EUR', 'quote': 'AUD', 'cross': 'CAD',
             'pairs': ['EURAUD.v', 'AUDCAD.v', 'EURCAD.v'], 'type': 'direct'},
            
            {'base': 'CHF', 'quote': 'JPY', 'cross': 'CAD',
             'pairs': ['CHFJPY.v', 'CADJPY.v', 'CADCHF.v'], 'type': 'direct'},
        ]
        
        # Validate and create available triangles
        for triangle_def in real_triangular_sets:
            pairs = triangle_def['pairs']
            available_pairs = [p for p in pairs if self.find_symbol_variant(p)]
            
            if len(available_pairs) >= 2:  # Need at least 2 pairs for partial arbitrage
                # Map to actual available symbols
                actual_pairs = [self.find_symbol_variant(p) for p in pairs]
                actual_pairs = [p for p in actual_pairs if p]  # Remove None values
                
                if actual_pairs:
                    triangle = {
                        'id': f"{triangle_def['base']}{triangle_def['quote']}{triangle_def['cross']}",
                        'pairs': actual_pairs,
                        'base_currency': triangle_def['base'],
                        'quote_currency': triangle_def['quote'], 
                        'cross_currency': triangle_def['cross'],
                        'type': triangle_def['type'],
                        'completeness': len(actual_pairs) / 3.0,  # How complete the triangle is
                        'quality_score': 0.0  # Will be calculated dynamically
                    }
                    triangles.append(triangle)
        
        self.logger.info(f"Created {len(triangles)} real triangular arbitrage opportunities")
        
        # Sort by completeness and return top triangles
        triangles.sort(key=lambda x: x['completeness'], reverse=True)
        return triangles[:6]  # Top 6 triangles maximum
    
    def find_symbol_variant(self, base_symbol: str) -> Optional[str]:
        """Find the actual symbol variant available in the broker"""
        # Common symbol variations - prioritize .v for your broker
        variants = [
            base_symbol + '.v',  # Your broker uses .v
            base_symbol + '.V',
            base_symbol,
            base_symbol + '.m',
            base_symbol + '.c',
            base_symbol + 'm',
            base_symbol + 'c',
            base_symbol.lower() + '.v',
            base_symbol.lower()
        ]
        
        for variant in variants:
            if variant in self.currency_pairs:
                return variant
        
        return None
    
    def init_market_analysis(self):
        """Initialize enhanced market analysis components"""
        try:
            # Initialize data structures for each available pair
            for pair in self.currency_pairs:
                self.price_history[pair] = []
                self.volatility_data[pair] = 0.0
                self.spread_history[pair] = []
            
            # Initialize triangle-specific tracking
            for triangle in self.triangular_pairs:
                triangle_id = triangle['id']
                self.last_signal_time[triangle_id] = 0
                self.signal_history[triangle_id] = []
            
            self.logger.info("Enhanced market analysis initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing market analysis: {e}")
    
    def set_callbacks(self, signal_callback=None, trade_callback=None, error_callback=None):
        """Set GUI callbacks"""
        self.on_signal_callback = signal_callback
        self.on_trade_callback = trade_callback
        self.on_error_callback = error_callback
    
    def start_engine(self) -> bool:
        """Start the enhanced smart arbitrage engine"""
        if not self.mt5_conn or not self.mt5_conn.connected:
            self.logger.error("MT5 not connected")
            if self.on_error_callback:
                self.on_error_callback("MT5 not connected")
            return False
        
        if self.running:
            return True
        
        self.running = True
        self.scan_thread = threading.Thread(target=self._enhanced_scanning_loop, daemon=True)
        self.scan_thread.start()
        
        self.logger.info("Smart Arbitrage Engine V2.0 started")
        if self.on_signal_callback:
            self.on_signal_callback("Smart Engine V2.0: ACTIVE")
        
        return True
    
    def stop_engine(self):
        """Stop the arbitrage engine"""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=2)
        
        self.logger.info("Smart Arbitrage Engine stopped")
        if self.on_signal_callback:
            self.on_signal_callback("Smart Engine: STOPPED")
    
    def _enhanced_scanning_loop(self):
        """Enhanced scanning loop with market intelligence"""
        self.logger.info(f"Smart scanning started: {len(self.triangular_pairs)} triangles, {len(self.currency_pairs)} pairs")
        
        scan_count = 0
        
        while self.running:
            try:
                scan_count += 1
                
                # Update market data and intelligence
                self.update_market_intelligence()
                
                # Update market sessions and strength (every 20 scans)
                if scan_count % 20 == 1:
                    self.update_market_sessions()
                    self.calculate_market_strength()
                
                # Smart arbitrage scanning with enhanced filters
                opportunities = self.smart_triangular_scan()
                
                # Process only HIGH-QUALITY opportunities
                if opportunities:
                    best_opportunity = self.select_premium_opportunity(opportunities)
                    if best_opportunity:
                        self.process_intelligent_opportunity(best_opportunity)
                
                # Update performance statistics (every 40 scans)
                if scan_count % 40 == 1:
                    self.update_performance_statistics()
                    self.send_status_update()
                
                # Adaptive scanning interval based on market conditions
                sleep_time = self.calculate_adaptive_scan_interval()
                time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"Error in enhanced scanning: {e}")
                if self.on_error_callback:
                    self.on_error_callback(f"Scanning error: {e}")
                time.sleep(5)
    
    def update_market_intelligence(self):
        """Update market data with enhanced intelligence"""
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
                        'time': tick['time'],
                        'spread_pips': self.calculate_spread_pips(symbol, spread)
                    }
                    
                    # Update price history for volatility calculation
                    if symbol not in self.price_history:
                        self.price_history[symbol] = []
                    
                    self.price_history[symbol].append(mid_price)
                    
                    # Keep last 100 prices for analysis
                    if len(self.price_history[symbol]) > 100:
                        self.price_history[symbol] = self.price_history[symbol][-100:]
                    
                    # Calculate enhanced volatility
                    if len(self.price_history[symbol]) >= 20:
                        self.volatility_data[symbol] = self.calculate_enhanced_volatility(symbol)
                    
                    # Update spread quality history
                    if symbol not in self.spread_history:
                        self.spread_history[symbol] = []
                    
                    spread_pips = current_data[symbol]['spread_pips']
                    self.spread_history[symbol].append(spread_pips)
                    
                    if len(self.spread_history[symbol]) > 50:
                        self.spread_history[symbol] = self.spread_history[symbol][-50:]
            
            self.market_data = current_data
            
        except Exception as e:
            self.logger.error(f"Error updating market intelligence: {e}")
    
    def calculate_spread_pips(self, symbol: str, spread: float) -> float:
        """Calculate spread in pips with proper decimal handling"""
        try:
            if 'JPY' in symbol:
                return spread * 100
            else:
                return spread * 10000
        except:
            return 0.0
    
    def calculate_enhanced_volatility(self, symbol: str) -> float:
        """Calculate enhanced volatility with multiple timeframes"""
        try:
            prices = self.price_history[symbol]
            if len(prices) < 20:
                return 0.0
            
            # Calculate multiple volatility measures
            recent_prices = prices[-20:]  # Last 20 prices
            short_vol = np.std(recent_prices) if len(recent_prices) > 1 else 0
            
            medium_prices = prices[-50:] if len(prices) >= 50 else prices
            medium_vol = np.std(medium_prices) if len(medium_prices) > 1 else 0
            
            # Weighted average volatility
            volatility = (short_vol * 0.7 + medium_vol * 0.3)
            
            # Convert to pips
            pip_factor = 100 if 'JPY' in symbol else 10000
            return volatility * pip_factor
            
        except Exception:
            return 0.0
    
    def update_market_sessions(self):
        """Update active market sessions with enhanced detection"""
        try:
            import pytz
            now_utc = datetime.now(pytz.UTC)
            self.active_sessions = []
            
            # Enhanced market sessions (UTC hours)
            sessions = {
                'Asian': {'start': 22, 'end': 8, 'strength': 0.7},
                'European': {'start': 7, 'end': 16, 'strength': 1.0},  
                'American': {'start': 12, 'end': 21, 'strength': 0.9},
                'Overlap_EU_US': {'start': 12, 'end': 16, 'strength': 1.2}  # Best session
            }
            
            current_hour = now_utc.hour
            session_strength = 0.0
            
            for session_name, session_data in sessions.items():
                start_hour = session_data['start']
                end_hour = session_data['end']
                strength = session_data['strength']
                
                # Handle overnight sessions
                if start_hour > end_hour:  # Overnight session
                    if current_hour >= start_hour or current_hour < end_hour:
                        self.active_sessions.append(session_name)
                        session_strength = max(session_strength, strength)
                else:  # Same day session
                    if start_hour <= current_hour < end_hour:
                        self.active_sessions.append(session_name)
                        session_strength = max(session_strength, strength)
            
            # Store session strength for decision making
            self.session_strength = session_strength
            
        except Exception as e:
            self.logger.error(f"Error updating market sessions: {e}")
            self.active_sessions = ['Unknown']
            self.session_strength = 0.5
    
    def calculate_market_strength(self):
        """Calculate overall market strength score (0-100)"""
        try:
            strength_factors = []
            
            # Session strength (0-40 points)
            session_score = min(self.session_strength * 30, 40)
            strength_factors.append(session_score)
            
            # Spread quality (0-25 points)
            if self.market_data:
                avg_spread = np.mean([data.get('spread_pips', 10) for data in self.market_data.values()])
                spread_score = max(0, 25 - (avg_spread * 2))  # Lower spread = higher score
                strength_factors.append(spread_score)
            
            # Volatility score (0-20 points) - moderate volatility is best
            if self.volatility_data:
                avg_volatility = np.mean(list(self.volatility_data.values()))
                # Optimal volatility is around 8-12 pips
                if 8 <= avg_volatility <= 12:
                    vol_score = 20
                elif 5 <= avg_volatility <= 15:
                    vol_score = 15
                else:
                    vol_score = max(0, 20 - abs(avg_volatility - 10))
                strength_factors.append(vol_score)
            
            # Data completeness (0-15 points)
            data_completeness = len(self.market_data) / max(len(self.currency_pairs), 1) * 15
            strength_factors.append(data_completeness)
            
            # Calculate final market strength
            self.market_strength = sum(strength_factors)
            
        except Exception as e:
            self.logger.error(f"Error calculating market strength: {e}")
            self.market_strength = 50.0  # Default neutral score
    
    def smart_triangular_scan(self) -> List[Dict]:
        """Enhanced triangular arbitrage scanning with real math"""
        opportunities = []
        
        try:
            for triangle in self.triangular_pairs:
                triangle_id = triangle['id']
                
                # Check signal cooldown first
                current_time = time.time()
                if current_time - self.last_signal_time.get(triangle_id, 0) < self.signal_cooldown:
                    continue
                
                # Get market data for triangle pairs
                triangle_data = {}
                valid_pairs = 0
                
                for pair in triangle['pairs']:
                    if pair in self.market_data:
                        triangle_data[pair] = self.market_data[pair]
                        valid_pairs += 1
                
                # Need at least 2 pairs for partial arbitrage
                if valid_pairs < 2:
                    continue
                
                # Apply enhanced quality filters
                if not self.passes_enhanced_filters(triangle, triangle_data):
                    continue
                
                # Calculate REAL triangular arbitrage
                arb_opportunity = self.calculate_real_triangular_arbitrage(triangle, triangle_data)
                
                if arb_opportunity and self.validate_opportunity_realism(arb_opportunity):
                    opportunities.append(arb_opportunity)
        
        except Exception as e:
            self.logger.error(f"Error in smart triangular scan: {e}")
        
        return opportunities
    
    def passes_enhanced_filters(self, triangle: Dict, data: Dict) -> bool:
        """Enhanced quality filters for triangular opportunities"""
        try:
            # Market strength filter
            if self.market_strength < 40:  # Below minimum market quality
                return False
            
            # Spread quality filter
            total_spread_pips = sum([pair_data.get('spread_pips', 10) for pair_data in data.values()])
            if total_spread_pips > self.spread_quality_threshold:
                return False
            
            # Volatility filter (avoid extreme volatility)
            for pair in triangle['pairs']:
                if pair in self.volatility_data:
                    vol = self.volatility_data[pair]
                    if vol > self.volatility_threshold or vol < 1.0:  # Too volatile or too quiet
                        return False
            
            # Session filter (avoid low-liquidity sessions)
            if len(self.active_sessions) == 0:
                return False
            
            # Data freshness filter
            for pair_data in data.values():
                data_age = time.time() - pair_data.get('time', 0)
                if data_age > 10:  # Data older than 10 seconds
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in enhanced filters: {e}")
            return False
    
    def calculate_real_triangular_arbitrage(self, triangle: Dict, data: Dict) -> Optional[Dict]:
        """Calculate REAL triangular arbitrage with proper mathematics"""
        try:
            pairs = triangle['pairs']
            triangle_type = triangle['type']
            base_curr = triangle['base_currency']
            quote_curr = triangle['quote_currency']
            cross_curr = triangle['cross_currency']
            
            # Get the three rates we need
            rates = {}
            for pair in pairs:
                if pair in data:
                    pair_data = data[pair]
                    rates[pair] = {
                        'bid': pair_data['bid'],
                        'ask': pair_data['ask'],
                        'mid': pair_data['mid_price']
                    }
            
            if len(rates) < 2:
                return None
            
            # Calculate triangular arbitrage based on type
            if triangle_type == 'direct':
                # Direct triangle: EUR/USD * GBP/USD = EUR/GBP
                return self.calculate_direct_triangle_arbitrage(triangle, rates)
            else:
                # Indirect triangle: EUR/USD * USD/JPY = EUR/JPY  
                return self.calculate_indirect_triangle_arbitrage(triangle, rates)
                
        except Exception as e:
            self.logger.error(f"Error calculating real triangular arbitrage: {e}")
            return None
    
    def calculate_direct_triangle_arbitrage(self, triangle: Dict, rates: Dict) -> Optional[Dict]:
        """Calculate direct triangular arbitrage (e.g., EUR/USD, GBP/USD, EUR/GBP)"""
        try:
            pairs = triangle['pairs']
            
            # For complete triangle, we need all 3 pairs
            if len(rates) < 3:
                return None
            
            # Get rates - example: EUR/USD, GBP/USD, EUR/GBP
            pair1_name = pairs[0]  # EUR/USD
            pair2_name = pairs[1]  # GBP/USD  
            pair3_name = pairs[2]  # EUR/GBP
            
            pair1 = rates[pair1_name]  # EUR/USD
            pair2 = rates[pair2_name]  # GBP/USD
            pair3 = rates[pair3_name]  # EUR/GBP
            
            # Forward arbitrage: Buy EUR/USD, Sell GBP/USD, Sell EUR/GBP
            # Cross rate should be: EUR/USD / GBP/USD = EUR/GBP
            synthetic_rate = pair1['bid'] / pair2['ask']  # EUR/GBP synthetic
            actual_rate = pair3['ask']  # EUR/GBP actual
            
            forward_profit_pips = (synthetic_rate - actual_rate) * 10000
            
            # Reverse arbitrage: Sell EUR/USD, Buy GBP/USD, Buy EUR/GBP  
            synthetic_rate_rev = pair1['ask'] / pair2['bid']
            actual_rate_rev = pair3['bid']
            
            reverse_profit_pips = (actual_rate_rev - synthetic_rate_rev) * 10000
            
            # Choose the better opportunity
            if abs(forward_profit_pips) > abs(reverse_profit_pips):
                profit_pips = forward_profit_pips
                direction = 'forward'
                trades = [
                    {'pair': pair1_name, 'action': 'buy', 'price': pair1['ask']},
                    {'pair': pair2_name, 'action': 'sell', 'price': pair2['bid']},
                    {'pair': pair3_name, 'action': 'sell', 'price': pair3['bid']}
                ]
            else:
                profit_pips = reverse_profit_pips  
                direction = 'reverse'
                trades = [
                    {'pair': pair1_name, 'action': 'sell', 'price': pair1['bid']},
                    {'pair': pair2_name, 'action': 'buy', 'price': pair2['ask']}, 
                    {'pair': pair3_name, 'action': 'buy', 'price': pair3['ask']}
                ]
            
            # Only return if profit is significant
            if abs(profit_pips) >= self.min_profit_pips:
                confidence = self.calculate_arbitrage_confidence(triangle, rates, abs(profit_pips))
                
                return {
                    'type': direction,
                    'triangle': triangle,
                    'profit_pips': profit_pips,
                    'confidence': confidence,
                    'trades': trades,
                    'timestamp': time.time(),
                    'market_strength': self.market_strength
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in direct triangle calculation: {e}")
            return None
    
    def calculate_indirect_triangle_arbitrage(self, triangle: Dict, rates: Dict) -> Optional[Dict]:
        """Calculate indirect triangular arbitrage (e.g., EUR/USD, USD/JPY, EUR/JPY)"""
        try:
            pairs = triangle['pairs']
            
            # For complete triangle, we need all 3 pairs
            if len(rates) < 3:
                return None
            
            # Get rates - example: EUR/USD, USD/JPY, EUR/JPY
            pair1_name = pairs[0]  # EUR/USD
            pair2_name = pairs[1]  # USD/JPY
            pair3_name = pairs[2]  # EUR/JPY
            
            pair1 = rates[pair1_name]  # EUR/USD
            pair2 = rates[pair2_name]  # USD/JPY  
            pair3 = rates[pair3_name]  # EUR/JPY
            
            # Forward arbitrage: Buy EUR/USD, Buy USD/JPY, Sell EUR/JPY
            # Cross rate should be: EUR/USD * USD/JPY = EUR/JPY
            synthetic_rate = pair1['bid'] * pair2['bid']  # EUR/JPY synthetic
            actual_rate = pair3['ask']  # EUR/JPY actual
            
            # Calculate profit in pips (JPY pairs use 100 as pip factor)
            pip_factor = 100 if 'JPY' in pair3_name else 10000
            forward_profit_pips = (synthetic_rate - actual_rate) * pip_factor
            
            # Reverse arbitrage: Sell EUR/USD, Sell USD/JPY, Buy EUR/JPY
            synthetic_rate_rev = pair1['ask'] * pair2['ask']
            actual_rate_rev = pair3['bid']
            
            reverse_profit_pips = (actual_rate_rev - synthetic_rate_rev) * pip_factor
            
            # Choose the better opportunity
            if abs(forward_profit_pips) > abs(reverse_profit_pips):
                profit_pips = forward_profit_pips
                direction = 'forward'
                trades = [
                    {'pair': pair1_name, 'action': 'buy', 'price': pair1['ask']},
                    {'pair': pair2_name, 'action': 'buy', 'price': pair2['ask']},
                    {'pair': pair3_name, 'action': 'sell', 'price': pair3['bid']}
                ]
            else:
                profit_pips = reverse_profit_pips
                direction = 'reverse'
                trades = [
                    {'pair': pair1_name, 'action': 'sell', 'price': pair1['bid']},
                    {'pair': pair2_name, 'action': 'sell', 'price': pair2['bid']},
                    {'pair': pair3_name, 'action': 'buy', 'price': pair3['ask']}
                ]
            
            # Only return if profit is significant and realistic
            if abs(profit_pips) >= self.min_profit_pips and abs(profit_pips) <= self.max_profit_pips:
                confidence = self.calculate_arbitrage_confidence(triangle, rates, abs(profit_pips))
                
                return {
                    'type': direction,
                    'triangle': triangle,
                    'profit_pips': profit_pips,
                    'confidence': confidence,
                    'trades': trades,
                    'timestamp': time.time(),
                    'market_strength': self.market_strength
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error in indirect triangle calculation: {e}")
            return None
    
    def calculate_arbitrage_confidence(self, triangle: Dict, rates: Dict, profit_pips: float) -> float:
        """Calculate confidence score for arbitrage opportunity (0-100)"""
        try:
            confidence = 50.0  # Base confidence
            
            # Profit magnitude (0-25 points)
            if profit_pips >= 5:
                confidence += min(profit_pips * 2, 25)
            else:
                confidence += profit_pips * 3  # Bonus for smaller but realistic profits
            
            # Market strength boost (0-20 points)
            market_boost = (self.market_strength / 100) * 20
            confidence += market_boost
            
            # Spread quality (0-15 points)
            avg_spread = np.mean([data.get('spread_pips', 5) for data in rates.values()])
            spread_bonus = max(0, 15 - (avg_spread * 2))
            confidence += spread_bonus
            
            # Triangle completeness (0-15 points)
            completeness_bonus = triangle['completeness'] * 15
            confidence += completeness_bonus
            
            # Volatility appropriateness (0-10 points)
            triangle_pairs = triangle['pairs']
            avg_vol = np.mean([self.volatility_data.get(pair, 5) for pair in triangle_pairs])
            if 5 <= avg_vol <= 12:  # Optimal volatility range
                confidence += 10
            elif 3 <= avg_vol <= 15:
                confidence += 5
            
            # Session quality (0-15 points)
            if len(self.active_sessions) >= 2:  # Multiple sessions active
                confidence += 15
            elif len(self.active_sessions) == 1:
                confidence += 8
            
            # Historical success rate (0-10 points)
            if self.total_signals > 0:
                success_bonus = (self.success_rate / 100) * 10
                confidence += success_bonus
            
            return min(100.0, max(0.0, confidence))
            
        except Exception as e:
            self.logger.error(f"Error calculating confidence: {e}")
            return 50.0
    
    def validate_opportunity_realism(self, opportunity: Dict) -> bool:
        """Validate that opportunity is realistic and worth trading"""
        try:
            profit_pips = abs(opportunity.get('profit_pips', 0))
            confidence = opportunity.get('confidence', 0)
            
            # Realistic profit range check
            if profit_pips < self.min_profit_pips or profit_pips > self.max_profit_pips:
                return False
            
            # Minimum confidence requirement
            if confidence < self.min_confidence_score:
                return False
            
            # Market strength requirement
            if self.market_strength < 40:
                return False
            
            # Avoid trading during very low volatility or extreme volatility
            triangle_pairs = opportunity['triangle']['pairs']
            for pair in triangle_pairs:
                vol = self.volatility_data.get(pair, 0)
                if vol < 1.0 or vol > 25.0:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating opportunity realism: {e}")
            return False
    
    def select_premium_opportunity(self, opportunities: List[Dict]) -> Optional[Dict]:
        """Select the highest quality opportunity from available options"""
        try:
            if not opportunities:
                return None
            
            # Sort by confidence score and profit potential
            opportunities.sort(key=lambda x: (x.get('confidence', 0), abs(x.get('profit_pips', 0))), reverse=True)
            
            # Additional quality check for top opportunity
            best_opportunity = opportunities[0]
            
            # Final validation
            if self.final_opportunity_validation(best_opportunity):
                return best_opportunity
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error selecting premium opportunity: {e}")
            return None
    
    def final_opportunity_validation(self, opportunity: Dict) -> bool:
        """Final validation before signaling opportunity"""
        try:
            triangle_id = opportunity['triangle']['id']
            current_time = time.time()
            
            # Check if we've had too many signals for this triangle recently
            recent_signals = [sig for sig in self.signal_history.get(triangle_id, []) 
                            if current_time - sig < 300]  # Last 5 minutes
            
            if len(recent_signals) >= 3:  # Max 3 signals per triangle per 5 minutes
                return False
            
            # Check overall signal rate (prevent spam)
            if self.total_signals > 0:
                signals_per_hour = self.total_signals / max((current_time - self.start_time) / 3600, 0.1)
                if signals_per_hour > 20:  # Max 20 signals per hour
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in final validation: {e}")
            return False
    
    def process_intelligent_opportunity(self, opportunity: Dict):
        """Process opportunity with enhanced intelligence"""
        try:
            triangle = opportunity['triangle']
            triangle_id = triangle['id']
            profit_pips = opportunity['profit_pips']
            confidence = opportunity['confidence']
            opp_type = opportunity['type']
            
            current_time = time.time()
            
            # Update signal tracking
            self.total_signals += 1
            self.quality_signals += 1  # All opportunities reaching here are quality
            self.last_signal_time[triangle_id] = current_time
            
            if triangle_id not in self.signal_history:
                self.signal_history[triangle_id] = []
            self.signal_history[triangle_id].append(current_time)
            
            # Create enhanced signal message
            session_info = '/'.join(self.active_sessions[:2]) if self.active_sessions else 'Off-hours'
            message = (f"SMART {opp_type.upper()} {triangle_id}: "
                      f"{profit_pips:+.2f}p | {confidence:.0f}% | "
                      f"Market:{self.market_strength:.0f} | {session_info}")
            
            self.logger.info(message)
            
            if self.on_signal_callback:
                self.on_signal_callback(message)
            
            # Intelligent trading decision
            if self.should_execute_intelligent_trade(opportunity):
                success = self.execute_intelligent_trade(opportunity)
                if success:
                    self.successful_trades += 1
                    trade_message = (f"EXECUTED: {opp_type} {triangle_id} | "
                                   f"{profit_pips:+.2f}p | {confidence:.0f}%")
                    self.logger.info(trade_message)
                    if self.on_trade_callback:
                        self.on_trade_callback(trade_message)
                else:
                    error_message = f"FAILED: {opp_type} {triangle_id} execution failed"
                    self.logger.warning(error_message)
        
        except Exception as e:
            self.logger.error(f"Error processing intelligent opportunity: {e}")
    
    def should_execute_intelligent_trade(self, opportunity: Dict) -> bool:
        """Intelligent trade execution decision with enhanced criteria"""
        try:
            confidence = opportunity.get('confidence', 0)
            profit_pips = abs(opportunity.get('profit_pips', 0))
            market_strength = opportunity.get('market_strength', 0)
            
            # Enhanced decision criteria
            min_confidence = 70.0  # Higher standard
            min_profit = 3.0      # Minimum 3 pips
            min_market_strength = 50.0
            
            # Adjust criteria based on market conditions
            if len(self.active_sessions) >= 2:  # Multiple sessions active
                min_confidence -= 5
                min_profit -= 0.5
            
            if market_strength > 80:  # Excellent market conditions
                min_confidence -= 10
                min_profit -= 1.0
            
            # Check criteria
            if confidence < min_confidence:
                return False
            
            if profit_pips < min_profit:
                return False
            
            if market_strength < min_market_strength:
                return False
            
            # Check position limits
            current_positions = len(self.mt5_conn.get_positions())
            if current_positions >= 3:  # Maximum 3 positions
                return False
            
            # Check recent performance
            if self.total_signals > 10 and self.success_rate < 40:  # Poor recent performance
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in intelligent trade decision: {e}")
            return False
    
    def execute_intelligent_trade(self, opportunity: Dict) -> bool:
        """Execute trade with intelligent position sizing and risk management"""
        try:
            trades = opportunity['trades']
            if not trades:
                return False
            
            # Select best trade from triangle (simplified to single trade for now)
            primary_trade = self.select_primary_trade(trades, opportunity)
            if not primary_trade:
                return False
            
            symbol = primary_trade['pair']
            action = primary_trade['action']
            confidence = opportunity.get('confidence', 50)
            profit_pips = abs(opportunity.get('profit_pips', 0))
            
            # Intelligent position sizing
            lot_size = self.calculate_intelligent_lot_size(confidence, profit_pips)
            
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
            
            # Calculate intelligent stop loss and take profit
            sl_price, tp_price = self.calculate_intelligent_sl_tp(
                symbol, execution_price, action, profit_pips, confidence
            )
            
            self.logger.info(f"Smart execution: {action.upper()} {symbol} "
                           f"{lot_size} lots at {execution_price:.5f}")
            
            # Execute with enhanced parameters
            result = self.mt5_conn.place_order(
                symbol=symbol,
                order_type=order_type,
                lots=lot_size,
                price=execution_price,
                sl=sl_price,
                tp=tp_price,
                comment=f"Smart-Arb-{opportunity['type']}"
            )
            
            if result and result.get('retcode') == mt5.TRADE_RETCODE_DONE:
                ticket = result.get('order')
                self.logger.info(f"SUCCESS: Intelligent trade executed - Ticket: {ticket}")
                
                # Record enhanced trade data
                self.record_intelligent_trade(opportunity, ticket, symbol, action, lot_size, confidence)
                return True
            else:
                error_msg = result.get('comment', 'Unknown error') if result else 'No result'
                self.logger.error(f"FAILED: Intelligent trade failed - {error_msg}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error executing intelligent trade: {e}")
            return False
    
    def select_primary_trade(self, trades: List[Dict], opportunity: Dict) -> Optional[Dict]:
        """Select the primary trade to execute from triangular trades"""
        try:
            if not trades:
                return None
            
            # For now, select the first valid trade
            # In the future, this could be enhanced to select the best trade based on:
            # - Spread quality
            # - Volatility
            # - Liquidity
            # - Historical performance
            
            for trade in trades:
                symbol = trade['pair']
                if symbol in self.market_data:
                    return trade
            
            return trades[0]  # Fallback
            
        except Exception as e:
            self.logger.error(f"Error selecting primary trade: {e}")
            return trades[0] if trades else None
    
    def calculate_intelligent_lot_size(self, confidence: float, profit_pips: float) -> float:
        """Calculate intelligent position size based on confidence and profit potential"""
        try:
            base_lot_size = 0.01  # Base size
            
            # Confidence multiplier (50-100% confidence -> 0.5-2.0x multiplier)
            confidence_multiplier = max(0.5, min(2.0, confidence / 50))
            
            # Profit potential multiplier
            profit_multiplier = max(0.8, min(1.5, profit_pips / 5))
            
            # Market strength multiplier
            market_multiplier = max(0.7, min(1.3, self.market_strength / 70))
            
            # Session multiplier
            session_multiplier = 1.2 if len(self.active_sessions) >= 2 else 1.0
            
            # Calculate final lot size
            lot_size = (base_lot_size * confidence_multiplier * 
                       profit_multiplier * market_multiplier * session_multiplier)
            
            # Apply limits
            lot_size = max(0.01, min(0.10, lot_size))  # Between 0.01 and 0.10
            lot_size = round(lot_size, 2)
            
            return lot_size
            
        except Exception as e:
            self.logger.error(f"Error calculating intelligent lot size: {e}")
            return 0.01
    
    def calculate_intelligent_sl_tp(self, symbol: str, entry_price: float, action: str, 
                                  profit_pips: float, confidence: float) -> Tuple[float, float]:
        """Calculate intelligent stop loss and take profit"""
        try:
            # Determine pip size
            pip_size = 0.01 if 'JPY' in symbol else 0.0001
            
            # Calculate stop loss (risk management)
            sl_pips = max(15, profit_pips * 2)  # Risk 2x the expected profit, minimum 15 pips
            
            # Calculate take profit (profit target)
            tp_pips = max(profit_pips * 1.5, 10)  # Target 1.5x expected profit, minimum 10 pips
            
            # Adjust based on confidence
            if confidence > 80:
                sl_pips *= 0.8  # Tighter stop loss for high confidence
                tp_pips *= 1.2  # Higher target for high confidence
            
            # Calculate actual prices
            if action == 'buy':
                sl_price = entry_price - (sl_pips * pip_size)
                tp_price = entry_price + (tp_pips * pip_size)
            else:  # sell
                sl_price = entry_price + (sl_pips * pip_size)
                tp_price = entry_price - (tp_pips * pip_size)
            
            return round(sl_price, 5), round(tp_price, 5)
            
        except Exception as e:
            self.logger.error(f"Error calculating SL/TP: {e}")
            return 0.0, 0.0
    
    def record_intelligent_trade(self, opportunity: Dict, ticket: int, symbol: str, 
                               action: str, lot_size: float, confidence: float):
        """Record executed trade with enhanced analytics"""
        try:
            record = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': opportunity['type'],
                'triangle_id': opportunity['triangle']['id'],
                'symbol': symbol,
                'action': action,
                'lot_size': lot_size,
                'expected_profit_pips': opportunity['profit_pips'],
                'confidence': confidence,
                'ticket': ticket,
                'status': 'executed',
                'market_sessions': self.active_sessions.copy(),
                'market_strength': self.market_strength,
                'volatility': self.volatility_data.get(symbol, 0),
                'spread_at_entry': self.market_data.get(symbol, {}).get('spread_pips', 0)
            }
            
            self.position_history.append(record)
            
            # Keep only last 100 records
            if len(self.position_history) > 100:
                self.position_history = self.position_history[-100:]
            
            self.logger.info(f"Intelligent trade recorded: {symbol} {action} - "
                           f"Ticket {ticket} - Confidence {confidence:.1f}%")
            
        except Exception as e:
            self.logger.error(f"Error recording intelligent trade: {e}")
    
    def update_performance_statistics(self):
        """Update enhanced performance statistics"""
        try:
            if self.total_signals > 0:
                self.success_rate = (self.successful_trades / self.total_signals) * 100
            else:
                self.success_rate = 0.0
            
            # Store start time if not set
            if not hasattr(self, 'start_time'):
                self.start_time = time.time()
                
        except Exception as e:
            self.logger.error(f"Error updating statistics: {e}")
    
    def send_status_update(self):
        """Send enhanced status update to GUI"""
        try:
            if self.on_signal_callback:
                current_time = time.time()
                uptime_hours = (current_time - getattr(self, 'start_time', current_time)) / 3600
                
                session_info = '/'.join(self.active_sessions[:2]) if self.active_sessions else 'Off-hours'
                success_rate = f"{self.success_rate:.1f}%" if self.total_signals > 0 else "N/A"
                signals_per_hour = f"{self.total_signals / max(uptime_hours, 0.1):.1f}" if uptime_hours > 0 else "0"
                
                status_message = (f"SMART V2.0: {session_info} | "
                                f"Market:{self.market_strength:.0f} | "
                                f"Success:{success_rate} | "
                                f"Signals:{self.total_signals} ({signals_per_hour}/h)")
                
                self.on_signal_callback(status_message)
                
        except Exception as e:
            self.logger.error(f"Error sending status update: {e}")
    
    def calculate_adaptive_scan_interval(self) -> float:
        """Calculate adaptive scanning interval based on market conditions"""
        try:
            base_interval = self.scan_interval
            
            # Faster scanning during high-quality market conditions
            if self.market_strength > 80:
                return base_interval * 0.7  # 30% faster
            elif self.market_strength > 60:
                return base_interval * 0.85  # 15% faster
            elif self.market_strength < 40:
                return base_interval * 1.5  # 50% slower
            else:
                return base_interval
                
        except Exception:
            return self.scan_interval
    
    def get_engine_status(self) -> Dict:
        """Get enhanced engine status for GUI"""
        try:
            current_time = time.time()
            uptime_hours = (current_time - getattr(self, 'start_time', current_time)) / 3600
            
            return {
                'running': self.running,
                'mode': 'SMART_V2.0',
                'total_signals': self.total_signals,
                'quality_signals': self.quality_signals,
                'successful_trades': self.successful_trades,
                'success_rate': f"{self.success_rate:.1f}%",
                'signals_per_hour': f"{self.total_signals / max(uptime_hours, 0.1):.1f}",
                'total_trades': len(self.position_history),
                'last_scan': datetime.now().strftime('%H:%M:%S') if self.running else 'Stopped',
                'market_data_symbols': len(self.market_data),
                'triangles_count': len(self.triangular_pairs),
                'available_pairs': len(self.currency_pairs),
                'active_sessions': self.active_sessions,
                'market_strength': f"{self.market_strength:.1f}",
                'avg_confidence': self.calculate_average_confidence(),
                'scan_frequency': f"{self.calculate_adaptive_scan_interval():.1f}s",
                'uptime_hours': f"{uptime_hours:.1f}h"
            }
        except Exception as e:
            self.logger.error(f"Error getting engine status: {e}")
            return {
                'running': False,
                'mode': 'SMART_V2.0',
                'error': str(e)
            }
    
    def calculate_average_confidence(self) -> float:
        """Calculate average confidence of recent trades"""
        try:
            recent_trades = [trade for trade in self.position_history[-20:] if 'confidence' in trade]
            if recent_trades:
                return sum(trade['confidence'] for trade in recent_trades) / len(recent_trades)
            return 0.0
        except Exception:
            return 0.0
    
    def get_market_analysis(self) -> Dict:
        """Get enhanced market analysis data"""
        try:
            analysis = {
                'active_sessions': self.active_sessions,
                'market_strength': f"{self.market_strength:.1f}",
                'session_strength': f"{getattr(self, 'session_strength', 0.5):.1f}",
                'high_volatility_pairs': [pair for pair, vol in self.volatility_data.items() if vol > 15],
                'low_spread_pairs': [pair for pair in self.currency_pairs 
                                   if pair in self.market_data and 
                                   self.market_data[pair].get('spread_pips', 10) < 2],
                'total_opportunities_today': self.total_signals,
                'quality_opportunities': self.quality_signals,
                'success_rate': f"{self.success_rate:.1f}%",
                'best_performing_triangles': self.get_best_performing_triangles(),
                'average_profit_pips': self.calculate_average_profit_pips(),
                'trading_efficiency': f"{self.quality_signals / max(self.total_signals, 1) * 100:.1f}%"
            }
            return analysis
        except Exception as e:
            self.logger.error(f"Error getting market analysis: {e}")
            return {}
    
    def get_best_performing_triangles(self) -> List[str]:
        """Get best performing triangular arbitrage pairs"""
        try:
            triangle_performance = {}
            
            for trade in self.position_history[-50:]:  # Last 50 trades
                triangle_id = trade.get('triangle_id')
                if triangle_id:
                    if triangle_id not in triangle_performance:
                        triangle_performance[triangle_id] = {'count': 0, 'success': 0, 'avg_profit': 0}
                    
                    triangle_performance[triangle_id]['count'] += 1
                    if trade.get('status') == 'executed':
                        triangle_performance[triangle_id]['success'] += 1
                    
                    expected_profit = trade.get('expected_profit_pips', 0)
                    triangle_performance[triangle_id]['avg_profit'] += expected_profit
            
            # Calculate success rates and sort
            triangle_rates = []
            for triangle_id, data in triangle_performance.items():
                if data['count'] >= 2:  # At least 2 trades
                    success_rate = data['success'] / data['count']
                    avg_profit = data['avg_profit'] / data['count']
                    combined_score = success_rate * 0.7 + (avg_profit / 10) * 0.3
                    triangle_rates.append((triangle_id, combined_score))
            
            triangle_rates.sort(key=lambda x: x[1], reverse=True)
            return [triangle for triangle, score in triangle_rates[:5]]  # Top 5
            
        except Exception:
            return []
    
    def calculate_average_profit_pips(self) -> float:
        """Calculate average expected profit in pips"""
        try:
            recent_trades = [trade for trade in self.position_history[-30:] 
                           if 'expected_profit_pips' in trade]
            if recent_trades:
                return sum(abs(trade['expected_profit_pips']) for trade in recent_trades) / len(recent_trades)
            return 0.0
        except Exception:
            return 0.0

# Maintain backward compatibility
ArbitrageEngine = SmartArbitrageEngine

# Example usage
if __name__ == "__main__":
    print("Smart Arbitrage Engine V2.0 - Enhanced Intelligence & Realistic Trading")
    print("Features:")
    print("   - Real triangular arbitrage mathematics")
    print("   - Enhanced market intelligence")
    print("   - Quality signal filtering (5-10 signals/hour)")
    print("   - Realistic profit expectations (2-50 pips)")
    print("   - Intelligent position sizing")
    print("   - Advanced risk management")
    print("   - Market session awareness")
    print("   - Performance analytics")