

from pycctx import *
from pycc.lib import *


class CCApp:
    def __init__(self, schema, eval_code):
        self.schema = schema
        self.eval_code = eval_code

    def __call__(self, *args, **kwargs):
        return self.cc_eval(*args, **kwargs)

    def cc_eval(self, chain, tx_bin):
        return validate_tx(chain, Tx.decode_bin(tx_bin))

    # Validate a TX
    # Go TX -> Condensed
    def validate_tx(self, chain, tx):
        stack = decode_params(get_opret(tx))
        model = get_model(self.schema, stack.pop(0))
        ctx = EvalContext(tx, self.eval_code, self.schema, {}, chain, stack)
        txdata = {"txid": tx.hash, "inputs":[], "outputs":[]}

        input_nums = list(range(len(tx.inputs)))
        for vin in model['inputs']:
            txdata['inputs'].append(vin.consume_inputs(ctx, input_nums))
        assert not input_nums, "leftover inputs"

        output_nums = list(range(len(tx.outputs) - 1))
        for vout in model['outputs']:
            txdata['outputs'].append(vout.consume_outputs(ctx, output_nums))
        assert not output_nums, "leftover outputs"

        if 'validate' in model:
            model['validate'](ctx, txdata)

        return txdata

    # Create a TX
    # Go Condensed -> TX
    def create_tx(self, name, chain, params):
        parts = name.split('.')
        tpl = self.schema[parts[0]][parts[1]]
        ctx = EvalContext(None, self.eval_code, self.schema, {}, chain, [])

        inputs = []
        outputs = []

        assert len(params['inputs']) == len(tpl['inputs'])
        for (i, inp) in enumerate(tpl['inputs']):
            inputs += inp.construct(ctx, i, params)

        assert len(params['outputs']) == len(tpl['outputs'])
        for (i, output) in enumerate(tpl['outputs']):
            outputs += output.construct(ctx, i, params)

        outputs += [TxOut.op_return(encode_params([name] + ctx.stack))]

        return Tx(
            inputs = tuple(inputs),
            outputs = tuple(outputs)
        )

