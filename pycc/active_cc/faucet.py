
from pycc import *
from pycctx import *
import json
#import pdb
import traceback

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


# FIXME set defaults to 'fail' so help message is returned to user if missing args, maybe a more elegant way of doing this
def create(app, create_amount='fail', drip_amount='fail', txpow=0, global_string='default'):
    try:
        create_amount = int(create_amount)
        drip_amount = int(drip_amount)
        txpow = int(txpow)
    except:
        return(rpc_error(info['help']['create']))

    myaddr = rpc_wrap(app.chain, 'setpubkey')['address']
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
    mywif = rpc_wrap(app.chain, 'dumpprivkey', myaddr)
    create_tx.sign((mywif,))
    return(rpc_success(create_tx.encode()))


def drip(app, global_string='default'):
    global_pair = string_keypair(global_string)
    CC_addr = CCaddr_normal(global_pair['pubkey'], app.eval_code)
    print('MY CC_ADDR', CC_addr)

    vin, vin_tx, vin_amount = find_input(app.chain, [CC_addr], 0, True)
    vin['script']['pubkey'] = global_pair['pubkey']

    vin_opret = decode_params(get_opret(vin_tx))
    drip_amount = vin_opret[2]['AmountUserArg']
    txpow = vin_opret[2]['TxPoW']

    wifs = (global_pair['wif'],)

    myaddr = rpc_wrap(app.chain, 'setpubkey')['address']

    drip_tx = app.create_tx_pow({
        "name": "faucet.drip",
        "inputs": [
            vin
        ],
        "outputs": [
            {"script": {"pubkey": global_pair['pubkey']}}, # CC change to global
            {"script": {"address": myaddr}} # faucet drip to arbitary address
        ]
    }, txpow, wifs, {"TxPoW": txpow, "AmountUserArg": drip_amount})
    return rpc_success(drip_tx.encode())
    #    def create_tx_pow(self, spec, txpow, wifs, data={}, vins=[]):

info = {"functions": {"drip": drip, "create": create},
        "eval": b'ee',
        "schema": schema, # FIXME this seems kind of stupid as we can assume schema dict will always exist, leaving it for now
        "help": {"drip": "pycli faucet drip [global_string]",
                 "create": "pycli faucet create amount_sats drip_amount [txpow] [global_string]"}}
