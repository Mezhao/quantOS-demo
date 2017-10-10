# encoding: UTF-8

from abc import abstractmethod

import numpy as np
import pandas as pd

from quantos.backtest import common
from quantos.backtest.pubsub import Publisher
from quantos.data.dataapi import DataApi
from quantos.data import align
from quantos.backtest.calendar import Calendar


class BaseDataServer(Publisher):
    """
    Abstract base class providing both historic and live data
    from various data sources.
    Current API version: 1.8

    Derived classes of DataServer hide different data source, but use the same API.

    Attributes
    ----------
    source_name : str
        Name of data source.

    Methods
    -------
    subscribe
    quote
    daily
    bar
    tick
    query

    """
    def __init__(self, name=""):
        Publisher.__init__(self)
        
        if name:
            self.source_name = name
        else:
            self.source_name = str(self.__class__.__name__)
    
    def init_from_config(self, props):
        pass
    
    def initialize(self):
        pass
    
    def subscribe(self, targets, callback):
        """
        Subscribe real time market data, including bar and tick,
        processed by respective callback function.

        Parameters
        ----------
        targets : str
            Security and type, eg. "000001.SH/tick,cu1709.SHF/1m"
        callback : dict of {str: callable}
            {'on_tick': func1, 'on_bar': func2}
            Call back functions.

        """
        # TODO for now it will not publish event
        for target in targets.split(','):
            sec, data_type = target.split('/')
            if data_type == 'tick':
                func = callback['on_tick']
            else:
                func = callback['on_bar']
            self.add_subscriber(func, target)
    
    @abstractmethod
    def quote(self, symbol, fields=""):
        """
        Query latest market data in DataFrame.
        
        Parameters
        ----------
        symbol : str
        fields : str, optional
            default ""

        Returns
        -------
        df : pd.DataFrame
        msg : str
            error code and error message joined by comma

        """
        pass
    
    @abstractmethod
    def daily(self, symbol, start_date, end_date, fields="", adjust_mode=None):
        """
        Query dar bar,
        support auto-fill suspended securities data,
        support auto-adjust for splits, dividends and distributions.

        Parameters
        ----------
        symbol : str
            support multiple securities, separated by comma.
        start_date : int or str
            YYYMMDD or 'YYYY-MM-DD'
        end_date : int or str
            YYYMMDD or 'YYYY-MM-DD'
        fields : str, optional
            separated by comma ',', default "" (all fields included).
        adjust_mode : str or None, optional
            None for no adjust;
            'pre' for forward adjust;
            'post' for backward adjust.

        Returns
        -------
        df : pd.DataFrame
            columns:
                symbol, code, trade_date, open, high, low, close, volume, turnover, vwap, oi, suspended
        msg : str
            error code and error message joined by comma

        Examples
        --------
        df, msg = api.daily("00001.SH,cu1709.SHF",start_date=20170503, end_date=20170708,
                            fields="open,high,low,last,volume", fq=None, skip_suspended=True)

        """
        pass
    
    @abstractmethod
    def bar(self, symbol, start_time=200000, end_time=160000, trade_date=None, freq='1m', fields=""):
        """
        Query minute bars of various type, return DataFrame.

        Parameters
        ----------
        symbol : str
            support multiple securities, separated by comma.
        start_time : int (HHMMSS) or str ('HH:MM:SS')
            Default is market open time.
        end_time : int (HHMMSS) or str ('HH:MM:SS')
            Default is market close time.
        trade_date : int (YYYMMDD) or str ('YYYY-MM-DD')
            Default is current trade_date.
        fields : str, optional
            separated by comma ',', default "" (all fields included).
        freq : backtest.common.MINBAR_TYPE, optional
            {'1m', '5m', '15m'}, Minute bar type, default is '1m'

        Returns
        -------
        df : pd.DataFrame
            columns:
                symbol, code, date, time, trade_date, freq, open, high, low, close, volume, turnover, vwap, oi
        msg : str
            error code and error message joined by comma

        Examples
        --------
        df, msg = api.bar("000001.SH,cu1709.SHF", start_time="09:56:00", end_time="13:56:00",
                          trade_date="20170823", fields="open,high,low,last,volume", freq="5m")

        """
        # TODO data_server DOES NOT know "current date".
        pass
    
    @abstractmethod
    def tick(self, symbol, start_time=200000, end_time=160000, trade_date=None, fields=""):
        """
        Query tick data in DataFrame.
        
        Parameters
        ----------
        symbol : str
        start_time : int (HHMMSS) or str ('HH:MM:SS')
            Default is market open time.
        end_time : int (HHMMSS) or str ('HH:MM:SS')
            Default is market close time.
        trade_date : int (YYYMMDD) or str ('YYYY-MM-DD')
            Default is current trade_date.
        fields : str, optional
            separated by comma ',', default "" (all fields included).

        Returns
        -------
        df : pd.DataFrame
        err_msg : str
            error code and error message joined by comma
            
        """
        pass
    
    @abstractmethod
    def query(self, view, filter, fields):
        """
        Query reference data.
        Input query type and parameters, return DataFrame.
        
        Parameters
        ----------
        view : str
            Type of reference data. See doc for details.
        filter : str
            Query conditions, separated by '&'.
        fields : str
            Fields to return, separated by ','.

        Returns
        -------
        df : pd.DataFrame
        err_msg : str
            error code and error message joined by comma

        """
        pass
    
    @abstractmethod
    def get_split_dividend(self):
        pass
    
    def get_suspensions(self):
        pass


