import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging
import statistics

class ProfitManager:
    """จัดการกำไรแต่ละ position ตาม lot size"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.base_profit_per_lot = 500  # $500 per 1.0 lot
        self.quick_profit_ratio = 0.3   # เก็บกำไรเร็วที่ 30% ของเป้าหมาย
        
    def calculate_dynamic_targets(self, position: Dict) -> Dict:
        """คำนวณเป้าหมายกำไรตาม lot size"""
        lot_size = position.get('volume', 0.01)
        
        targets = {
            'quick_target': lot_size * self.base_profit_per_lot * self.quick_profit_ratio,
            'normal_target': lot_size * self.base_profit_per_lot,
            'max_target': lot_size * self.base_profit_per_lot * 1.5,
            'lot_size': lot_size
        }
        
        return targets
    
    def should_take_profit(self, position: Dict) -> Dict:
        """ตัดสินใจว่าควรเก็บกำไรหรือไม่"""
        profit = position.get('profit', 0)
        targets = self.calculate_dynamic_targets(position)
        
        decision = {
            'action': 'hold',
            'reason': '',
            'profit_ratio': 0,
            'targets': targets
        }
        
        if profit >= targets['max_target']:
            decision.update({
                'action': 'close_full',
                'reason': f"Max profit reached: ${profit:.1f} >= ${targets['max_target']:.1f}",
                'profit_ratio': 1.0
            })
        elif profit >= targets['normal_target']:
            decision.update({
                'action': 'close_partial',
                'reason': f"Normal target reached: ${profit:.1f} >= ${targets['normal_target']:.1f}",
                'profit_ratio': 0.7  # ปิด 70%
            })
        elif profit >= targets['quick_target']:
            decision.update({
                'action': 'close_quick',
                'reason': f"Quick profit available: ${profit:.1f} >= ${targets['quick_target']:.1f}",
                'profit_ratio': 0.3  # ปิด 30%
            })
        
        return decision

class PortfolioGuardian:
    """ดูแล portfolio รวม - กั้นหน้าทุนและประคอง"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.min_portfolio_profit = 0  # รักษาให้ไม่ติดลบ
        self.profit_lock_threshold = 100  # ล็อคกำไรเมื่อเกิน $100
        
    def analyze_portfolio(self, positions: List[Dict]) -> Dict:
        """วิเคราะห์สถานะ portfolio"""
        analysis = {
            'total_profit': 0,
            'total_lots': 0,
            'profitable_positions': [],
            'losing_positions': [],
            'currency_exposure': {},
            'correlation_groups': {},
            'risk_score': 0
        }
        
        # วิเคราะห์แต่ละ position
        for pos in positions:
            profit = pos.get('profit', 0)
            volume = pos.get('volume', 0)
            symbol = pos.get('symbol', '')
            
            analysis['total_profit'] += profit
            analysis['total_lots'] += volume
            
            if profit > 0:
                analysis['profitable_positions'].append(pos)
            else:
                analysis['losing_positions'].append(pos)
            
            # วิเคราะห์ currency exposure
            self._update_currency_exposure(symbol, volume, pos.get('type', 0), analysis['currency_exposure'])
        
        # คำนวณ risk score
        analysis['risk_score'] = self._calculate_risk_score(analysis)
        
        return analysis
    
    def _update_currency_exposure(self, symbol: str, volume: float, pos_type: int, exposure: Dict):
        """อัพเดท currency exposure"""
        if len(symbol) >= 6:
            base_currency = symbol[:3]
            quote_currency = symbol[3:6].replace('.', '').replace('v', '')
            
            if pos_type == 0:  # BUY
                exposure[base_currency] = exposure.get(base_currency, 0) + volume
                exposure[quote_currency] = exposure.get(quote_currency, 0) - volume
            else:  # SELL
                exposure[base_currency] = exposure.get(base_currency, 0) - volume
                exposure[quote_currency] = exposure.get(quote_currency, 0) + volume
    
    def _calculate_risk_score(self, analysis: Dict) -> float:
        """คำนวณ risk score (0-100)"""
        total_profit = analysis['total_profit']
        profitable_count = len(analysis['profitable_positions'])
        losing_count = len(analysis['losing_positions'])
        total_positions = profitable_count + losing_count
        
        if total_positions == 0:
            return 0
        
        # Risk factors
        profit_factor = max(0, min(50, (total_profit + 100) / 4))  # -100 to +100 = 0 to 50 points
        balance_factor = (profitable_count / total_positions) * 30  # 0 to 30 points
        exposure_factor = min(20, len(analysis['currency_exposure']) * 2)  # 0 to 20 points
        
        risk_score = profit_factor + balance_factor + exposure_factor
        return min(100, max(0, risk_score))

