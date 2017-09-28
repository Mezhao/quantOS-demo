import time

import jrpc_py
# import jrpc
import utils


#def set_log_dir(log_dir):
#    if log_dir:
#        jrpc.set_log_dir(log_dir)

#class DataApiCallback:
#    """DataApi Callback
#
#    def on_quote(quote):
#        pass
#        
#    def on_connection()
#    """
#
#    def __init__(self):
#        self.on_quote = None

class DataApi:
    
    def __init__(self, addr, use_jrpc=False):
        """Create DataApi client.
        
        If use_jrpc, try to load the C version of JsonRpc. If failed, use pure
        Python version of JsonRpc.
        """
        self._remote = None
#        if use_jrpc:
#            try:
#                import jrpc
#                self._remote = jrpc.JRpcClient()
#            except Exception as e:
#                print "Can't load jrpc", e.message
        
        if not self._remote:
            self._remote = jrpc_py.JRpcClient()

        self._remote.on_rpc_callback = self._on_rpc_callback
        self._remote.on_disconnected = self._on_disconnected
        self._remote.on_connected    = self._on_connected
        self._remote.connect(addr)

        self._on_jsq_callback = None

        self._connected   = False
        self._loggined    = False
        self._username    = ""
        self._password    = ""
        self._data_format = "default"
        self._callback = None
        self._schema = []
        self._schema_id = 0
        self._sub_hash = ""
        self._subscribed_set = set()
        self._timeout = 20

    def __del__(self):
        self._remote.close()
    

    def _on_disconnected(self):
        """JsonRpc callback"""