class JzDataServer(BaseDataServer):
    """
    JzDataServer uses data from jz's local database.

    """
    # TODO no validity check for input parameters
    
    def __init__(self):
        BaseDataServer.__init__(self)
        
        address = 'tcp://10.1.0.210:8910'
        self.api = DataApi(address, use_jrpc=False)
        self.api.set_timeout(60)
        r, msg = self.api.login("test", "123")
        if not r:
            print msg
        else:
            print "DataAPI login success."
        
        self.REPORT_DATE_FIELD_NAME = 'report_date'

    def daily(self, symbol, start_date, end_date,
              fields="", adjust_mode=None):
        df, err_msg = self.api.daily(symbol=symbol, start_date=start_date, end_date=end_date,
                                     fields=fields, adjust_mode=adjust_mode, data_format="")
        # trade_status performance warning
        return df, err_msg

    def bar(self, symbol,
            start_time=200000, end_time=160000, trade_date=None,
            freq='1m', fields=""):
        df, msg = self.api.bar(symbol=symbol, fields=fields,
                               start_time=start_time, end_time=end_time, trade_date=trade_date,
                               freq='1m', data_format="")
        return df, msg
    
    def query(self, view, filter="", fields="", **kwargs):
        """
        Get various reference data.
        
        Parameters
        ----------
        view : str
            data source.
        fields : str
            Separated by ','
        filter : str
            filter expressions.
        kwargs

        Returns
        -------
        df : pd.DataFrame
        msg : str
            error code and error message, joined by ','
        
        Examples
        --------
        res3, msg3 = ds.query("wd.secDailyIndicator", fields="price_level,high_52w_adj,low_52w_adj",
                              filter="start_date=20170907&end_date=20170907",
                              orderby="trade_date",
                              data_format='pandas')
            view does not change. fileds can be any field predefined in reference data api.

        """
        df, msg = self.api.query(view, fields=fields, filter=filter, data_format="", **kwargs)
        return df, msg
    
    def get_suspensions(self):
        return None
    
    def get_trade_date(self, start_date, end_date, symbol=None, is_datetime=False):
        if symbol is None:
            symbol = '000300.SH'
        df, msg = self.daily(symbol, start_date, end_date, fields="close")
        res = df.loc[:, 'trade_date'].values
        if is_datetime:
            res = Calendar.convert_int_to_datetime(res)
        return res
    
    @staticmethod
    def _dic2url(d):
        """
        Convert a dict to str like 'k1=v1&k2=v2'
        
        Parameters
        ----------
        d : dict

        Returns
        -------
        str

        """
        l = ['='.join([key, str(value)]) for key, value in d.items()]
        return '&'.join(l)

    def query_wd_fin_stat(self, type_, symbol, start_date, end_date, fields=""):
        """
        Helper function to call data_api.query with 'wd.income' more conveniently.
        
        Parameters
        ----------
        type_ : {'income', 'balance_sheet', 'cash_flow'}
        symbol : str
            separated by ','
        start_date : int
            Annoucement date in results will be no earlier than start_date
        end_date : int
            Annoucement date in results will be no later than start_date
        fields : str, optional
            separated by ',', default ""

        Returns
        -------
        df : pd.DataFrame
            index date, columns fields
        msg : str

        """
        view_map = {'income': 'wd.income', 'cash_flow': 'wd.cashFlow', 'balance_sheet': 'wd.balanceSheet',
                    'fin_indicator': 'wd.finIndicator'}
        view_name = view_map.get(type_, None)
        if view_name is None:
            raise NotImplementedError("type_ = {:s}".format(type_))
        
        dic_argument = {'symbol': symbol,
                        'start_date': start_date,
                        'end_date': end_date,
                        'update_flag': '0'}
        if view_name != 'wd.finIndicator':
            dic_argument.update({'report_type': '408002000'})  # joint sheet
        
        filter_argument = self._dic2url(dic_argument)  # 0 means first time, not update
        
        res, msg = self.query(view_name, fields=fields, filter=filter_argument,
                              order_by=self.REPORT_DATE_FIELD_NAME)
        # change data type
        try:
            cols = list(set.intersection({'ann_date', 'report_date'}, set(res.columns)))
            dic_dtype = {col: int for col in cols}
            res = res.astype(dtype=dic_dtype)
        except:
            pass
        
        return res, msg

    def OLD_query_wd_balance_sheet(self, symbol, start_date, end_date, fields="", extend=0):
        """
        Helper function to call data_api.query with 'wd.income' more conveniently.
        
        Parameters
        ----------
        symbol : str
            separated by ','
        start_date : int
            Annoucement date in results will be no earlier than start_date
        end_date : int
            Annoucement date in results will be no later than start_date
        fields : str, optional
            separated by ',', default ""
        extend : int, optional
            If not zero, extend for weeks.

        Returns
        -------
        df : pd.DataFrame
            index date, columns fields
        msg : str

        """
        # extend 1 year
        if extend:
            start_dt = Calendar.convert_int_to_datetime(start_date)
            start_dt = start_dt - pd.Timedelta(weeks=extend)
            start_date = Calendar.convert_datetime_to_int(start_dt)
    
        filter_argument = self._dic2url({'symbol': symbol,
                                         'start_date': start_date,
                                         'end_date': end_date,
                                         'report_type': '408002000'})
    
        return self.query("wd.balanceSheet", fields=fields, filter=filter_argument,
                          order_by=self.REPORT_DATE_FIELD_NAME)

    def OLD_query_wd_cash_flow(self, symbol, start_date, end_date, fields="", extend=0):
        """
        Helper function to call data_api.query with 'wd.income' more conveniently.
        
        Parameters
        ----------
        symbol : str
            separated by ','
        start_date : int
            Annoucement date in results will be no earlier than start_date
        end_date : int
            Annoucement date in results will be no later than start_date
        fields : str, optional
            separated by ',', default ""
        extend : int, optional
            If not zero, extend for weeks.

        Returns
        -------
        df : pd.DataFrame
            index date, columns fields
        msg : str

        """
        # extend 1 year
        if extend:
            start_dt = Calendar.convert_int_to_datetime(start_date)
            start_dt = start_dt - pd.Timedelta(weeks=extend)
            start_date = Calendar.convert_datetime_to_int(start_dt)
    
        filter_argument = self._dic2url({'symbol': symbol,
                                         'start_date': start_date,
                                         'end_date': end_date,
                                         'report_type': '408002000'})
    
        return self.query("wd.cashFlow", fields=fields, filter=filter_argument,
                          order_by=self.REPORT_DATE_FIELD_NAME)
    
    def query_wd_dailyindicator(self, symbol, start_date, end_date, fields=""):
        """
        Helper function to call data_api.query with 'wd.secDailyIndicator' more conveniently.
        
        Parameters
        ----------
        symbol : str
            separated by ','
        start_date : int
        end_date : int
        fields : str, optional
            separated by ',', default ""

        Returns
        -------
        df : pd.DataFrame
            index date, columns fields
        msg : str
        
        """
        filter_argument = self._dic2url({'symbol': symbol,
                                         'start_date': start_date,
                                         'end_date': end_date})
    
        return self.query("wd.secDailyIndicator",
                          fields=fields,
                          filter=filter_argument,
                          orderby="trade_date")

    def _get_index_comp(self, index, start_date, end_date):
        """
        Return all securities that have been in index during start_date and end_date.
        
        Parameters
        ----------
        index : str
            separated by ','
        start_date : int
        end_date : int

        Returns
        -------
        list

        """
        filter_argument = self._dic2url({'index_code': index,
                                         'start_date': start_date,
                                         'end_date': end_date})
    
        df_io, msg = self.query("wd.indexCons", fields="",
                                filter=filter_argument, orderby="symbol")
        return df_io, msg
    
    def get_index_comp(self, index, start_date, end_date):
        """
        Return all securities that have been in index during start_date and end_date.
        
        Parameters
        ----------
        index : str
            separated by ','
        start_date : int
        end_date : int

        Returns
        -------
        list

        """
        df_io, msg = self._get_index_comp(index, start_date, end_date)
        if msg != '0,':
            print msg
        return list(np.unique(df_io.loc[:, 'symbol']))
    
    def get_index_comp_df(self, index, start_date, end_date):
        """
        Get index components on each day during start_date and end_date.
        
        Parameters
        ----------
        index : str
            separated by ','
        start_date : int
        end_date : int

        Returns
        -------
        res : pd.DataFrame
            index dates, columns all securities that have ever been components,
            values are 0 (not in) or 1 (in)
        msg : str

        """
        df_io, msg = self._get_index_comp(index, start_date, end_date)
        if msg != '0,':
            print msg
        
        def str2int(s):
            if isinstance(s, (str, unicode)):
                return int(s) if s else 99999999
            elif isinstance(s, (int, np.integer, float, np.float)):
                return s
            else:
                raise NotImplementedError("type s = {}".format(type(s)))
        df_io.loc[:, 'in_date'] = df_io.loc[:, 'in_date'].apply(str2int)
        df_io.loc[:, 'out_date'] = df_io.loc[:, 'out_date'].apply(str2int)
        
        # df_io.set_index('symbol', inplace=True)
        dates = self.get_trade_date(start_date=start_date, end_date=end_date, symbol=index)

        dic = dict()
        gp = df_io.groupby(by='symbol')
        for sec, df in gp:
            mask = np.zeros_like(dates, dtype=int)
            for idx, row in df.iterrows():
                bool_index = np.logical_and(dates > row['in_date'], dates < row['out_date'])
                mask[bool_index] = 1
            dic[sec] = mask
            
        res = pd.DataFrame(index=dates, data=dic)
        
        return res

    @staticmethod
    def _group_df_to_dict(df, by):
        gp = df.groupby(by=by)
        res = {key: value for key, value in gp}
        return res
    
    def get_industry_df(self, symbol, start_date, end_date, type_='SW'):
        """
        Get index components on each day during start_date and end_date.
        
        Parameters
        ----------
        symbol : str
            separated by ','
        start_date : int
        end_date : int
        type_ : {'SW', 'ZZ'}

        Returns
        -------
        res : pd.DataFrame
            index dates, columns symbols
            values are industry code

        """
        df_raw = self.get_industry_raw(symbol, type_=type_)
        
        dic_sec = self._group_df_to_dict(df_raw, by='symbol')
        dic_sec = {sec: df.drop_duplicates().sort_values(by='in_date', axis=0).reset_index()
                   for sec, df in dic_sec.viewitems()}

        df_ann = pd.concat([df.loc[:, 'in_date'].rename(sec) for sec, df in dic_sec.viewitems()], axis=1)
        df_value = pd.concat([df.loc[:, 'industry1_code'].rename(sec) for sec, df in dic_sec.viewitems()], axis=1)

        dates_arr = self.get_trade_date(start_date, end_date)
        df_industry = align.align(df_value, df_ann, dates_arr)
        
        # TODO before industry classification is available, we assume they belong to their first group.
        df_industry = df_industry.fillna(method='bfill')
        df_industry = df_industry.astype(str)
        
        return df_industry
        
    def get_industry_raw(self, symbol, type_='ZZ'):
        """
        Get daily industry of securities from ShenWanHongYuan or ZhongZhengZhiShu.
        
        Parameters
        ----------
        symbol : str
            separated by ','
        type_ : {'SW', 'ZZ'}

        Returns
        -------
        df : pd.DataFrame

        """
        if type_ == 'SW':
            src = u'申万研究所'.encode('utf-8')
        elif type_ == 'ZZ':
            src = u'中证指数有限公司'.encode('utf-8')
        else:
            raise ValueError("type_ must be one of SW of ZZ")
    
        filter_argument = self._dic2url({'symbol': symbol,
                                         'industry_src': src})
        fields_list = ['symbol', 'industry1_code', 'industry1_name']
    
        df_raw, msg = self.query("lb.secIndustry", fields=','.join(fields_list),
                                 filter=filter_argument, orderby="symbol")
        if msg != '0,':
            print msg
        return df_raw.astype(dtype={'in_date': int,
                                    # 'out_date': int
                                    })

