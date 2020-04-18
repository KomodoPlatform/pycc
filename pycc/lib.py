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

    def consume_outputs(self, ctx, nums):
        i = nums.pop(0)
        return {
            "script": self.script.consume_output(ctx, i) or {},
            "amount": self.amount.consume(ctx, i)
        }

    def construct(self, ctx, i, params):
        p = params['outputs'][i]
        return [TxOut(
            amount = self.amount.construct(ctx, i, params),
            script = self.script.construct_output(ctx, i, params)
        )]


class Input:
    def __init__(self, script):
        self.script = script

    def consume_inputs(self, ctx, nums):
        i = nums.pop(0)
        return {
            "previous_output": ctx.tx.inputs[i].previous_output,
            "script": self.script.consume_input(ctx, i) or {}
        }

    def construct(self, ctx, i, params):
        p = params['inputs'][i]
        return [TxIn(p['previous_output'], self.script.construct_input(ctx, i, params))]


class P2PKH:
    def consume_input(self, ctx, i):
        return ctx.tx.inputs[i].script.parse_p2pkh()

    def consume_output(self, ctx, i):
        return ctx.tx.outputs[i].script.parse_p2pkh()

    def construct_input(self, ctx, i, spec):
        addr = spec['inputs'][i]['script']['address']
        return ScriptSig.from_address(addr)

    def construct_output(self, ctx, i, spec):
        addr = spec['outputs'][i]['script']['address']
        return ScriptPubKey.from_address(addr)


class SpendBy:
    """
    SpendBy ensures that an output is spent by a given type of input

    SpendBy make either use a dynamic or fixed pubkey.
    If it's fixed (provided in constructor), it does not expect to find
    it in tx spec and does not provide it in validated spec.

    """
    def __init__(self, name, idx, pubkey=None):
        self.name = name
        self.idx = idx
        self.pubkey = pubkey
    
    def consume_output(self, ctx, i):
        return self._check_cond(ctx, ctx.tx.outputs[i].script.parse_condition())

    def consume_input(self, ctx, i):
        r = self._check_cond(ctx, ctx.tx.inputs[i].script.parse_condition())
        # Check output of parent tx to make sure link is correct
        # TODO: support groups
        for inp in (ctx.tx.inputs[i],):
            p = inp.previous_output
            # TODO: tx wrapper with model with methods like get_output_group etc
            input_tx = ctx.chain.get_tx_confirmed(p[0])
            stack = decode_params(get_opret(input_tx))
            model = get_model(ctx.schema, stack[0])
            assert model['outputs'][self.idx].script._eq(self)
        return r

    def construct_output(self, ctx, i, spec):
        return ScriptPubKey.from_condition(self._construct_cond(ctx, spec['outputs'][i]))

    def construct_input(self, ctx, i, spec):
        return ScriptSig.from_condition(self._construct_cond(ctx, spec['inputs'][i]))

    def _eq(self, other):
        # Should compare the pubkey here? maybe it's not neccesary
        return self.name == other.name and self.idx == other.idx and self.pubkey == other.pubkey

    def _check_cond(self, ctx, cond):
        pubkey = self.pubkey or self.stack.pop()
        c = cc_threshold(2, [mk_cc_eval(ctx.eval_code), cc_secp256k1(pubkey)])
        assert c.is_same_condition(cond)
        return {} if self.pubkey else { "pubkey": pubkey }

    def _construct_cond(self, ctx, script_spec):
        pubkey = self.pubkey
        if pubkey:
            assert not script_spec.get('pubkey'), "pubkey is provided"
        else:
            pubkey = script_spec['pubkey']
            ctx.stack.append(pubkey)
        return cc_threshold(2, [mk_cc_eval(ctx.eval_code), cc_secp256k1(pubkey)])


class AnyAmount():
    def consume(self, ctx, i):
        return ctx.tx.outputs[i].amount

    def construct(self, ctx, i, params):
        return params['outputs'][i]['amount']


class RelativeAmount:
    def __init__(self, input_idx, diff=0):
        self.input_idx = input_idx
        self.diff = diff

    def __sub__(self, n):
        return RelativeAmount(self.input_idx, self.diff - n)

    def consume(self, ctx, i):
        amount = ctx.tx.outputs[i].amount

        # We have the input idx of the input *group*, not the input itself.
        # Since there's no easy way to get the inputs in the group from here,
        # add a post validator which gets the validation output and run it on that.

        def post_validator(spec):
            # TODO: handle input groups
            total = 0
            for inp in (spec['inputs'][self.input_idx],):
                p = inp['previous_output']
                input_tx = ctx.chain.get_tx_confirmed(p[0])
                total += input_tx.outputs[p[1]].amount

            assert total + self.diff == amount

        ctx.add_post_validator(post_validator)
        return amount

    def construct(self, ctx, i, spec):
        # TODO: handle input groups
        r = self.diff
        for inp in (spec['inputs'][self.input_idx],):
            p = inp['previous_output']
            input_tx = ctx.chain.get_tx_confirmed(p[0])
            r += input_tx.outputs[p[1]].amount

        assert r >= 0, "cannot construct RelativeInput: low balance"

        return r




