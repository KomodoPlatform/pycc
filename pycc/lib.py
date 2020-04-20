import binascii
import io
import json
import copy
from collections import namedtuple

from pycctx import *

# Hack because komodod expects cc_eval function and pycctx.script also exports it
mk_cc_eval = cc_eval
del globals()['cc_eval']



def py_to_hex(data):
    return hex_encode(json.dumps(data, sort_keys=True))

def hex_encode(data):
    if hasattr(data, 'encode'):
        data = data.encode()
    return binascii.hexlify(data).decode()

def hex_decode(data):
    return binascii.unhexlify(data)

def get_opret(tx):
    assert tx.outputs, "opret not present"
    opret = tx.outputs[-1]
    assert opret.amount == 0
    data = opret.script.get_opret_data()
    assert not data is None, "opret not present"
    return data

def get_model(schema, path):
    (module_name, model_name) = path.split('.', 2)

    assert module_name in schema, ("unknown module: %s" % module_name)
    module = schema[module_name]

    assert model_name in module, ("unknown tx: %s" % model_name)
    return module.get(model_name)



def encode_params(params):
    return repr(params).encode()

def decode_params(b):
    return eval(b)


class EvalContext:
    def __init__(self, tx, eval_code, schema, chain, stack):
        self.tx = tx
        self.eval_code = eval_code
        self.schema = schema
        self.chain = chain
        self.stack = stack
        self.post_validators = []

    def get_model(self, name):
        # TODO: control errors
        path = name.split('.')
        assert len(path) == 2
        return self.schema[path[0]][path[1]]

    def add_post_validator(self, f):
        self.post_validators.append(f)


class Output:
    def __init__(self, script, amount=None):
        self.script = script
        self.amount = amount or AnyAmount()

    def consume(self, ctx, outputs):
        assert len(outputs) == 1
        return self.consume_output(ctx, *outputs)

    def consume_output(self, ctx, output):
        return {
            "script": self.script.consume_output(ctx, output.script) or {},
            "amount": self.amount.consume(ctx, output.amount)
        }

    def construct(self, ctx, spec):
        return [TxOut(
            amount = self.amount.construct(ctx, spec.get('amount')),
            script = self.script.construct_output(ctx, spec.get('script'))
        )]


class Outputs:
    def __init__(self, script, amount=None, min=1):
        self.script = script
        self.amount = amount or AnyAmount()

    def consume(self, ctx, outputs):
        assert len(outputs) >= self.min
        o = Output(self.script, self.amount)
        return [o.consume_output(ctx, o) for o in outputs]

    def construct(self, ctx, i, spec):
        ps = spec['inputs'][i]
        n = len(ps)
        ctx.spec.push(n)
        assert n >= self.min
        return [TxOut(
            amount = self.amount.construct(ctx, i, spec),
            script = self.script.construct_output(ctx, i, spec)
        ) for p in ps]


class Input:
    def __init__(self, script):
        self.script = script

    def consume(self, ctx, inputs):
        assert len(inputs) == 1
        return self.consume_input(ctx, *inputs)

    def consume_input(self, ctx, inp):
        return {
            "previous_output": inp.previous_output,
            "script": self.script.consume_input(ctx, inp) or {}
        }

    def construct(self, ctx, spec):
        return [TxIn(spec['previous_output'], self.script.construct_input(ctx, spec.get('script')))]


class Inputs:
    def __init__(self, script, min=1):
        self.script = script
        self.min = min

    def consume(self, ctx, inputs):
        assert len(inputs) >= self.min
        inp = Input(self.script)
        return [inp.consume_input(ctx, i) for i in inputs]

    def construct(self, ctx, i, spec):
        ps = spec['inputs'][i]
        n = len(ps)
        ctx.params.push(n)
        assert n >= self.min
        return [TxIn(p['previous_output'], self.script.construct_input(ctx, i, spec))
                for p in spec['inputs'][i]]


class P2PKH:
    def consume_input(self, ctx, inp):
        return inp.script.parse_p2pkh()

    def consume_output(self, ctx, script):
        return script.parse_p2pkh()

    def construct_input(self, ctx, spec):
        return ScriptSig.from_address(spec['address'])

    def construct_output(self, ctx, spec):
        return ScriptPubKey.from_address(spec['address'])


