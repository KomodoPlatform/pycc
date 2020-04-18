

from pycctx import Tx
from pycc.lib import *


class CCApp:
    def __init__(self, schema, eval_code, chain):
        self.schema = schema
        self.eval_code = eval_code
        self.chain = chain

    def __call__(self, *args, **kwargs):
        return self.cc_eval(*args, **kwargs)

    def cc_eval(self, tx_bin):
        return validate_tx(chain, Tx.decode_bin(tx_bin))

    # Validate a TX
    # Go TX -> Condensed
    def validate_tx(self, tx):
        stack = decode_params(get_opret(tx))
        model = get_model(self.schema, stack.pop(0))
        ctx = EvalContext(tx, self.eval_code, self.schema, self.chain, stack)
        spec = {"txid": tx.hash, "inputs":[], "outputs":[]}

        input_nums = list(range(len(tx.inputs)))
        for vin in model['inputs']:
            spec['inputs'].append(vin.consume_inputs(ctx, input_nums))
        assert not input_nums, "leftover inputs"

        output_nums = list(range(len(tx.outputs) - 1))
        for vout in model['outputs']:
            spec['outputs'].append(vout.consume_outputs(ctx, output_nums))
        assert not output_nums, "leftover outputs"

        for pv in ctx.post_validators:
            pv(spec)

        if 'validate' in model:
            model['validate'](ctx, spec)

        return spec

    # Create a TX
    # Go Condensed -> TX
    def create_tx(self, name, params):
        parts = name.split('.')
        tpl = self.schema[parts[0]][parts[1]]
        ctx = EvalContext(None, self.eval_code, self.schema, self.chain, [])

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

