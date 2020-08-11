
from pycc import *
from pycctx import *
import json
#import pdb
import traceback

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


def addr_from_script(script_hexstr):
    ripemd = hash160(script_hexstr)
    addr = addr_from_ripemd('3c', ripemd)
    return addr


def CCaddr_normal(pubkey, eval_code):
    cond = cc_threshold(2, [mk_cc_eval(eval_code), cc_threshold(1, [cc_secp256k1(pubkey)])])
    spk = cond.encode_condition().hex()
    spk = hex(int(len(spk)/2))[2:] + spk + 'cc'
    return addr_from_script(spk)
######################


######################
# FIXME will move this elsewhere if it's determined this
# is a viable method for handling global keys
# import hashlib
# import binascii
# import base58
import ecdsa


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


def WIF_compressed(byte, raw_privkey):
    extended_key = byte+raw_privkey+'01'
    first_sha256 = hashlib.sha256(binascii.unhexlify(extended_key[:68])).hexdigest()
    second_sha256 = hashlib.sha256(binascii.unhexlify(first_sha256)).hexdigest()
    # add checksum to end of extended key
    final_key = extended_key[:68]+second_sha256[:8]
    # Wallet Import Format = base 58 encoded final_key
    WIF = base58.b58encode(binascii.unhexlify(final_key))
    return(WIF.decode("utf-8"))


# this will take an arbitary string and output a unique keypair+address
# intended to be used for global addresses with publicly known private keys
def string_keypair(key_string):
    privkey = hashlib.sha256(key_string.encode('utf-8')).hexdigest()
    sk = ecdsa.SigningKey.from_string(binascii.unhexlify(privkey), curve=ecdsa.SECP256k1)
    vk = sk.verifying_key
    pk = vk.to_string("compressed").hex()
    addr = addr_from_ripemd('3c', hash160(pk))
    wif = WIF_compressed('bc', privkey)
    return({"wif": wif, "addr": addr, "pubkey": pk})
######################


######################
# I intend to move all of these to lib.py if CC devs agree these are useful
def rpc_wrap(chain, method, *params):
    return(json.loads(chain.rpc(json.dumps({"method": method, "params": list(params), "id": "pyrpc"}))))


def find_input(chain, addresses, amount, CCflag=False):
    if CCflag:
        unspent = rpc_wrap(chain, 'getaddressutxos', {"addresses": addresses}, 1)
    else:
        unspent = rpc_wrap(chain, 'getaddressutxos', {"addresses": addresses})
    for i in unspent:
        # FIXME this is a hacky way to disclude p2pk utxos;
        # will remove this when pycc issue#11 is addressed
        if i['script'].startswith('76') or CCflag:
            if i['satoshis'] >= amount:
                vin_tx = load_tx(chain, i['txid'])
                vin = {"previous_output": (i['txid'], i['outputIndex']),
                       "script": {"address": i['address']},
                       "amount": i['satoshis']}
                return vin, vin_tx, i['satoshis']
    raise IntendExcept("find_input: No suitable utxo found")


# this is likely a good candidate for a cpp method in pycc.ccp as it
# could be resource intensive depending on getaddressutxos output
def find_inputs(chain, addresses, minimum, CCflag=False):
    vins = []
    total = 0
    if CCflag:
        unspent = rpc_wrap(chain, 'getaddressutxos', {"addresses": addresses}, 1)
    else:
        unspent = rpc_wrap(chain, 'getaddressutxos', {"addresses": addresses})
    for i in unspent:
        # FIXME this is a hacky way to disclude p2pk utxos;
        # will remove this when pycc issue#11 is addressed
        if i['script'].startswith('76') or CCflag:
            am = i['satoshis']
            total += am
            vins.append({"previous_output": (i['txid'], i['outputIndex']),
                         "script": {"address": i['address']},
                         "amount": i['satoshis']})
            if total >= minimum:
                return vins, total
    raise IntendExcept("find_inputs: No suitable utxo set found")


def load_txes(chain, txids):
    txes = []
    for txid in txid:
            tx = rpc_wrap(chain, 'getrawtransaction', txid)
            txes.append(Tx.decode(tx))
    return(txes)


def load_tx(chain, txid):
    tx_hex = rpc_wrap(chain, 'getrawtransaction', txid)
    return(Tx.decode(tx_hex))


def rpc_error(msg):
    # this will make komodo-cli output a bit prettier for unexpected(non-IntendExcept) exceptions
    msg = str(msg).split('\n')
    return(json.dumps({"error": msg}))


def rpc_success(msg):
    return(json.dumps({"success": str(msg)}))
######################


schema_link = SpendBy("faucet.drip")

