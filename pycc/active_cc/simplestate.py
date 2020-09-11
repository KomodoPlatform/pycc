
from pycc import *
from pycctx import *
import json
#import pdb
import traceback

valid_events = ['on', 'off']

schema = {
    "state": {
        "fund": {
            "inputs": [
                Inputs(P2PKH())
            ],
            "outputs": [
                Output(SpendBy("state.fund")), # CC global vout
                Output(P2PKH()) # normal change vout; input - create_amount - txfee
            ],
        },
        "toggle": {
            "inputs": [
                Inputs(SpendBy("state.fund"))
            ],
            "outputs": [
                Output(P2PKH()) # normal change vout; input - create_amount - txfee
            ],
            "validators": [
                ValidEvents(valid_events)
            ]
        }
    }
}

transitions = ( ('on', ['on'], 'on'),
                ('on', ['off'], 'off'),
                ('off', ['on'], 'on'),
                ('off', ['off'], 'off'), 
            )
init_state = 'off'


def fund(app, global_string='default'):
    myaddr = rpc_wrap(app.chain, 'setpubkey')['address']
    global_pair = string_keypair(global_string)
    print('glob', global_pair['addr'])


    vins, vins_amount = find_inputs(app.chain, [myaddr], 100000000)

    fund_tx = app.create_tx_extra_data({
        "name": "state.fund",
        "inputs": [vins],
        "outputs": [
            {"amount": 10000000, "script": {"pubkey": global_pair['pubkey']}},
            {"script": {"address": myaddr}, "amount": vins_amount - 10000000 - 10000}
        ]
    }, {})
    mywif = rpc_wrap(app.chain, 'dumpprivkey', myaddr)
    fund_tx.sign((mywif,))
    return(rpc_success(fund_tx.encode()))

def my_events(prevblock, events):
    if ( (prevblock['height']+1) % 10 == 0):
        print("SPECIAL EVENT OFF")
        events.append('off')
        return(events)
    if ( (prevblock['height']+1) % 5 == 0):
        print("SPECIAL EVENT ON")
        events.append('on')
        return(events)
    return(events)


def spend(app, global_string='default', new_state='on'):
    global_pair = string_keypair(global_string)
    CC_addr = CCaddr_normal(global_pair['pubkey'], app.eval_code)


    last_state = miner_end_state(app, -1, info['name'])
    print(last_state)
    if last_state[info['name']] == 'on':
        new_state = 'off'

    vins, vin_amount = find_inputs(app.chain, [CC_addr], 1, True)
    for vin in vins:
        vin['script']['pubkey'] = global_pair['pubkey']


    wifs = (global_pair['wif'],)
    myaddr = rpc_wrap(app.chain, 'setpubkey')['address']

    spend_tx = app.create_tx_extra_data({
        "name": "state.toggle",
        "inputs": [vins],
        "outputs": [
            {"script": {"address": myaddr}, "amount": vin_amount - 10000} # faucet drip to arbitary address
        ]
    }, {info['name']: new_state})
    spend_tx.sign(wifs)
    return rpc_success(spend_tx.encode())

info = {"name": "stupidstate1",
        "special_events": my_events,
        "functions": {"fund": fund,
                      "spend": spend},
        "FSM": transitions,
        "FSM_init": init_state,
        "eval": b'ee',
        "schema": schema, # FIXME this seems kind of stupid as we can assume schema dict will always exist, leaving it for now
        "help": {"fund": "pycli state fund [on/off]",
                 "spend": "pycli state spend [on/off]"}
        }
