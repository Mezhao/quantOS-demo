# encoding: utf-8

from data.calendar import Calendar
from quantos.backtest import common
from quantos.backtest.analyze.pnlreport import PnlManager
from quantos.backtest.event.eventEngine import Event
from quantos.backtest.event.eventType import EVENT
from quantos.backtest.pubsub import Subscriber
from quantos.data.basic.marketdata import Bar
from quantos.data.basic.trade import Trade
from quantos.util import dtutil
from quantos.util import fileio


class BacktestInstance(Subscriber):
    def __init__(self):
        Subscriber.__init__(self)
        
        self.strategy = None
        self.start_date = 0
        self.end_date = 0
        self.current_date = 0
        self.last_date = 0
        self.folder = ''
        
        self.calendar = Calendar()
        
        self.props = None
        
        self.ctx = None
    
    def init_from_config(self, props, strategy, data_api=None, dataview=None, gateway=None, context=None):
        """
        
        Parameters
        ----------
        props
        strategy
        data_api
        dataview
        gateway
        context : Context

        Returns
        -------

        """
        self.props = props
        
        self.start_date = props.get("start_date")
        self.end_date = props.get("end_date")
        
        self.ctx = context
        # TODO
        self.ctx.add_universe(props['universe'])
        
        strategy.context = self.ctx
        # strategy.context.data_api = data_api
        # strategy.context.gateway = gateway
        # strategy.context.calendar = self.calendar
        
        strategy.init_from_config(props)
        strategy.initialize(common.RUN_MODE.BACKTEST)
        
        self.strategy = strategy
        
        return True


class AlphaBacktestInstance(BacktestInstance):
    def __init__(self):
        BacktestInstance.__init__(self)
        
        self.last_rebalance_date = 0
        self.current_rebalance_date = 0
        self.trade_days = None
    
    def _is_trade_date(self, start, end, date, data_server):
        if self.trade_days is None:
            df, msg = data_server.daily('000300.SH', start, end, fields="close")
            self.trade_days = df.loc[:, 'trade_date'].values
        return date in self.trade_days
    
    def go_next_date(self):
        """update self.current_date and last_date."""
        if self.ctx.gateway.match_finished:
            self.current_date = dtutil.get_next_period_day(self.current_date,
                                                                  self.strategy.period, self.strategy.days_delay)
            if self.current_rebalance_date > 0:
                self.last_rebalance_date = self.current_rebalance_date
            else:
                self.last_rebalance_date = self.start_date
            self.current_rebalance_date = self.current_date
            self.last_date = self.calendar.get_last_trade_date(self.current_date)
        else:
            # TODO here we must make sure the matching will not last to next period
            self.current_date = self.calendar.get_next_trade_date(self.current_date)
        
        while (self.current_date < self.end_date
               and not self._is_trade_date(self.start_date, self.end_date, self.current_date,
                                           self.ctx.data_api)):
            print "WARNING: not trade date, go next day."
            self.current_date = self.calendar.get_next_trade_date(self.current_date)
            self.current_rebalance_date = self.current_date
            self.last_date = self.calendar.get_last_trade_date(self.current_date)
    
    def run_alpha(self):
        gateway = self.ctx.gateway
        
        self.current_date = self.start_date
        while True:
            self.go_next_date()
            if self.current_date > self.end_date:
                break
            
            if gateway.match_finished:
                self.on_new_day(self.last_date)
                df_dic = self.strategy.get_univ_prices()  # access data
                self.strategy.re_balance_plan_before_open(df_dic, suspensions=[])
                
                self.on_new_day(self.current_date)
                self.strategy.send_bullets()
            else:
                self.on_new_day(self.current_date)
            
            df_dic = self.strategy.get_univ_prices()  # access data
            trade_indications = gateway.match(df_dic, self.current_date)
            for trade_ind in trade_indications:
                self.strategy.on_trade_ind(trade_ind)
        
        print "Backtest done. {:d} days, {:.2e} trades in total.".format(len(self.trade_days),
                                                                         len(self.strategy.pm.trades))
    
    def on_new_day(self, date):
        self.ctx.trade_date = date
        self.strategy.on_new_day(date)
        self.ctx.gateway.on_new_day(date)
    
    def save_results(self, folder='../output/'):
        import pandas as pd
        
        trades = self.strategy.pm.trades
        
        type_map = {'task_id': str,
                    'entrust_no': str,
                    'entrust_action': str,
                    'symbol': str,
                    'fill_price': float,
                    'fill_size': int,
                    'fill_date': int,
                    'fill_time': int,
                    'fill_no': str}
        # keys = trades[0].__dict__.keys()
        ser_list = dict()
        for key in type_map.keys():
            v = [t.__getattribute__(key) for t in trades]
            ser = pd.Series(data=v, index=None, dtype=type_map[key], name=key)
            ser_list[key] = ser
        df_trades = pd.DataFrame(ser_list)
        df_trades.index.name = 'index'
        
        fn = folder + 'trades.csv'
        fileio.create_dir(fn)
        df_trades.to_csv(fn)
        
        fileio.save_json(self.props, folder + 'configs.json')

        print ("Backtest results has been successfully saved to:\n" + folder)


