
from pycc.lib import *
from pycctx import Tx
from copy import deepcopy


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
        txv = TxValidator(tx, self.schema)
        ctx = EvalContext(txv, self.eval_code, self.schema, self.chain, txv.stack)
        return txv.validate(ctx)

    # Create a TX
    # Go Condensed -> TX
    def create_tx(self, name, spec):
        parts = name.split('.')
        model = self.schema[parts[0]][parts[1]]
        tx = TxConstructor(model, spec)
        ctx = EvalContext(tx, self.eval_code, self.schema, self.chain, [])

        def f(l):
            out = []
            groups = []
            assert len(spec[l]) == len(model[l]), ("number of %s groups differs" % l)
            for (spec_i, model_i) in zip(spec[l], model[l]):
                r = model_i.construct(ctx, spec_i)
                n = len(r)
                assert n <= 256, ("%s group too large (256 max)" % l)
                groups.append(n)
                out.extend(r)
            return (groups, out)


        (input_groups, inputs) = f('inputs')
        (output_groups, outputs) = f('outputs')

        outputs += [TxOut.op_return(encode_params([name, (input_groups, output_groups)] + ctx.stack))]

        return Tx(
            inputs = tuple(inputs),
            outputs = tuple(outputs)
        )


class TxConstructor:
    def __init__(self, model, spec):
        self.model = model
        self.spec = deepcopy(spec)

    @property
    def inputs(self):
        return tuple(i if type(i) == list else [i] for i in self.spec['inputs'])


class TxValidator:
    def __init__(self, tx, schema):
        self.tx = tx
        self.schema = schema

        self.stack = decode_params(get_opret(tx))
        self.model = get_model(schema, self.stack.pop(0))
        (self.input_groups, self.output_groups) = self.stack.pop(0)

    def validate(self, ctx):
        spec = {"txid": self.tx.hash, "inputs":[], "outputs":[]}

        def f(groups, l, nodes):
            assert len(groups) == len(self.model[l])
            assert sum(groups) == len(nodes)
            for (n, m) in zip(groups, self.model[l]):
                spec[l].append(m.consume(ctx, nodes[:n]))
                nodes = nodes[n:]

        f(self.input_groups, 'inputs', self.tx.inputs)
        f(self.output_groups, 'outputs', self.tx.outputs[:-1])

        if 'validate' in self.model:
            self.model['validate'](ctx, spec)

        return spec

    def get_input_group(self, idx):
        groups = self.input_groups
        assert idx < len(groups), "TODO better message"
        skip = sum(groups[:idx])
        return self.tx.inputs[skip:][:groups[idx]]

