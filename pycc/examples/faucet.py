
from pycc import *
from pycctx import *
import json
import pdb

######################
# FIXME this whole chunk is not neccesary if rust app or komodod 
# can provide a function to take pubkey and eval code as input and output corresponding CC addr
import hashlib
import binascii
import base58
def hash160(hexstr):
    preshabin = binascii.unhexlify(hexstr)
    my160 = hashlib.sha256(preshabin).hexdigest()
    return(hashlib.new('ripemd160', binascii.unhexlify(my160)).hexdigest())

def addr_from_ripemd(prefix, ripemd):
    net_byte = prefix + ripemd
    bina = binascii.unhexlify(net_byte)
    sha256a = hashlib.sha256(bina).hexdigest()
    binb = binascii.unhexlify(sha256a)
    sha256b = hashlib.sha256(binb).hexdigest()
    hmmmm = binascii.unhexlify(net_byte + sha256b[:8])
    final = base58.b58encode(hmmmm)
    return(final.decode())

def CCaddr_from_script(script_hexstr):
    ripemd = hash160(script_hexstr)
    addr = addr_from_ripemd('3c', ripemd)
    return addr


def CCaddr_dummy(pubkey, eval_code):
    cond = cc_threshold(2,[mk_cc_eval(eval_code),cc_threshold(1,[cc_secp256k1(pubkey)])])
    spk = cond.encode_condition().hex()
    spk = hex(int(len(spk)/2))[2:] + spk + 'cc'
    return CCaddr_from_script(spk) 
######################


def rpc_wrap(chain, method, params):
    return(json.loads(chain.rpc(json.dumps({"method": method, "params": params, "id":"pyrpc"}))))


# FIXME handle multiple inputs; just a PoC for now 
def find_unspent(chain, addresses, minimum):
    unspent = rpc_wrap(chain, 'listunspent', [1,9999999,addresses])
    for i in unspent:
        am = int(i['amount'] * 100000000+0.000000004999)
        if am >= minimum:
            return i, am
    # BaseException can be raised to send error msg back to komodod
    raise BaseException("find_unspent: No suitable utxo found") 


def load_tx(chain, txid):
    tx_hex = rpc_wrap(chain, 'getrawtransaction', [txid])
    return(Tx.decode(tx_hex))


def rpc_error(msg):
    return(json.dumps({"error": str(msg)}))


def rpc_success(msg):
    return(json.dumps({"success": str(msg)}))


global_addr = {
  "wif": "UuCGjHJ5pQNjLH3qhEibx7eACnHsBRpQpvJwjz9QkiAPsG84pHw6",
  "addr": "RB7qkc7UehLdfvk3Y2BMgxjMYTmYFrvLsH",
  "pubkey": "0328f24468cf695ccb14d819ab21c356b7193db4d597f59b3d1424068a1fc12775"
}

DRIP_AMOUNT = 1000000

schema_link = SpendBy("faucet.drip", pubkey=global_addr['pubkey'])

schema = {
    "faucet": {
        "create": {
            "inputs": [
                Input(P2PKH())
            ],
            "outputs": [
                Output(schema_link), # CC global vout 
                Output(P2PKH()) # normal change vout; input - create_amount - txfee
            ],
        },
        "drip": {
            "inputs": [
                Input(schema_link) # faucet create or drip utxo from global
            ],
            "outputs": [
                Output(schema_link, RelativeAmount(0) - DRIP_AMOUNT - 10000), # input amount - drip - txfee
                Output(P2PKH(), ExactAmount(DRIP_AMOUNT)) # drip amount to any normal address
            ]
        },
    }
}



def cc_eval(chain, tx_bin, nIn, eval_code):
    return CCApp(schema, eval_code, chain).cc_eval(tx_bin)


def cc_cli(chain, code):
    print('CODE', code)
    try:
        code = json.loads(code) # FIXME PyccRunGlobalCCRpc in pycc.cpp needs to be fixed to allow sending objects to this, not just strings
        app = CCApp(schema, b'_', chain)
        if code[0] == 'drip':
            CC_addr = CCaddr_dummy(global_addr['pubkey'], app.eval_code)


            # FIXME generalize utxo selection, both CC and normal 
            CC_utxos = rpc_wrap(chain, 'getaddressutxos', [{"addresses":[CC_addr]}, 1] )
            utxo = None 
            for i in CC_utxos:
                if i['satoshis'] > 100000 + 10000:
                    utxo = i
            if not utxo:
                raise BaseException("faucetdrip: no suitable utxo found")

            vin_tx = load_tx(chain, utxo['txid'])
            wifs = (global_addr['wif'],)

            myaddr = rpc_wrap(chain, 'setpubkey', [])['address']

            drip_tx = app.create_tx({
                "name": "faucet.drip",
                "inputs": [
                    { "previous_output": (utxo['txid'], utxo['outputIndex'])}
                ],
                "outputs": [
                    { }, # CC change to global
                    { "script": {"address": myaddr}} # faucet drip to arbitary address
                ]
            })
            drip_tx.version = 1 # FIXME if sapling 
            drip_tx.sign(wifs, [vin_tx])
            tx_bin = drip_tx.encode_bin()
            return rpc_success(drip_tx.encode())

        elif code[0] == 'test':
            return json.dumps({"success": "faucetdrip"})
        elif code[0] == 'create':
            if len(code) < 2:
                raise BaseException("create: argument 2 should be amount in sats")
            try:
                create_amount = int(code[1])
            except:
                raise BaseException("create: argument 2 should be amount in sats")

            myaddr = rpc_wrap(chain, 'setpubkey', [])['address']
            utxo, in_amount = find_unspent(chain, [myaddr], create_amount+10000)
            create_tx = app.create_tx({
                "name": "faucet.create",
                "inputs": [
                    { "previous_output": (utxo['txid'], utxo['vout']), "script": { "address": myaddr } }
                ],
                "outputs": [
                    { "amount": create_amount },
                    { "script": {"address": myaddr}, "amount": in_amount - create_amount}
                ]
            })
            create_tx.version = 1 # FIXME if sapling
            vin_tx = load_tx(chain, utxo['txid'])
            mywif = rpc_wrap(chain, 'dumpprivkey', [myaddr])
            create_tx.sign((mywif,), [vin_tx])
            return rpc_success(create_tx.encode())
        else:
            return rpc_error("method does not exist")

    except BaseException as e:
        #pdb.set_trace()
        return rpc_error(e)
    except Exception as e:
        #pdb.set_trace()
        return rpc_error(e)