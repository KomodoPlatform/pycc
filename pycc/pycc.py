
import binascii
import io
import subprocess
import base64
import json
import copy
from collections import namedtuple


def call_hoek(method, data):
    args = ['hoek', method, json.dumps(data)]
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    r = p.wait()
    if r != 0:
        raise IOError("Hoek returned error with args: ", args)
    return p.stdout.read()


def decode_tx(tx_bin):
    return call_hoek("decodeTx", {
        "hex": binascii.hexlify(tx_bin)
    })


def encode_tx(tx_dict):
    return call_hoek('encodeTx', tx_dict)


def py_to_hex(data):
    return base64.b16encode(json.dumps(data, sort_keys=True))


def hex_encode(data):
    return base64.b16encode(data)

def hex_decode(data):
    return base64.b16decode(data)

def get_opret(output):
    assert output.get('amount') == 0
    assert 'op_return' in output['script']
    return hex_decode(output['script']['op_return'])

class CCApp:
    def __init__(self, schema):
        self.schema = schema

    def __call__(self, *args, **kwargs):
        try:
            self._cc_eval(*args, **kwargs)
        except AssertionError as e:
            return str(e)

    def _cc_eval(self, chain, tx_bin, nIn, eval_prefix):
        tx = decode_tx(tx_bin)
        tx_data = self.consume_tx(chain, tx_bin, n_in, eval_prefix)
        # TODO: business validators

    def consume_tx(self, chain, tx, n_in, eval_prefix):
        opret_data = get_opret(tx["outputs"].pop())
        opret = opret_data.decode().split('.')
        assert len(opret) == 2, ("Invalid opret data")

        module_name = opret[0]
        assert module_name in self.schema, ("unknown module: %s" % module_name)
        module = self.schema[module_name]

        node_name = opret[1]
        assert node_name in module, ("unknown node: %s" % node_name)
        node = module.get(node_name)

        ctx = EvalContext(eval_prefix, self.schema, chain)

        txdata = {"inputs":[], "outputs":[]}
        for vin in node['inputs']:
            txdata['inputs'].append(vin.consume_inputs(ctx, tx['inputs']))

        assert not tx['inputs'], "leftover inputs"

        for vout in node['outputs']:
            txdata['outputs'].append(vout.consume_outputs(ctx, tx['outputs']))

        assert not tx['outputs'], "leftover outputs"

        return txdata


class EvalContext(namedtuple("EvalContext", 'code,schema,chain')):
    pass


class P2PKH:
    def consume_inputs(self, ctx, inputs):
        inp = inputs.pop(0)
        return {"address": inp['script']['address']}

    def consume_outputs(self, ctx, script):
        raise NotImplementedError()


class OutputOpReturn(namedtuple("OutputOpReturn", 'data')):
    pass

class Condition(namedtuple("Condition", 'script')):
    pass

class CCEval(namedtuple("CCEval", 'name,idx')):
    """
    CCEdge is an output that encodes a validation that the spending
    transaction corresponds to a certain type of node.

    It needs to be able to write an eval code that
    will route back to a function. So it needs contextual information.
    """
    def consume_outputs(self, ctx, outputs):
        out = outputs.pop(0)
        assert out['script'] == {
            "condition": {
                "type": "eval-sha-256",
                "code": hex_encode(ctx.code).decode()
            }
        }

    def consume_input(self, ctx, script):
        assert script == {
            "type": "eval-sha-256",
            "code": ctx.code
        }

class Ref(namedtuple("Ref", "name,idx")):
    
    """
    CCEdge is an input that finds the corresponding input for the referenced output.
    
    It needs to look up an output by name. So it needs access to the schema.
    """
    def consume_input(self, ctx, script):

        path = self.name.split('.')
        assert len(path) == 2

        node = ctx.schema[path[0]][path[1]]
        return node['outputs'][self.output_idx].consume_input(ctx, script)


class OneOf(namedtuple("OneOf", 'inputs')):
    pass


class AnyAmount():
    def consume(self, ctx, amount):
        self.amount = amount





# def hex_to_py(data):
#     return json.loads(base64.b16decode(data))
# 
# 
# def get_tx_params(tx):
#     opret = tx['outputs'][0]['script']['op_return']
#     return hex_to_py(opret)
# 
# 
# class PyccApp:
#     def __init__(self):
#         self.contracts = {}
# 
#     def add_contract(prefix, contract):
#         self.contracts[prefix] = contract
# 
#     def __call__(self, chain, transaction, nIn, code):
#         pass
