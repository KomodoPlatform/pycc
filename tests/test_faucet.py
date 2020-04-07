
from pycc.examples import faucet
from pycc import *
from pycctx import *

# app = CCApp(faucet.schema)
# 
# keypair = {
#     "wif": "UuKZRxAR4KYVSVKxgL8oKuyBku7bVhqbGk9onuaEzkXdaxgytpLB",
#     "addr": "RWqrNbM3gUr4A9kX9sMXTRyRbviLsSbjAs",
#     "pubKey": "038c3d482cd29f75ce997737705fb5287f022ded66093ee7d929aea100c5ef8a63"
# }
# 
# txid_1 = "d21633ba23f70118185227be58a63527675641ad37967e2aa461559f577aec43"
# 
# eval_code_bin = b'_'
# 
# create_tx = Tx(
#     inputs = [
#         TxIn((txid_1, 0), ScriptSig.from_address(keypair['addr']))
#     ],
#     outputs = [
#         TxOut(1000000, ScriptPubKey.from_condition(cc_eval(eval_code_bin))),
#         TxOut.op_return(repr({"tx": "faucet.create"}).encode())
#     ]
# )
# create_tx.sign([keypair['wif']])
# 
# 
# drip_tx
# drip_tx = {
#     "inputs": [
#         {
#             "txid": txid_1,
#             "idx":0,
#             "script": {
#                 "fulfillment": {
#                     "type": "eval-sha-256",
#                     "code": eval_code_hex
#                 }
#             }
#         }
#     ],
#     "outputs": [
#         {
#             "amount": 999000,
#             "script": {
#                 "condition": {
#                     "type": "eval-sha-256",
#                     "code": eval_code_hex
#                 }
#             }
#         },
#         {
#             "amount": 1000,
#             "script": {
#                 "address": keypair['addr']
#             }
#         },
#         {
#             "amount": 0,
#             "script": {
#                 "op_return": py2hex({"tx": "faucet.drip"})
#             }
#         }
#     ]
# }
# 
# 
# def test_validate_create():
#     o = app.cc_eval({}, create_tx.encode_bin(), 0, b"_")
#     assert o == {
#         "inputs": [{"address": keypair['addr'], "txid": txid_1, "idx": 0}],
#         "outputs": [{"amount": 1000000}],
#         "txid": create_tx.hash
#     }
# 
# 
# def test_validate_drip():
#     o = app.cc_eval({}, drip_tx.encode_bin(), 0, b'_')
#     assert o == {
#         "inputs": [{"idx": 0, "txid": txid_1}],
#         "outputs": [{"amount": 999000}, {"amount": 1000, "address": keypair['addr']}],
#         "txid": drip_tx.hash
#     }
# 
