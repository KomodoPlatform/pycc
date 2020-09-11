from pycc import *
from pycctx import *

schema = {
    "faucet": {
        "create": {
            "inputs": [
                Inputs(P2PKH())
            ],
            "outputs": [
                Output(SpendBy("faucet.get")), # CC global vout
                Output(P2PKH()) # normal change vout; input - create_amount - txfee
            ],
        },
        "get": {
            "inputs": [
                Input(SpendBy("faucet.get"))
            ],
            "outputs":[
                Output(SpendBy("faucet.get"), RelativeAmount(0) - 100000000 - 10000),
                Output(P2PKH(), ExactAmount(100000000))]
        },
    }
}

def faucetcreate(app, faucet_amount):
    global_pair = string_keypair("satinder's faucet")

    faucet_amount = int(faucet_amount)

    myaddr = rpc_wrap(app.chain, 'setpubkey')['address']
    mywif = rpc_wrap(app.chain, 'dumpprivkey', myaddr)

    vins, vins_total = find_inputs(app.chain, [myaddr], faucet_amount)

    if not vins:
        return(rpc_error("No inputs found"))

    create_tx = app.create_tx({
        "name": "faucet.create",
        "inputs": [vins],
        "outputs": [
            {"amount": faucet_amount, "script": {"pubkey": global_pair['pubkey']}},
            {"script": {"address": myaddr}, "amount": vins_total - faucet_amount - 10000}
        ]
    })

    create_tx.sign([mywif])

    return(rpc_success(create_tx.encode()))

def faucetget(app):
    global_pair = string_keypair("satinder's faucet")

    CC_addr = CCaddr_normal(global_pair['pubkey'], info['eval'])

    myaddr = rpc_wrap(app.chain, 'setpubkey')['address']
    vin, vin_tx, vin_amount = find_input(app.chain, [CC_addr], 100000000, True)
    vin['script']['pubkey'] = global_pair['pubkey']

    get_tx = app.create_tx({
        "name": "faucet.get",
        "inputs": [vin],
        "outputs": [
            {"script": {"pubkey": global_pair['pubkey']}},
            {"script": {"address": myaddr}}
        ]
    })

    get_tx.sign([global_pair['wif']])

    return(rpc_success(get_tx.encode()))


info = {"functions": {"faucet_create": faucetcreate, "give_me_money": faucetget},
        "eval": b'f',
        "schema": schema, # FIXME this seems kind of stupid as we can assume schema dict will always exist, leaving it for now
        "help": {"faucet_create": "pycli faucet_create faucet_amount"}}