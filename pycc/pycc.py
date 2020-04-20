
from pycc.lib import *
from pycctx import Tx


class CCApp:
    def __init__(self, schema, eval_code, chain):
        self.schema = schema
        self.eval_code = eval_code
        self.chain = chain

    def __call__(self, *args, **kwargs):
        return self.cc_eval(*args, **kwargs)

    def cc_eval(self, tx_bin):
        self.validate_tx(chain, Tx.decode_bin(tx_bin))

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