class AlphaBacktestInstance_dv(AlphaBacktestInstance):
    def position_adjust(self):
        """
        adjust happens after market close
        Before each re-balance day, adjust for all dividend and cash paid actions during the last period.
        We assume all cash will be re-invested.
        Since we adjust our position at next re-balance day, PnL before that may be incorrect.
        """
        # start = self.calendar.get_next_trade_date(self.last_rebalance_date)  # start will be one day later
        start = self.last_rebalance_date  # start will be one day later
        end = self.current_rebalance_date  # end is the same to ensure position adjusted for dividend on rebalance day
        df_adj = self.ctx.dataview.get_ts('adjust_factor',
                                          start_date=start, end_date=end)
        pm = self.strategy.pm
        
        for symbol in pm.holding_securities:
            ser = df_adj.loc[:, symbol]
            ser_div = ser.div(ser.shift(1)).fillna(1.0)
            mask_diff = ser_div != 1
            ser_adj = ser_div.loc[mask_diff]
            for date, ratio in ser_adj.iteritems():
                pos_old = pm.get_position(symbol).curr_size
                # TODO pos will become float, original: int
                pos_new = pos_old * ratio
                pos_diff = pos_new - pos_old  # must be positive
                if pos_diff <= 0:
                    # TODO this is possible
                    # raise ValueError("pos_diff <= 0")
                    continue
                
                trade_ind = Trade()
                trade_ind.symbol = symbol
                trade_ind.task_id = 101010
                trade_ind.entrust_no = 101010
                trade_ind.entrust_action = common.ORDER_ACTION.BUY  # for now only BUY
                trade_ind.send_fill_info(price=0.0, size=pos_diff, date=date, time=0, no=101010)
                
                self.strategy.on_trade_ind(trade_ind)
        '''
        adj_curr = self.ctx.dataview.get_snapshot(self.current_rebalance_date, fields='adjust_factor')
        adj_last = self.ctx.dataview.get_snapshot(self.last_rebalance_date, fields='adjust_factor')
        cols = adj_curr.index
        v = adj_curr.values.flatten()/adj_last.values.flatten()
        adj_ratio = dict(zip(list(cols), list(v)))

        pm = self.strategy.pm
        for sec in pm.holding_securities:
            r = adj_ratio[sec]
            pm.set_position(sec, self.current_rebalance_date, r)
        '''
    
    def delist_adjust(self):
        pass
    
    def run_alpha(self):
        gateway = self.ctx.gateway
        
        self.current_date = self.start_date
        while True:
            # switch trade date
            self.go_next_date()
            
            if self.current_date > self.end_date:
                break

            # match orders or re-balance
            if gateway.match_finished:
                # position adjust according to dividend, cash paid, de-list actions during the last period
                # two adjust must in order
                self.position_adjust()
                self.delist_adjust()
    
                # plan re-balance before new day
                self.on_new_day(self.last_date)
                # univ_price_dic = self.get_univ_prices(field_name="close_adj,open_adj,high_adj,low_adj")  # access data
                self.strategy.re_balance_plan_before_open()
                
                # do re-balance on new day
                self.on_new_day(self.current_date)
                
                univ_price_dic = self.get_univ_prices(field_name="close,vwap,open,high,low")  # access data
                suspensions = self.get_suspensions()
                self.strategy.re_balance_plan_after_open(univ_price_dic, suspensions)
                self.strategy.send_bullets()
            else:
                self.on_new_day(self.current_date)
                univ_price_dic = self.get_univ_prices(field_name="close,vwap,open,high,low")  # access data
            
            # return trade indications
            trade_indications = gateway.match(univ_price_dic, self.current_date)
            for trade_ind in trade_indications:
                self.strategy.on_trade_ind(trade_ind)
        
        print "Backtest done. {:d} days, {:.2e} trades in total.".format(len(self.ctx.dataview.dates),
                                                                         len(self.strategy.pm.trades))
        
    def get_univ_prices(self, field_name='close'):
        dv = self.ctx.dataview
        df = dv.get_snapshot(self.current_date, fields=field_name)
        gp = df.groupby(by='symbol')
        return {sec: df for sec, df in gp}
    
    def _is_trade_date(self, start, end, date, data_server):
        return date in self.ctx.dataview.dates
    
    def get_suspensions(self):
        trade_status = self.ctx.dataview.get_snapshot(self.current_date, fields='trade_status')
        trade_status = trade_status.loc[:, 'trade_status']
        mask_sus = trade_status != u'交易'.encode('utf-8')
        return list(trade_status.loc[mask_sus].index.values)
    

