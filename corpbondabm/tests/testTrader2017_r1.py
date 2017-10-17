import unittest

import numpy as np

from corpbondabm.trader2017_r1 import BuySide, MutualFund, InsuranceCo, HedgeFund
from corpbondabm.bondmarket2017_r1 import BondMarket

MM_FRACTION = 0.15
IC_EQUITY = 0.4


class TestTrader(unittest.TestCase):


    def setUp(self):
        self.bondmarket = BondMarket('bondmarket1')
        self.bondmarket.add_bond('MM101', 500, 1, .0175, .015, 2)
        self.bondmarket.add_bond('MM102', 500, 2, .025, .0175, 2)
        self.bondmarket.add_bond('MM103', 1000, 5, .0225, .025, 2)
        self.bondmarket.add_bond('MM104', 2000, 10, .024, .026, 2)
        self.bondmarket.add_bond('MM105', 1000, 25, .04, .0421, 2)
        index_weights = self.bondmarket.compute_weights_from_nominal()
        bond_list = []
        mm_portfolio = {}
        ic_portfolio = {}
        for bond in self.bondmarket.bonds:
            mm_bond = {'Name': bond['Name'], 'Nominal': MM_FRACTION*bond['Nominal'], 'Maturity': bond['Maturity'],
                       'Coupon': bond['Coupon'], 'Yield': bond['Yield'], 'Price': bond['Price']}
            ic_bond = {'Name': bond['Name'], 'Nominal': (1-MM_FRACTION)*bond['Nominal'], 'Maturity': bond['Maturity'],
                       'Coupon': bond['Coupon'], 'Yield': bond['Yield'], 'Price': bond['Price']}
            bond_list.append(bond['Name'])
            mm_portfolio[bond['Name']] = mm_bond
            ic_portfolio[bond['Name']] = ic_bond
            
        self.b1 = BuySide('b1', bond_list, mm_portfolio)
            
        self.m1 = MutualFund('m1', 0.03, 0.08, 0.05, bond_list, mm_portfolio, index_weights)
        prices = {k:self.m1.portfolio[k]['Price'] for k in self.m1.bond_list}
        bond_value = self.m1.compute_portfolio_value(prices)
        self.m1.cash = self.m1.target*bond_value/(1-self.m1.target)
        self.m1.add_nav_to_history(0, prices)
        
        self.i1 = InsuranceCo('i1', 1-IC_EQUITY, bond_list, ic_portfolio)
        prices = {k:self.i1.portfolio[k]['Price'] for k in self.i1.bond_list}
        bond_value = self.i1.compute_portfolio_value(prices)
        self.i1.equity = IC_EQUITY*bond_value/(1-IC_EQUITY)
        
        self.h1 = HedgeFund('h1', bond_list, mm_portfolio) # use MF portfolio for now
        
        
    def test_repr_BuySide(self):
        self.assertEqual('BuySide(b1)', '{0}'.format(self.b1))
        
    def test_make_rfq(self):
        self.m1.make_rfq('MM101', 'sell', 10)
        expected = {'order_id': 'm1_1', 'name': 'MM101', 'side': 'sell', 'amount': 10}
        self.assertDictEqual(self.m1.rfq_collector[0], expected)
        
    def test_compute_portfolio_value(self):
        prices = {'MM101': 100, 'MM102': 100, 'MM103': 100, 'MM104': 100, 'MM105': 100}
        portfolio_value = self.m1.compute_portfolio_value(prices)
        bond_values = np.sum([x['Nominal'] for x in self.bondmarket.bonds])
        expected = MM_FRACTION*bond_values
        self.assertEqual(portfolio_value, expected)

    
    def test_repr_MutualFund(self):
        self.assertEqual('BuySide(m1, MutualFund)', '{0}'.format(self.m1))
        
    def test_add_nav_to_history(self):
        self.m1.nav_history = {}
        prices = {'MM101': 100, 'MM102': 100, 'MM103': 100, 'MM104': 100, 'MM105': 100}
        self.m1.add_nav_to_history(1, prices)
        self.assertDictEqual(self.m1.nav_history, {1: 788.91782200258319})
          
    def test_compute_flow(self):
        self.m1.nav_history[1] = 100
        self.m1.nav_history[5] = 100
        self.m1.nav_history[6] = 101
        flow = self.m1.compute_flow(7)
        self.assertAlmostEqual(flow, 1.1888, 4)
        self.m1.nav_history[1] = 100
        self.m1.nav_history[5] = 100
        self.m1.nav_history[6] = 95
        flow = self.m1.compute_flow(7)
        self.assertAlmostEqual(flow, -5.492, 4)
        
    def test_modify_portfolioMM(self):
        self.m1.cash = 0
        confirm_sell = {'name': 'MM101', 'side': 'sell', 'price': 100, 'size': 5}
        confirm_buy = {'name': 'MM105', 'side': 'buy', 'price': 100, 'size': 10}
        self.assertEqual(self.m1.cash, 0)
        self.m1.modify_portfolio(confirm_sell)
        self.assertEqual(self.m1.cash, 500)
        self.assertEqual(self.m1.portfolio['MM101']['Nominal'], 70)
        self.m1.modify_portfolio(confirm_buy)
        self.assertEqual(self.m1.cash, -500)
        self.assertEqual(self.m1.portfolio['MM105']['Nominal'], 160)
        
    def test_make_portfolio_decisionMF(self):
        prices = {'MM101': 101, 'MM102': 98, 'MM103': 95, 'MM104': 105, 'MM105': 100}
        # Do nothing: index doesn't change cash between limits
        self.m1.nav_history[1] = 750
        self.m1.nav_history[5] = 750
        self.m1.nav_history[6] = 750
        self.m1.cash = 30
        self.m1.portfolio['MM101']['Nominal'] = 73
        self.m1.portfolio['MM102']['Nominal'] = 72
        self.m1.portfolio['MM103']['Nominal'] = 145
        self.m1.portfolio['MM104']['Nominal'] = 285
        self.m1.portfolio['MM105']['Nominal'] = 137.5
        self.m1.make_portfolio_decision(7, prices)
        self.assertFalse(self.m1.rfq_collector)
        # Sell some: index decline, low on cash
        self.m1.nav_history[1] = 750
        self.m1.nav_history[5] = 750
        self.m1.nav_history[6] = 737.5
        self.m1.cash = 25
        self.m1.portfolio['MM101']['Nominal'] = 73
        self.m1.portfolio['MM102']['Nominal'] = 72
        self.m1.portfolio['MM103']['Nominal'] = 145
        self.m1.portfolio['MM104']['Nominal'] = 285
        self.m1.portfolio['MM105']['Nominal'] = 137.5
        self.m1.make_portfolio_decision(7, prices)
        expected = [
                    {'order_id': 'm1_1', 'name': 'MM101', 'side': 'sell', 'amount': 2.0},
                    {'order_id': 'm1_2', 'name': 'MM102', 'side': 'sell', 'amount': 1.0},
                    {'order_id': 'm1_3', 'name': 'MM103', 'side': 'sell', 'amount': 3.0},
                    {'order_id': 'm1_4', 'name': 'MM104', 'side': 'sell', 'amount': 4.0}
                    ]
        for i in range(len(self.m1.rfq_collector)):
            with self.subTest(i=i):
                self.assertDictEqual(self.m1.rfq_collector[i], expected[i])
        # Buy some: index increase, extra cash
        self.m1.nav_history[1] = 750
        self.m1.nav_history[5] = 750
        self.m1.nav_history[6] = 767.5
        self.m1.cash = 50
        self.m1.portfolio['MM101']['Nominal'] = 68
        self.m1.portfolio['MM102']['Nominal'] = 79
        self.m1.portfolio['MM103']['Nominal'] = 138
        self.m1.portfolio['MM104']['Nominal'] = 293
        self.m1.portfolio['MM105']['Nominal'] = 139.5
        self.m1.make_portfolio_decision(7, prices)
        expected = [
                    {'order_id': 'm1_5', 'name': 'MM101', 'side': 'buy', 'amount': 6.0},
                    {'order_id': 'm1_6', 'name': 'MM103', 'side': 'buy', 'amount': 10.0},
                    {'order_id': 'm1_7', 'name': 'MM104', 'side': 'buy', 'amount': 6.0},
                    {'order_id': 'm1_8', 'name': 'MM105', 'side': 'buy', 'amount': 9.0}
                    ]
        for i in range(len(self.m1.rfq_collector)):
            with self.subTest(i=i):
                self.assertDictEqual(self.m1.rfq_collector[i], expected[i])
        
        
    def test_repr_InsuranceCo(self):
        self.assertEqual('BuySide(i1, InsuranceCo)', '{0}'.format(self.i1))
        
    def test_modify_portfolioIC(self):
        self.i1.equity = 0
        confirm_sell = {'name': 'MM101', 'side': 'sell', 'price': 100, 'size': 5}
        confirm_buy = {'name': 'MM105', 'side': 'buy', 'price': 100, 'size': 10}
        self.assertEqual(self.i1.equity, 0)
        self.i1.modify_portfolio(confirm_sell)
        self.assertEqual(self.i1.equity, 500)
        self.assertEqual(self.i1.portfolio['MM101']['Nominal'], 420)
        self.i1.modify_portfolio(confirm_buy)
        self.assertEqual(self.i1.equity, -500)
        self.assertEqual(self.i1.portfolio['MM105']['Nominal'], 860)
        
    def test_make_portfolio_decisionIC(self):
        prices = {'MM101': 101, 'MM102': 98, 'MM103': 95, 'MM104': 105, 'MM105': 100}
        equity_ret = 0.02
        np.random.seed(1) # randomly selects 'MM104'
        self.i1.make_portfolio_decision(prices, equity_ret)
        expected = {'order_id': 'i1_1', 'name': 'MM104', 'side': 'sell', 'amount': 5.0}
        self.assertDictEqual(self.i1.rfq_collector[0], expected)
        
   
    def test_repr_HedgeFund(self):
        self.assertEqual('BuySide(h1, HedgeFund)', '{0}'.format(self.h1))