class SpendBy:
    """
    SpendBy ensures that an output is spent by a given type of input

    SpendBy make either use a dynamic or fixed pubkey.
    If it's fixed (provided in constructor), it does not expect to find
    it in tx spec and does not provide it in validated spec.

    """
    def __init__(self, name, idx, pubkey=None):
        self.name = name
        self.output_idx = idx
        self.pubkey = pubkey

        # TODO: sanity check on structure? make sure that inputs and outputs are compatible
    
    def consume_output(self, ctx, script):
        # When checking the output there's nothing to check except the script
        return self._check_cond(ctx, script.parse_condition())

    def consume_input(self, ctx, inp):
        # Check input script
        r = self._check_cond(ctx, inp.script.parse_condition())

        # Check output of parent tx to make sure link is correct
        p = inp.previous_output

        # TODO: make this easier
        input_tx = ctx.chain.get_tx_confirmed(p[0])
        stack = decode_params(get_opret(input_tx))
        model = get_model(ctx.schema, self.name)
        assert model['outputs'][self.output_idx].script._eq(self)

        # Check that index of output being spent is part of target output group
        gs = ctx.tx.output_groups
        p = p[1] - sum(gs[:self.output_idx])
        assert p >= 0 and p < gs[self.output_idx], "TODO: Nice message"

        return r

    def construct_output(self, ctx, spec):
        return ScriptPubKey.from_condition(self._construct_cond(ctx, spec))

    def construct_input(self, ctx, spec):
        return ScriptSig.from_condition(self._construct_cond(ctx, spec))

    def _eq(self, other):
        # Should compare the pubkey here? maybe it's not neccesary
        return (self.name == other.name and
                self.output_idx == other.output_idx and
                self.pubkey == other.pubkey)

    def _check_cond(self, ctx, cond):
        pubkey = self.pubkey or self.stack.pop()
        c = cc_threshold(2, [mk_cc_eval(ctx.eval_code), cc_secp256k1(pubkey)])
        assert c.is_same_condition(cond)
        return {} if self.pubkey else { "pubkey": pubkey }

    def _construct_cond(self, ctx, node_spec):
        pubkey = self.pubkey
        script_spec = (node_spec or {}).get('script', {})
        if pubkey:
            assert not script_spec.get('pubkey'), "pubkey must not be in both spec and schema"
        else:
            pubkey = script_spec['pubkey']
            ctx.stack.append(pubkey)
        return cc_threshold(2, [mk_cc_eval(ctx.eval_code), cc_secp256k1(pubkey)])


class AnyAmount():
    def consume(self, ctx, amount):
        return amount

    def construct(self, ctx, amount):
        return amount


class ExactAmount:
    def __init__(self, amount):
        self.amount = amount
    
    def consume(self, ctx, amount):
        assert amount == self.amount

    def construct(self, ctx, amount):
        assert amount is None
        return self.amount


class RelativeAmount:
    def __init__(self, input_idx, diff=0):
        self.input_idx = input_idx
        self.diff = diff

    def __sub__(self, n):
        return RelativeAmount(self.input_idx, self.diff - n)

    def consume(self, ctx, amount):
        total = self.diff
        for inp in ctx.tx.get_input_group(self.input_idx):
            p = inp.previous_output
            input_tx = ctx.chain.get_tx_confirmed(p[0])
            total += input_tx.outputs[p[1]].amount

        assert total == amount, "TODO: nice error message"
        return amount

    def construct(self, ctx, spec):
        assert spec == None, "amount should not be provided for RelativeAmount"

        r = self.diff

        for inp in as_list(ctx.tx.inputs[self.input_idx]):
            p = inp['previous_output']
            input_tx = ctx.chain.get_tx_confirmed(p[0])
            r += input_tx.outputs[p[1]].amount

        assert r >= 0, "cannot construct RelativeInput: low balance"
        return r

def as_list(val):
    return val if type(val) == list else [val]
