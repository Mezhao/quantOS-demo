import numpy as np

from quantos.backtest import common
from quantos.backtest.strategy import EventDrivenStrategy
from quantos.data.basic.order import Order


class DoubleMaStrategy(EventDrivenStrategy):
    """"""
    def __init__(self):
        EventDrivenStrategy.__init__(self)
        self.symbol = ''
        self.fastN = 14
        self.slowN = 45
        self.bar = None
        self.bufferCount = 0
        self.bufferSize = 20
        self.closeArray = np.zeros(self.bufferSize)
        self.fastMa = 0
        self.slowMa = 0
        self.pos = 0
    
    def init_from_config(self, props):
        self.symbol = props.get('symbol')
        self.initbalance = props.get('init_balance')
    
    def initialize(self, runmode):
        self.initUniverse(self.symbol)
    
    def onCycle(self):
        pass
    
    def createOrder(self, quote, price, size):
        order = Order.new_order(quote.symbol, "", price, size, quote.getDate(), quote.time)
        order.order_type = common.ORDER_TYPE.LIMIT
        return order
    
    def buy(self, quote, price, size):
        order = self.createOrder(quote, price, size)
        order.entrust_action = common.ORDER_ACTION.BUY
        self.context.gateway.send_order(order, '', '')
    
    def sell(self, quote, price, size):
        order = self.createOrder(quote, price, size)
        order.entrust_action = common.ORDER_ACTION.SELL
        self.context.gateway.send_order(order, '', '')
    
    def cover(self, quote, price, size):
        order = self.createOrder(quote, price, size)
        order.entrust_action = common.ORDER_ACTION.BUY
        self.context.gateway.send_order(order, '', '')
    
    def short(self, quote, price, size):
        order = self.createOrder(quote, price, size)
        order.entrust_action = common.ORDER_ACTION.SELL
        self.context.gateway.send_order(order, '', '')
    
    def onNewday(self, trade_date):
        print 'new day comes ' + str(trade_date)
    
    def onQuote(self, quote):
        quote_date = quote.getDate()
        p = self.pm.get_position(quote.symbol, quote_date)
        if p is None:
            self.pos = 0
        else:
            self.pos = p.curr_size
        
        self.closeArray[0:self.bufferSize - 1] = self.closeArray[1:self.bufferSize]
        self.closeArray[-1] = quote.close
        self.bufferCount += 1
        
        if self.bufferCount <= self.bufferSize:
            return
        self.fastMa = self.closeArray[-self.fastN - 1:-1].mean()
        self.slowMa = self.closeArray[-self.slowN - 1:-1].mean()
        
        if self.fastMa > self.slowMa:
            if self.pos == 0:
                self.buy(quote, quote.close + 3, 1)
            
            elif self.pos < 0:
                self.cover(quote, quote.close + 3, 1)
                self.buy(quote, quote.close + 3, 1)
        
        elif self.fastMa < self.slowMa:
            if self.pos == 0:
                self.short(quote, quote.close - 3, 1)
            elif self.pos > 0:
                self.sell(quote, quote.close - 3, 1)
                self.short(quote, quote.close - 3, 1)
