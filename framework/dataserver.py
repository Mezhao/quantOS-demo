# encoding: UTF-8

from datetime import datetime
from datetime import timedelta

from abc import abstractmethod

from pubsub import Publisher

import jzquant
from jzquant import jzquant_api
from framework import common

########################################################################
class Quote(object):
    #----------------------------------------------------------------------
    def __init__(self, type):
        self.type = type
        self.frequency   = 0
        self.symbol      = ''
        self.refsymbol   = ''
        self.time        = ''
        self.open        = 0.0
        self.high        = 0.0
        self.low         = 0.0
        self.close       = 0.0
        self.volume      = 0.0
        self.turnover    = 0.0
        self.oi          = 0.0
        self.settle      = 0.0
        self.preclose    = 0.0
        self.presettle   = 0.0
        self.bidprice    = []
        self.bidvol      = []
        self.askprice    = []
        self.askvol      = []
        
        self.format      = '%Y%m%d %H:%M:%S %f'
        
    def getDate(self):
        dt = datetime.strptime(self.time , self.format)
        return int(dt.strftime('%Y%m%d'))
    
    def getTime(self):
        dt = datetime.strptime(self.time , self.format)
        return int(dt.strftime('%H%M%S'))
    
    def show(self):
        print self.type, self.time, self.symbol, self.open, self.high, self.low, self.close, self.volume, self.turnover 
        
########################################################################
class DataServer(Publisher):
    
    #----------------------------------------------------------------------
    def __init__(self):
        Publisher.__init__(self)
    
    @abstractmethod    
    def initConfig(self, props):
        pass
    
    
    @abstractmethod    
    def initialization(self):
        pass
    
    @abstractmethod    
    def start(self):
        pass
    
    @abstractmethod    
    def join(self):
        pass
    
    @abstractmethod    
    def stop(self):
        pass
    
    @abstractmethod    
    def getNextQuote(self):
        pass
    
    def subscribe(self, subscriber, univlist):
        
        for i in xrange(len(univlist)):
            self.onSubscribe(subscriber, univlist[i])
    
    
########################################################################
class JshHistoryBarDataServer(DataServer):
    
    #----------------------------------------------------------------------
    def __init__(self):
        self.api    = None
        self.addr   = ''
        self.bar_type   = common.QUOTE_TYPE.MINBAR
        self.symbol     = ''
        
        self.daily_quotes_cache      = None

        DataServer.__init__(self)
    
    def initConfig(self, props):
        self.addr       = props.get('jsh.addr')
        self.bar_type   = props.get('bar_type')
        self.symbol     = props.get('symbol')
    
    def initialization(self):
        self.api = jzquant_api.connect(addr=self.addr,user="TODO", password="TODO")

    def start(self):
        pass
    
    def join(self):
        pass
    
    def stop(self):
        pass

    """
    def getNextQuote(self):
        if (self.daily_quotes_cache is not None and self.cache_pos < len(self.daily_quotes_cache)):
            quote = self.daily_quotes_cache[self.cache_pos]
            self.cache_pos = self.cache_pos + 1
            return quote
        
        else:
            self.daily_quotes_cache = None
            self.cache_pos = 0
            
            while (self.daily_quotes_cache is None or len(self.daily_quotes_cache) == 0):
                if (self.next_day_pos > self.end_date):
                    return None
                
                self.daily_quotes_cache = self.makeCache(self.next_day_pos)
                self.next_day_pos = self.getNextDate(self.next_day_pos)
            
            return self.getNextQuote()
    """

    def get_daily_quotes(self, target_date):
        self.daily_quotes_cache = self.makeCache(target_date)
        return self.daily_quotes_cache

    """
    def getNextDate(self, read_pos):
        dt = datetime.strptime(str(read_pos) , '%Y%m%d')
        # next_dt = dt + timedelta(days = 1)
        # next_pos = int(next_dt.strftime('%Y%m%d'))
        # today = self.calendar.transferDtToInt(dt)
        next_pos = self.calendar.getNextTradeDate(read_pos)
        return next_pos
    """

    def makeTime(self, timestamp):
        return timestamp.strftime('%Y%m%d %H:%M:%S %f')
        
    def makeCache(self, target_date):
        """Return a list of quotes of a single day. If any error, print error msg and return None.

        """
        topicList = self.getTopic()
        
        for i in xrange(len(topicList)):
            instcode = topicList[i]
            pd_bar, msg = self.api.jsh(instcode, fields='', date=target_date,
                                       start_time='', end_time = '', bar_size=self.bar_type.value)
            
            if pd_bar is not None:
                cache = []
            
                dict_bar = pd_bar.transpose().to_dict()
                keys = sorted(dict_bar.keys())
                
                for j in xrange(len(keys)):
                    key = keys[j]
                    bar = dict_bar.get(key)
                    quote = Quote(self.bar_type)
                    quote.symbol   = bar['SYMBOL']
                    quote.open     = bar['OPEN']
                    quote.close    = bar['CLOSE']
                    quote.high     = bar['HIGH']
                    quote.low      = bar['LOW']
                    quote.volume   = bar['VOLUME']
                    quote.turnover = bar['TURNOVER']
                    quote.oi       = bar['OPENINTEREST']
                    quote.time     = self.makeTime(key)
                    
                    cache.append(quote)
                return cache
            else:
                print msg

        return None

# 直接运行脚本可以进行测试
if __name__ == '__main__':
    
    props = {}
    props['jsh.addr'] = 'tcp://10.2.0.14:61616'
    props['bar_type'] = common.QUOTE_TYPE.MINBAR
    props['symbol'] = '600030.SH'
    
    server = JshHistoryBarDataServer()
    server.initConfig(props)
    
    server.initialization()
    
    server.subscribe(None, ['600030.SH'])

    quotes = server.get_daily_quotes(20170712)
    for quote in quotes:
        print quote.symbol, quote.time, quote.open, quote.high