class SmartClosingEngine:
    """ตัดสินใจปิดไม้อัจฉริยะ"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.correlation_threshold = 0.7
        
    def create_closing_strategy(self, analysis: Dict, profit_decisions: List[Dict]) -> Dict:
        """สร้างกลยุทธ์ปิดไม้"""
        strategy = {
            'immediate_closes': [],
            'partial_closes': [],
            'hedge_recommendations': [],
            'hold_positions': [],
            'portfolio_action': 'monitor'
        }
        
        total_profit = analysis['total_profit']
        risk_score = analysis['risk_score']
        
        # 🎯 Portfolio-level decisions
        if total_profit > 150:  # กำไรมาก → ล็อคกำไร
            strategy['portfolio_action'] = 'lock_profits'
            # เลือกไม้ที่กำไรดีที่สุดมาปิด
            profitable_sorted = sorted(analysis['profitable_positions'], 
                                     key=lambda x: x.get('profit', 0), reverse=True)
            
            lock_count = min(3, len(profitable_sorted) // 2)  # ปิดครึ่งหนึ่งหรือสูงสุด 3 ไม้
            for i in range(lock_count):
                strategy['immediate_closes'].append({
                    'position': profitable_sorted[i],
                    'reason': 'Portfolio profit lock',
                    'close_ratio': 1.0
                })
        
        elif total_profit < -50:  # ขาดทุน → หา hedge
            strategy['portfolio_action'] = 'hedge_portfolio'
            hedge_recommendations = self._find_hedge_opportunities(analysis)
            strategy['hedge_recommendations'] = hedge_recommendations
        
        elif risk_score < 30:  # ความเสี่ยงสูง → ปิดไม้อันตราย
            strategy['portfolio_action'] = 'reduce_risk'
            dangerous_positions = self._identify_dangerous_positions(analysis)
            for pos in dangerous_positions:
                strategy['immediate_closes'].append({
                    'position': pos,
                    'reason': 'High risk position',
                    'close_ratio': 1.0
                })
        
        # 💰 Individual position decisions
        for decision in profit_decisions:
            if decision['action'] == 'close_full':
                strategy['immediate_closes'].append({
                    'position': decision['position'],
                    'reason': decision['reason'],
                    'close_ratio': 1.0
                })
            elif decision['action'] in ['close_partial', 'close_quick']:
                strategy['partial_closes'].append({
                    'position': decision['position'],
                    'reason': decision['reason'],
                    'close_ratio': decision['profit_ratio']
                })
        
        return strategy
    
    def _find_hedge_opportunities(self, analysis: Dict) -> List[Dict]:
        """หาโอกาส hedge"""
        hedge_opportunities = []
        
        # ตัวอย่างการหา hedge แบบง่าย
        currency_exposure = analysis['currency_exposure']
        
        for currency, exposure in currency_exposure.items():
            if abs(exposure) > 0.1:  # exposure เกิน 0.1 lot
                hedge_opportunities.append({
                    'currency': currency,
                    'exposure': exposure,
                    'suggested_hedge': f"Consider hedging {currency} exposure of {exposure:.2f} lots"
                })
        
        return hedge_opportunities
    
    def _identify_dangerous_positions(self, analysis: Dict) -> List[Dict]:
        """ระบุ positions ที่อันตราย"""
        dangerous = []
        
        for pos in analysis['losing_positions']:
            profit = pos.get('profit', 0)
            volume = pos.get('volume', 0)
            
            # อันตรายถ้าขาดทุนเกิน $50 per 0.1 lot
            danger_threshold = -(volume * 500)
            
            if profit < danger_threshold:
                dangerous.append(pos)
        
        return dangerous

class RiskBalancer:
    """จัดการความเสี่ยงและสมดุล portfolio"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.max_risk_per_currency = 1.0  # สูงสุด 1.0 lot per currency
        
    def balance_portfolio(self, analysis: Dict) -> Dict:
        """สร้างแผนสมดุล portfolio"""
        balance_plan = {
            'rebalance_needed': False,
            'currency_adjustments': [],
            'position_adjustments': [],
            'risk_level': 'LOW'
        }
        
        # เช็ค currency exposure
        currency_exposure = analysis['currency_exposure']
        
        for currency, exposure in currency_exposure.items():
            if abs(exposure) > self.max_risk_per_currency:
                balance_plan['rebalance_needed'] = True
                balance_plan['currency_adjustments'].append({
                    'currency': currency,
                    'current_exposure': exposure,
                    'target_exposure': self.max_risk_per_currency if exposure > 0 else -self.max_risk_per_currency,
                    'action': 'reduce_exposure'
                })
        
        # กำหนด risk level
        total_profit = analysis['total_profit']
        risk_score = analysis['risk_score']
        
        if risk_score > 70:
            balance_plan['risk_level'] = 'LOW'
        elif risk_score > 40:
            balance_plan['risk_level'] = 'MEDIUM'
        else:
            balance_plan['risk_level'] = 'HIGH'
        
        return balance_plan