schema = {
    "faucet": {
        "create": {
            "inputs": [
                Inputs(P2PKH())
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
                Output(schema_link, RelativeAmountUserArg(0) - 10000), # input amount - drip - txfee
                Output(P2PKH(), ExactAmountUserArg(0)) # drip amount to any normal address
            ],
            "validators": [
                TxPoW(0), # 0 value for TxPow is saying read vin0's OP_RETURN params to find how many leading/trailing 0s this drip must have
                CarryParams(0, ['TxPoW', 'AmountUserArg'])
            ]
        },
    }
}

# TODO 
# once mixed mode is ready, make it to where faucet.create cannot be done to an address that already has a faucet on it 
# possibly a "faucet.add" 
# maybe a "canspendfrommempool" flag 
# min confirmations flag
# let creator claim back faucet amount
# mesh tokens pycc with faucet
# mempool flag for find_input(s) - probably best to have cpp method in pycc.cpp




def cc_eval(chain, tx_bin, nIn, eval_code):
    return CCApp(schema, eval_code, chain).cc_eval(tx_bin)


# FIXME set defaults to 'fail' so help message is returned to user if missing args, maybe a more elegant way of doing this
def faucet_create(app, create_amount='fail', drip_amount='fail', txpow=0, global_string='default'):
    try:
        create_amount = int(create_amount)
        drip_amount = int(drip_amount)
        txpow = int(txpow)
    except:
        return(help('faucet'))

    setpubkey = rpc_wrap(app.chain, 'setpubkey')
    myaddr = setpubkey['address']
    mypk = setpubkey['pubkey']
    global_pair = string_keypair(global_string)

    vins, vins_amount = find_inputs(app.chain, [myaddr], create_amount+10000)

    create_tx = app.create_tx_extra_data({
        "name": "faucet.create",
        "inputs": [vins],
        "outputs": [
            {"amount": create_amount, "script": {"pubkey": global_pair['pubkey']}},
            {"script": {"address": myaddr}, "amount": vins_amount - create_amount - 10000}
        ]
    }, {"TxPoW": txpow, "AmountUserArg": drip_amount})
    # create_tx.set_standard()
    # FIXME make a "issapling" method in pycc.cpp to be accessed as chain.issapling
    # from within TxConstructor
    create_tx.set_sapling()
    mywif = rpc_wrap(app.chain, 'dumpprivkey', myaddr)
    create_tx.sign((mywif,))
    return(rpc_success(create_tx.encode()))


def faucet_drip(app, global_string='default'):
    global_pair = string_keypair(global_string)
    CC_addr = CCaddr_normal(global_pair['pubkey'], app.eval_code)

    vin, vin_tx, vin_amount = find_input(app.chain, [CC_addr], 0, True)
    vin['script']['pubkey'] = global_pair['pubkey']

    vin_opret = decode_params(get_opret(vin_tx))
    drip_amount = vin_opret[2]['AmountUserArg']
    txpow = vin_opret[2]['TxPoW']

    wifs = (global_pair['wif'],)

    setpubkey = rpc_wrap(app.chain, 'setpubkey')
    myaddr = setpubkey['address']
    mypk = setpubkey['pubkey']

    drip_tx = app.create_tx_pow({
        "name": "faucet.drip",
        "inputs": [
            vin
        ],
        "outputs": [
            {"script": {"pubkey": global_pair['pubkey']}}, # CC change to global
            {"script": {"address": myaddr}} # faucet drip to arbitary address
        ]
    }, {"TxPoW": txpow, "AmountUserArg": drip_amount}, txpow, wifs, [], True)
    return rpc_success(drip_tx.encode())


def help(specific=None):
    help_str = {"faucet": {"drip": "pycli drip [global_string]",
                           "create": "pycli create amount_sats drip_amount [txpow] [global_string]"},
                "example": {"example": "example"}}
    if specific:
        return(json.dumps(help_str[specific]))
    else:
        return(json.dumps(help_str))


def cc_cli(chain, code):
    try:
        code = json.loads(code)
        if code[0] == 'faucet':
            app = CCApp(schema, b'ee', chain)
            if code[1] == 'drip':
                return faucet_drip(app, *code[2:])
            elif code[1] == 'create':
                return faucet_create(app, *code[2:])
            else:
                return help('faucet')
        if code[0] == 'test':
            app = CCApp(schema, b'ee', chain)
            pdb.set_trace()
        else:
            return help()
    # IntendExcept can be raised to send error msg back to komodod
    except IntendExcept as e:
        return rpc_error(e)
    except Exception as e:
        return rpc_error(traceback.format_exc())