class EventBacktestInstance(BacktestInstance):
    def __init__(self):
        super(EventBacktestInstance, self).__init__()
        
        self.pnlmgr = None
        self.bar_type = 1

    def init_from_config(self, props, strategy, data_api=None, dataview=None, gateway=None, context=None):
        self.props = props

        data_api.init_from_config(props)
        data_api.initialize()

        gateway.register_callback('portfolio manager', strategy.pm)

        self.start_date = self.props.get("start_date")
        self.end_date = self.props.get("end_date")
        self.bar_type = props.get("bar_type")

        self.ctx = context
        self.strategy = strategy
        self.ctx.universe = props.get("symbol")

        strategy.context = self.ctx
        strategy.init_from_config(props)
        strategy.initialize(common.RUN_MODE.BACKTEST)

        self.pnlmgr = PnlManager()
        self.pnlmgr.setStrategy(strategy)
        self.pnlmgr.initFromConfig(props, data_api)
    
    def go_next_trade_date(self):
        next_dt = self.calendar.get_next_trade_date(self.current_date)
        
        self.last_date = self.current_date
        self.current_date = next_dt
    
    def run_event(self):
        data_api = self.ctx.data_api
        universe = self.ctx.universe
        
        data_api.add_batch_subscribe(self, universe)
        
        self.current_date = self.start_date
        
        def __extract(func):
            return lambda event: func(event.data, **event.kwargs)
        
        ee = self.strategy.eventEngine  # TODO event-driven way of lopping, is it proper?
        ee.register(EVENT.CALENDAR_NEW_TRADE_DATE, __extract(self.strategy.on_new_day))
        ee.register(EVENT.MD_QUOTE, __extract(self.process_quote))
        ee.register(EVENT.MARKET_CLOSE, __extract(self.close_day))
        
        while self.current_date <= self.end_date:  # each loop is a new trading day
            quotes = data_api.get_daily_quotes(self.current_date)
            if quotes is not None:
                # gateway.oneNewDay()
                e_newday = Event(EVENT.CALENDAR_NEW_TRADE_DATE)
                e_newday.data = self.current_date
                ee.put(e_newday)
                ee.process_once()  # this line should be done on another thread
                
                # self.strategy.onNewday(self.current_date)
                self.strategy.pm.on_new_day(self.current_date, self.last_date)
                self.strategy.trade_date = self.current_date
                
                for quote in quotes:
                    # self.processQuote(quote)
                    e_quote = Event(EVENT.MD_QUOTE)
                    e_quote.data = quote
                    ee.put(e_quote)
                    ee.process_once()
                
                # self.strategy.onMarketClose()
                # self.closeDay(self.current_date)
                e_close = Event(EVENT.MARKET_CLOSE)
                e_close.data = self.current_date
                ee.put(e_close)
                ee.process_once()
                # self.strategy.onSettle()
                
                self.last_date = self.current_date
            else:
                # no quotes because of holiday or other issues. We don't update last_date
                print "in backtest.py: function run(): {} quotes is None, continue.".format(self.last_date)
            
            self.current_date = self.go_next_trade_date(self.current_date)
            
            # self.strategy.onTradingEnd()

    def on_new_day(self):
        self.ctx.gateway.on_new_day(self.current_date)
        self.strategy.on_new_day(self.current_date)
        print 'on_new_day in backtest {}'.format(self.current_date)

    def run(self):
        self.current_date = self.start_date
    
        while self.current_date <= self.end_date:  # each loop is a new trading day
            self.go_next_trade_date()
            self.on_new_day()
            
            df_quotes, msg = self.ctx.data_api.bar(symbol=self.ctx.universe, start_time=200000, end_time=160000,
                                                   trade_date=self.current_date, freq=self.bar_type)
            if df_quotes is None:
                print msg
                continue
                
            df_quotes = df_quotes.sort_values(by='time')
            quotes_list = Bar.create_from_df(df_quotes)
            
            # for idx in df_quotes.index:
            #     df_row = df_quotes.loc[[idx], :]
            for quote in quotes_list:
                self.process_quote(quote)
        
        print "Backtest done."
        
    def process_quote(self, quote):
        # match
        trade_results = self.ctx.gateway.process_quote(quote)
        
        # trade indication
        for tradeInd, statusInd in trade_results:
            self.strategy.on_trade_ind(tradeInd)
            self.strategy.on_order_status(statusInd)
        
        # on_quote
        self.strategy.on_quote(quote)

    def generate_report(self):
        return self.pnlmgr.generateReport()