class MasterPortfolioManager:
    """ระบบเก็บกำไรครบวงจร"""
    
    def __init__(self, mt5_connection, config_path: str = "config.json"):
        self.mt5_conn = mt5_connection
        self.config = self.load_config(config_path)
        
        # Initialize components
        self.profit_manager = ProfitManager(self.config)
        self.portfolio_guardian = PortfolioGuardian(self.config)
        self.smart_closing = SmartClosingEngine(self.config)
        self.risk_balancer = RiskBalancer(self.config)
        
        # Statistics
        self.stats = {
            'profits_taken': 0,
            'total_profit_locked': 0,
            'hedges_executed': 0,
            'risk_reductions': 0,
            'last_action_time': None
        }
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Callbacks
        self.on_profit_callback = None
        self.on_hedge_callback = None
        self.on_error_callback = None
    
    def load_config(self, config_path: str) -> dict:
        """Load configuration"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Config load error: {e}")
            return {}
    
    def set_callbacks(self, profit_callback=None, hedge_callback=None, error_callback=None):
        """Set GUI callbacks"""
        self.on_profit_callback = profit_callback
        self.on_hedge_callback = hedge_callback
        self.on_error_callback = error_callback
    
    def execute_portfolio_strategy(self) -> Dict:
        """รันกลยุทธ์ portfolio ครบวงจร"""
        try:
            # 1. ดึงข้อมูล positions ปัจจุบัน
            positions = self.mt5_conn.get_positions()
            if not positions:
                return {'status': 'no_positions', 'total_profit': 0}
            
            # 2. วิเคราะห์ portfolio
            portfolio_analysis = self.portfolio_guardian.analyze_portfolio(positions)
            
            # 3. วิเคราะห์กำไรแต่ละไม้
            profit_decisions = []
            for pos in positions:
                decision = self.profit_manager.should_take_profit(pos)
                if decision['action'] != 'hold':
                    profit_decisions.append({
                        'position': pos,
                        'action': decision['action'],
                        'reason': decision['reason'],
                        'profit_ratio': decision['profit_ratio']
                    })
            
            # 4. สร้างกลยุทธ์ปิดไม้
            closing_strategy = self.smart_closing.create_closing_strategy(portfolio_analysis, profit_decisions)
            
            # 5. จัดสมดุล portfolio
            balance_plan = self.risk_balancer.balance_portfolio(portfolio_analysis)
            
            # 6. Execute actions
            actions_executed = self.execute_closing_actions(closing_strategy)
            
            # 7. Update statistics
            self.update_statistics(actions_executed, portfolio_analysis)
            
            # 8. Return status
            return {
                'status': 'completed',
                'total_profit': portfolio_analysis['total_profit'],
                'risk_score': portfolio_analysis['risk_score'],
                'actions_executed': actions_executed,
                'portfolio_health': 'HEALTHY' if portfolio_analysis['total_profit'] >= 0 else 'AT_RISK',
                'balance_plan': balance_plan,
                'profitable_positions': len(portfolio_analysis['profitable_positions']),
                'losing_positions': len(portfolio_analysis['losing_positions'])
            }
            
        except Exception as e:
            self.logger.error(f"Error in portfolio strategy: {e}")
            if self.on_error_callback:
                self.on_error_callback(f"Portfolio error: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def execute_closing_actions(self, strategy: Dict) -> Dict:
        """Execute การปิดไม้ตาม strategy"""
        actions = {
            'full_closes': 0,
            'partial_closes': 0,
            'total_profit_locked': 0,
            'positions_closed': []
        }
        
        try:
            # Execute immediate closes
            for close_action in strategy['immediate_closes']:
                position = close_action['position']
                ticket = position.get('ticket')
                profit = position.get('profit', 0)
                close_ratio = close_action.get('close_ratio', 1.0)
                
                if close_ratio >= 1.0:
                    # ปิดเต็มจำนวน
                    if self.mt5_conn.close_position(ticket):
                        actions['full_closes'] += 1
                        actions['total_profit_locked'] += profit
                        actions['positions_closed'].append({
                            'ticket': ticket,
                            'symbol': position.get('symbol'),
                            'profit': profit,
                            'type': 'full_close'
                        })
                        
                        if self.on_profit_callback:
                            self.on_profit_callback(f"💰 Profit locked: {position.get('symbol')} ${profit:.1f}")
                
                else:
                    # ปิดบางส่วน (ถ้า MT5 รองรับ)
                    # Note: MT5 บางโบรกเกอร์ไม่รองรับ partial close
                    # ใช้วิธีปิดเต็มจำนวนแทน
                    if self.mt5_conn.close_position(ticket):
                        actions['partial_closes'] += 1
                        actions['total_profit_locked'] += profit * close_ratio
                        actions['positions_closed'].append({
                            'ticket': ticket,
                            'symbol': position.get('symbol'),
                            'profit': profit * close_ratio,
                            'type': 'partial_close'
                        })
            
            # Log hedge recommendations
            for hedge in strategy['hedge_recommendations']:
                if self.on_hedge_callback:
                    self.on_hedge_callback(f"🛡️ Hedge recommended: {hedge}")
            
        except Exception as e:
            self.logger.error(f"Error executing closing actions: {e}")
        
        return actions
    
    def update_statistics(self, actions: Dict, analysis: Dict):
        """Update statistics"""
        self.stats['profits_taken'] += actions['full_closes'] + actions['partial_closes']
        self.stats['total_profit_locked'] += actions['total_profit_locked']
        self.stats['last_action_time'] = datetime.now()
    
    def get_portfolio_status(self) -> Dict:
        """Get current portfolio status"""
        try:
            positions = self.mt5_conn.get_positions()
            if not positions:
                return {'status': 'empty', 'message': 'No positions'}
            
            analysis = self.portfolio_guardian.analyze_portfolio(positions)
            
            return {
                'total_positions': len(positions),
                'profitable_positions': len(analysis['profitable_positions']),
                'losing_positions': len(analysis['losing_positions']),
                'total_profit': analysis['total_profit'],
                'total_lots': analysis['total_lots'],
                'risk_score': analysis['risk_score'],
                'currency_exposure': analysis['currency_exposure'],
                'stats': self.stats.copy()
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def force_profit_lock(self, min_profit: float = 20) -> Dict:
        """บังคับเก็บกำไรไม้ที่กำไรเกินกำหนด"""
        try:
            positions = self.mt5_conn.get_positions()
            locked_profits = []
            
            for pos in positions:
                profit = pos.get('profit', 0)
                if profit >= min_profit:
                    ticket = pos.get('ticket')
                    if self.mt5_conn.close_position(ticket):
                        locked_profits.append({
                            'symbol': pos.get('symbol'),
                            'profit': profit,
                            'ticket': ticket
                        })
            
            total_locked = sum([p['profit'] for p in locked_profits])
            
            return {
                'success': True,
                'positions_closed': len(locked_profits),
                'total_profit_locked': total_locked,
                'details': locked_profits
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

# Example usage and testing
if __name__ == "__main__":
    print("🎯 Portfolio Guardian System")
    print("💰 ระบบเก็บกำไรครบวงจร")
    print("🛡️ Portfolio Protection & Profit Management")
    print("⚖️ Dynamic Risk Balancing")
    print("\n📋 Features:")
    print("   - Dynamic profit targets based on lot size")
    print("   - Portfolio-level profit protection")
    print("   - Smart closing decisions")
    print("   - Currency exposure management")
    print("   - Risk balancing")
    print("   - Recovery system coordination")