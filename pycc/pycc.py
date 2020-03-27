
import binascii
import io
import subprocess
import json
import copy
from collections import namedtuple


def call_hoek(method, data):
    args = ['hoek', method, json.dumps(data)]
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    r = p.wait()
    if r != 0:
        raise IOError("Hoek returned error with args: ", args)
    return json.loads(p.stdout.read())


def decode_tx(tx_hex):
    return call_hoek("decodeTx", {
        "hex": tx_hex
    })


def encode_tx(tx_dict):
    return call_hoek('encodeTx', tx_dict)

def sign_tx(tx_dict, privKeys):
    return call_hoek('signTx', {
        "tx": tx_dict,
        "privateKeys": privKeys
    })

def get_txid(tx_hex):
    return call_hoek('getTxid', {"hex": tx_hex})

def py_to_hex(data):
    return hex_encode(json.dumps(data, sort_keys=True))

def encode_condition(fulfillment):
    return call_hoek('encodeCondition', fulfillment)

def hex_encode(data):
    if hasattr(data, 'encode'):
        data = data.encode()
    return binascii.hexlify(data).decode()

def hex_decode(data):
    return binascii.unhexlify(data)

def hex2py(hex_data):
    return json.loads(hex_decode(hex_data))

def py2hex(data):
    return hex_encode(json.dumps(data))


def get_opret(output):
    assert output.get('amount') == 0
    assert 'op_return' in output['script']
    return hex2py(output['script']['op_return'])


def get_node_path(opret_data):
    assert 'tx' in opret_data
    path = opret_data['tx'].split('.')
    assert len(path) == 2
    return path


def get_node(schema, opret):
    (module_name, node_name) = get_node_path(opret)

    assert module_name in schema, ("unknown module: %s" % module_name)
    module = schema[module_name]

    assert node_name in module, ("unknown node: %s" % node_name)
    return module.get(node_name)


class CCApp:
    def __init__(self, schema):
        self.schema = schema

    def __call__(self, *args, **kwargs):
        return self.cc_eval(*args, **kwargs)

    def cc_eval(self, chain, tx_bin, n_in, eval_prefix):
        tx_hex = hex_encode(tx_bin)
        tx = decode_tx(tx_hex)
        txid = get_txid(tx_hex)
        params = get_opret(tx["outputs"].pop())
        ctx = EvalContext(eval_prefix, self.schema, params, chain)
        node = get_node(self.schema, params)
        txdata = {"txid": txid, "inputs":[], "outputs":[]}

        for vin in node['inputs']:
            txdata['inputs'].append(vin.consume_inputs(ctx, tx['inputs']))

        assert not tx['inputs'], "leftover inputs"

        for vout in node['outputs']:
            txdata['outputs'].append(vout.consume_outputs(ctx, tx['outputs']))

        assert not tx['outputs'], "leftover outputs"

        if 'validate' in node:
            node['validate'](ctx, txdata)

        return txdata

    def construct_tx(self, name, params):
        parts = name.split('.')
        tpl = self.schema[parts[0]][parts[1]]

        out = {
            "inputs": [],
            "outputs": []
        }

        for (inp, param) in zip(tpl['inputs'], params['inputs']):
            out['inputs'] += inp.construct(param)

        for (out, param) in zip(tpl['outputs'], params['inputs']):
            out['outputs'] += out.construct(param)

        return out



class EvalContext(namedtuple("EvalContext", 'code,schema,params,chain')):
    pass


class Output:
    def __init__(self, script, amount=None):
        self.script = script
        self.amount = amount or AnyAmount()

    def consume_outputs(self, ctx, outputs):
        output = outputs.pop(0)
        r = self.script.consume_output(ctx, output['script']) or {}
        r['amount'] = self.amount.consume(ctx, output['amount'])
        return r

class Input:
    def __init__(self, script):
        self.script = script

    def consume_inputs(self, ctx, inputs):
        inp = inputs.pop(0)
        r = self.script.consume_input(ctx, inp['script']) or {}
        r['txid'] = inp['txid']
        r['idx'] = inp['idx']
        return r


class P2PKH:
    def consume_input(self, ctx, script):
        return {"address": script['address']}

    def consume_output(self, ctx, script):
        return {"address": script['address']}


class InputAmount:
    def __init__(self, input_idx, transforms=None):
        self.input_idx = input_idx
        self.transforms = transforms or []

    def consume(self, ctx, amount):
        # TODO: look up input amount at idx, apply transforms, compare
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
    def consume_output(self, ctx, script):
        assert script == {
            "condition": encode_condition({
                "type": "eval-sha-256",
                "code": hex_encode(ctx.code)
            })
        }

    def consume_input(self, ctx, script):
        assert script == {
            "fulfillment": {
                "type": "eval-sha-256",
                "code": hex_encode(ctx.code)
            }
        }

        assert ctx.params['tx'] == self.name



class Ref(namedtuple("Ref", "name,idx")):
    
    """
    CCEdge is an input that finds the corresponding input for the referenced output.
    
    It needs to look up an output by name. So it needs access to the schema.
    """
    def consume_input(self, ctx, script):

        path = self.name.split('.')
        assert len(path) == 2

        node = ctx.schema[path[0]][path[1]]
        return node['outputs'][self.idx].script.consume_input(ctx, script)


class OneOf(namedtuple("OneOf", 'inputs')):
    pass


class AnyAmount():
    def consume(self, ctx, amount):
        return amount

