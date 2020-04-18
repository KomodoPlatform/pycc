import binascii
import io
import json
import copy
from collections import namedtuple

from pycctx import *


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


class EvalContext(namedtuple("EvalContext", 'tx,eval_code,schema,params,chain,stack')):
    pass


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
        return [TxOut(p['amount'], self.script.construct_output(ctx, i, params))]


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

    def construct_input(self, ctx, i, params):
        addr = params['inputs'][i]['script']['address']
        return ScriptSig.from_address(addr)


class CCEval(namedtuple("CCEval", 'name,idx')):
    """
    CCEdge is an output that encodes a validation that the spending
    transaction corresponds to a certain type of model.

    It needs to be able to write an eval code that
    will route back to a function. So it needs contextual information.
    """
    def consume_output(self, ctx, i):
        pubkey = ctx.stack.pop()
        cond = cc_threshold(2, [cc_eval(ctx.eval_code), cc_secp256k1(pubkey)])
        assert ctx.tx.outputs[i].script.parse_condition().is_same_condition(cond)
        return {
            "pubkey": pubkey
        }

    def consume_input(self, ctx, script):
        assert script == {
            "fulfillment": {
                "type": "eval-sha-256",
                "code": hex_encode(ctx.code)
            }
        }

        assert ctx.params['tx'] == self.name

    def construct_output(self, ctx, i, params):
        pubkey = params['outputs'][i]['script']['pubkey']
        ctx.stack.append(pubkey)
        cond = cc_threshold(2, [cc_eval(ctx.eval_code), cc_secp256k1(pubkey)])
        return ScriptPubKey.from_condition(cond)


class Ref(namedtuple("Ref", "name,idx")):
    """
    CCEdge is an input that finds the corresponding input for the referenced output.
    
    It needs to look up an output by name. So it needs access to the schema.
    """
    def consume_input(self, ctx, script):

        path = self.name.split('.')
        assert len(path) == 2

        model = ctx.schema[path[0]][path[1]]
        return model['outputs'][self.idx].script.consume_input(ctx, script)


class AnyAmount():
    def consume(self, ctx, i):
        return ctx.tx.outputs[i].amount


class RelativeAmount:
    def __init__(self, input_idx, diff=0):
        self.input_idx = input_idx
        self.diff = 0

    def __sub__(self, n):
        return RelativeAmount(self.input_idx, self.diff - n)

    def consume(self, ctx, amount):

        # We have the input idx of the input *group*, not the input itself.
        # Since there's no easy way to get the inputs in the group from here,
        # add a post validator which gets the validation output and run it on that.

        def post_validator(spec):
            total = 0
            for inp in spec['inputs'][self.input_idx]:
                input_tx = ctx.chain.get_transaction(inp.previous_output[0])
                total += input_tx.outputs[inp.previous_output[1]]['amount']
            
            assert total + diff == amount

        ctx.add_post_validator(post_validator)
        return amount

