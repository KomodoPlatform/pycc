
from pycc.lib import *
from pycctx import Tx
import time


class CCApp:
    def __init__(self, schema, eval_code, chain):
        self.schema = schema
        self.eval_code = eval_code
        self.chain = chain

    def __call__(self, *args, **kwargs):
        return self.cc_eval(*args, **kwargs)

    def cc_eval(self, tx_bin):
        self.validate_tx(Tx.decode_bin(tx_bin))

    def get_model(self, name):
        try:
            (module_name, model_name) = name.split('.', 2)
            return self.schema[module_name][model_name]
        except:
            raise AssertionError("Invalid model: %s" % name)

    # Validate a TX
    # Go TX -> Condensed
    def validate_tx(self, tx):
        return TxValidator(self, tx).validate()

    # Create a TX
    # Go Condensed -> TX
    def create_tx(self, spec):
        return TxConstructor(self, spec).construct()

    def create_tx_extra_data(self, spec, data):
        return TxConstructor(self, spec, params=data).construct()

    # needed for TxPoW validated txes 
    def create_tx_pow(self, spec, data, txpow, wifs, vins):
        # start_time is just used as "entropy",
        # needs to change each time this function is called or 
        # can result in user never finding a solution
        # using time is suboptimal because if it fails, on retry it will use some of the same numbers again
        start_time = int(time.time())
        for i in range(0,100000):
            tx = TxConstructor(self, spec, params={**data, **{"txpown": start_time}}).construct()
            tx.sign(wifs, vins)
            if tx.hash.startswith('0'*txpow) and tx.hash.endswith('0'*txpow):
                return(tx)
            start_time += 1
        raise IntendExcept("txpow: solution not found after 100000 attempts, try again")