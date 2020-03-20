
import binascii
import io
import subprocess
import base64
import json


def call_hoek(method, data):
    args = ['hoek', method, data]
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    r = p.wait()
    if r != 0:
        raise IOError("Hoek returned error with args: ", args)
    return p.stdout.read()


def decode_tx(tx_bin):
    return call_hoek("decodeTx", json.dumps({
        "hex": binascii.hexlify(tx_bin)
    }))


def encode_tx(tx_dict):
    return call_hoek('encodeTx', json.dumps(tx_dict))


def py_to_hex(data):
    return base64.b16encode(json.dumps(data, sort_keys=True))


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