#        print "DataApi: _on_disconnected"
        self._connected = False
        
        if self._callback:
            self._callback("connection", False)

    def _on_connected(self):
        """JsonRpc callback"""
        self._connected = True

        self._do_login()
        self._do_subscribe()

        if self._callback:
            self._callback("connection", True)

    def _check_session(self):
        if not self._connected:
            return (False, "no connection")
        elif self._loggined:
            return (True, "")
        elif self._username and self._password:
            return self._do_login()
        else:
            return (False, "no login session")


    def close(self):
        self._remote.close()

    def set_data_format(self, format):
        """Set queried data format.
        
        Available formats are:
            ""        -- Don't convert data, usually the type is map
            "pandas"  -- Convert table likely data to DataFrame
        """
        self._data_format = format
        
    def _get_format(self, format, default_format):
        if format:
            return format
        elif self._data_format != "default":
            return self._data_format
        else:
            return default_format

    def set_callback(self, callback):
        self._callback = callback

    def _convert_quote_ind(self, quote_ind):
        """Convert original quote_ind to a map.
        
        The original quote_ind contains field index instead of field name!
        """
        
        if quote_ind != self._schema_id:
            return None

        indicators = quote_ind.indicators
        values     = quote_ind.values

        max_index = len(self._schema)

        quote = {}
        for i in xrange(len(indicators)):
            if indicators[i] < max_index: 
                quote[self._schema[indicators[i]].name] = values[i]
            else:
                quote[str(indicators[i])] =  values[i]

        return quote

    def _on_rpc_callback(self, method, data):
        #print "_on_rpc_callback:", method, data

        try:
            if method == "jsq.quote_ind":
                if self._callback:
                    q = self._convert_quote_ind(data)
                    if q :
                        self._callback("quote", q)

            elif method == ".sys.heartbeat":
                if 'sub_hash' in data:
                    if self._sub_hash and self._sub_hash != data['sub_hash']:
                        print "sub_hash is not same", self._sub_hash, data['sub_hash']
                        self._do_subscribe()

        except Exception as e:
            print "Can't load jrpc", e.message

    def login(self, username, password):
        
        for i in xrange(3):
            if self._connected:
                break
            time.sleep(1)

        if not self._connected:
            return (None, "-1,no connection")
        
        self._username = username
        self._password = password
        return self._do_login()

    def _do_login(self):
        # Shouldn't check connected flag here. ZMQ is a mesageq queue!
        # if !self._connected :
        #    return (False, "-1,no connection")

        if self._username and self._password:
            rpc_params = { "username" : self._username,
                           "password" : self._password }

            cr = self._remote.call("auth.login", rpc_params)
            r, msg = utils.extract_result(cr, data_format="", class_name="UserInfo")
            self._loggined = r
            return (r, msg)
        else:
            self._loggined = None
            return (False, "-1,empty username or password")
        
    def logout(self):
        
        self._loggined = None

        rpc_params = { }
    
        cr = self._remote.call("auth.logout", rpc_params)
        return utils.extract_result(cr)

    def _call_rpc(self, method, data_format, data_class, **kwargs):

        r, msg = self._check_session()
        if not r:
            return (r, msg)

        rpc_params = { }
        for kw in kwargs.items():
            rpc_params[ str(kw[0]) ] = kw[1]

        cr = self._remote.call(method, rpc_params, timeout=self._timeout)
        
        return utils.extract_result(cr, data_format=data_format, class_name=data_class)

    def quote(self, symbol, fields="", data_format="", **kwargs):
        
        r, msg = self._call_rpc("jsq.query",
                                self._get_format(data_format, ""),
                                "Quote",
                                symbol = str(symbol),
                                fields   = fields,
                                **kwargs)
        return (r, msg)    

    def _do_subscribe(self):
        """Subscribe again when reconnected or hash_code is not same"""
        if not self._subscribed_set: return

        codes = list(self._subscribed_set)
        codes.sort()
        
        # XXX subscribe with default fields!
        rpc_params = {"symbol" : ",".join(codes),
                      "fields"   : "" }

        cr = self._remote.call("jsq.subscribe", rpc_params)
        
        rsp, msg = utils.extract_result(cr, data_format="", class_name="SubRsp")
        if not rsp:
            #return (rsp, msg)
            return

        self._schema_id     = rsp['schema_id']
        self._schema        = rsp['schema']
        self._sub_hash      = rsp['sub_hash']
        #return (rsp.securities, msg)

    def subscribe(self, symbol, func=None, fields="", data_format=""):
        """Subscribe securites
        
        This function adds new securities to subscribed list on the server. If
        success, return subscribed codes.
        
        If securities is empty, return current subscribed codes.
        """
        r, msg = self._check_session()
        if not r:
            return (r, msg)

        if func:
            self._on_jsq_callback = func
        
        rpc_params = {"symbol" : symbol,
                      "fields"   : fields }

        cr = self._remote.call("jsq.subscribe", rpc_params)
        
        rsp, msg = utils.extract_result(cr, data_format="", class_name="SubRsp")
        if not rsp:
            return (rsp, msg)

        new_codes = [ x.strip() for x in symbol.split(',') if x ]
        
        self._subscribed_set = self._subscribed_set.union( set(new_codes) )
        self._schema_id     = rsp['schema_id']
        self._schema        = rsp['schema']
        self._sub_hash      = rsp['sub_hash']
        return (rsp['securities'], msg)
        

    def unsubscribe(self, symbol):
        """Unsubscribe securities.

        Unscribe codes and return list of subscribed code.
        """
        assert False, "NOT IMPLEMENTED"


    def bar(self, symbol, start_time=200000, end_time=160000,
        trade_date=0, cycle="1m", fields="", data_format="", **kwargs ) :
        
        begin_time = utils.to_time_int(start_time)
        if(begin_time == -1):
            return(-1, "Begin time format error")
        end_time   = utils.to_time_int(end_time)
        if(end_time == -1):
            return(-1, "End time format error")
        trade_date = utils.to_date_int(trade_date)
        if(trade_date == -1):
            return(-1, "Trade date format error")

        return self._call_rpc("jsi.query",
                              self._get_format(data_format, "pandas"),
                              "Bar",
                              symbol   = str(symbol),
                              fields     = fields,
                              cycle      = cycle,
                              trade_date = trade_date,
                              begin_time = begin_time,
                              end_time   = end_time,
                              **kwargs)

    def bar_view(self, symbol, start_time=200000, end_time=160000,
        trade_date=0, cycle="1m", fields="", data_format="", **kwargs ) :

        begin_time = utils.to_time_int(start_time)
        if(begin_time == -1):
            return(-1, "Begin time format error")
        end_time   = utils.to_time_int(end_time)
        if(end_time == -1):
            return(-1, "End time format error")
        trade_date = utils.to_date_int(trade_date)
        if(trade_date == -1):
            return(-1, "Trade date format error")

        return self._call_rpc("jsi.bar_view",
                              self._get_format(data_format, "pandas"),
                              "Bar",
                              symbol   = str(symbol),
                              fields     = fields,
                              cycle      = cycle,
                              trade_date = trade_date,
                              begin_time = begin_time,
                              end_time   = end_time,
                              **kwargs)    


    def daily(self, symbol, start_date, end_date,
        adjust_mode = None, fields="",
        data_format="", **kwargs ) :

        if adjust_mode == None:
            adjust_mode = "none"

        begin_date = utils.to_date_int(start_date)
        if(begin_date == -1):
            return(-1, "Begin date format error")
        end_date   = utils.to_date_int(end_date)
        if(end_date == -1):
            return(-1, "End date format error")

        return self._call_rpc("jsd.query",
                              self._get_format(data_format, "pandas"),
                              "Daily",
                              symbol       = str(symbol),
                              fields         = fields,
                              begin_date     = begin_date,
                              end_date       = end_date,
                              adjust_mode    = adjust_mode,                             
                              **kwargs)

    def query(self, view, filter="", fields="", data_format="", **kwargs ) :
        return self._call_rpc( "jset.query",
                               self._get_format(data_format, "pandas"),
                               "JSetData",
                               view   = view,
                               fields = fields,
                               filter = filter,
                               **kwargs)

    def set_heartbeat(self, interval, timeout):
        self._remote.set_hearbeat_options(interval, timeout)

    def set_timeout(self, timeout):
        self._timeout = timeout
