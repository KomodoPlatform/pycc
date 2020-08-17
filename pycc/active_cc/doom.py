import oblige
import os
import sys
from pycc import *
from pycctx import *
import json
import traceback
import zlib
import subprocess # RISSSSKKKKKYYYYYYYYYYY should compile prboom directly into daemon and be accesible via chain.prboom()

def rebuild_demo(rawtics):
    static_header = b'm\x02\x01\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00' # maybe this can differ by "plan"
    uncomp = zlib.decompress(rawtics)
    return(static_header + uncomp + b'\x80')


def prboom_val(seed, demo_path):
    current_path = os.path.dirname(os.path.realpath(__file__))
    prboom_bin = os.path.join(current_path, 'prboom-plus')
    wad_path = current_path + '/WADS/' + str(seed) + '/' + str(seed) + '.wad'

    args = [prboom_bin, '-iwad', 'DOOM.WAD', '-file', wad_path, '-timedemo', demo_path, '-nodraw', '-nosound']
    try:
        prboom_process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,universal_newlines=True)
        results = prboom_process.communicate()[0]
        exit_code = prboom_process.returncode

    except subprocess.CalledProcessError:
        raise Exception("prboom exited with error!"
                        "\nExit code: {}"
                        "\nLog:\n{}".format(exit_code, results))
    if results.split('\n')[-4] == 'FINISHED: E1M1': # FIXME make sure this is static, maybe better to search through last few params
        return(True)



class DoomDemo:
    def __init__(self, input_idx):
        self.input_idx = input_idx

    def __call__(self, tx, spec):
        txid_in = spec['inputs'][0]['previous_output'][self.input_idx]
        tx_in = Tx.decode_bin(tx.app.chain.get_tx_confirmed(txid_in))
        prev_params = decode_params(get_opret(tx_in))
        seed = prev_params[2]['seed'] 

        rawtics = decode_params(get_opret(tx.tx))[2]['rawtics']
        current_path = os.path.dirname(os.path.realpath(__file__))
        if not os.path.exists(current_path + '/temp_demos'):
            os.makedirs(current_path + '/temp_demos')
        full_demo = rebuild_demo(rawtics)
        temp_path = current_path + '/temp_demos/' + str(seed) + '.demo'
        with open(temp_path, "wb") as rebuilt:
            rebuilt.write(full_demo)

        validated = prboom_val(seed, temp_path)
        os.remove(temp_path)
        if not validated:
            raise IntendExcept('Submitted bad demo, dirty cheater or broken client')
        return(0)


schema_link = SpendBy("doom.submit_demo")

schema = {
    "doom": {
        "create_funding": {
            "inputs": [
                Inputs(P2PKH())
            ],
            "outputs": [
                Output(schema_link), # CC global vout
                Output(P2PKH()) # normal change vout; input - create_amount - txfee
            ],
        },
        "submit_demo": {
            "inputs": [
                Input(schema_link) # faucet create or drip utxo from global
            ],
            "outputs": [
                Output(P2PKH(), RelativeAmount(0) - 10000),# input amount - txfee
                Output(schema_link, ExactAmount(0))
            ],
            "validators": [
                # put txpow back in after segfault is addressed; segfault can be reproduced by using create_tx_pow within submit_demo func?
                #TxPoW(0), # 00..00 txpow for submitdemo, is relatively heavy valdiation so requires some rate limiting, FIXME add DOS ban score 
                DoomDemo(0)
            ]
        },
    }
}



# FIXME set defaults to 'fail' so help message is returned to user if missing args, maybe a more elegant way of doing this
def create_funding(app, create_amount='fail', seed='fail'):
    try:
        create_amount = int(create_amount)
        seed = int(seed)
        pdb.set_trace()
    except:
        return(rpc_error(info['help']['create_funding']))

    myaddr = rpc_wrap(app.chain, 'setpubkey')['address']
    global_pair = string_keypair(seed)

    vins, vins_amount = find_inputs(app.chain, [myaddr], create_amount+10000)
    print(seed)

    create_tx = app.create_tx_extra_data({
        "name": "doom.create_funding",
        "inputs": [vins],
        "outputs": [
            {"amount": create_amount,
             "script": {"pubkey": global_pair['pubkey']}},
            {"script": {"address": myaddr}, "amount": vins_amount - create_amount - 10000}
        ]
    }, 
    {"seed": seed})
    mywif = rpc_wrap(app.chain, 'dumpprivkey', myaddr)
    create_tx.sign((mywif,))
    return(rpc_success(create_tx.encode()))


def submit_demo(app, seed=None):
    if not seed:
        return(rpc_error(info['help']['submit_demo']))
    rawtics = b''
    demo_path = sys.path[0] + '/pycc/active_cc/WADS/' + str(seed) + '/' + str(seed) + '.demo' # FIXME fixed path sucks; will fix after blocknotify thing is removed
    if os.path.isfile(demo_path):
        with open(demo_path, "rb") as f:
            f.seek(13) # we don't care about the header
            while (f.peek(1)[:1] != b"\x80"): # 0x80 marks the end of tics, we don't care about it or anything following
                rawtics += f.read(4)
            f.flush()
        opret = zlib.compress(rawtics, 9) # FIXME this can be lowered if performance is impacted, should have a check to make sure opret vout is not >10k
    else:
        return(rpc_error(demo_path + ' not found'))

    myaddr = rpc_wrap(app.chain, 'setpubkey')['address']
    global_pair = string_keypair(seed)

    CC_addr = CCaddr_normal(global_pair['pubkey'], app.eval_code)

    vin, vin_tx, vin_amount = find_input(app.chain, [CC_addr], 0, True)
    vin['script']['pubkey'] = global_pair['pubkey']
    # FIXME add a check here to check that seed of vin matches global address
    # could prevent a player from submitting demo if we create a bad create_funding with mismatched seed

    #vin['script']['pubkey'] = global_pair['pubkey'] # FIXME this causes a komodod segfault with create_tx_pow somehow?
    wifs = (global_pair['wif'],)

    submit_tx = app.create_tx_extra_data({
        "name": "doom.submit_demo",
        "inputs": [
            vin
        ],
        "outputs": [
            {"script": {"address": myaddr}},
            {"script": {"pubkey": global_pair['pubkey']}}
        ]
    },
    {"rawtics": opret})
    submit_tx.sign(wifs)
    return rpc_success(submit_tx.encode())



def create_wad(app, in_hash=False):
    if not in_hash:
        if app.chain.get_height() % 10 == 0 and not in_hash:
            in_hash = rpc_wrap(app.chain, 'getbestblockhash')
        else:
            return(rpc_success('not height % 10, do not need to generate'))

    seed = int(in_hash,16) >> 225
    wad_path = make_wad(seed)
    if wad_path:
        return rpc_success('created: ' + wad_path)
    return(rpc_error('wad not created or already exists'))


def make_wad(seed):
    wad_dir = sys.path[0] + '/WADS/' + str(seed)
    wad_path = wad_dir + '/' + str(seed) + '.wad'
    if not os.path.exists(wad_dir):
        os.makedirs(wad_dir)
    if not os.path.isfile(wad_path):
        gen = oblige.DoomLevelGenerator(seed)
        gen.generate(wad_path)
        return wad_path
    return(False)


info = {"functions": {"create_wad": create_wad,
                      "submit_demo": submit_demo,
                      "create_funding": create_funding},
        "eval": b'dd',
        "schema": schema, # FIXME this seems kind of stupid as we can assume schema dict will always exist, leaving it for now
        "help": {"create_wad": "pycli doom create_wad [hash]", # FIXME not used until pycli segfault is fixed, using blocknotify for now
                 "submit_demo": "pycli doom submit_demo seed", # 
                 "create_funding": "pycli doom create_funding amount seed"}} 
                 # create the "faucet", this _should be_ done automatically but for v0 I will make a central node that creates these utxos every blocks % 10


"""
### TODO
clean up all the fixed paths, just general path management in general
    see if we can get away with not saving temp_demos at all, have subproc pass bytes as a literal file somehow

pycli causes a segfault in komodod if it is called twice in quick succession. 
    This can be reproduced by putting a loop in cc_cli and calling it via komodo-cli twice

long term, it's much better if we can build oblige and prboom directly into the daemon, much safer 
    could be in pycc.cpp accessed as app.chain.oblige() and app.chain.prboom() 

right now the validation code is assuming the wads will exist. This means validation is currently relying on the blocknotify script, doom_notify.py; not good
    once the pycli segfault is fixed, we can rely on "create_wad", such be safer but still not ideal 
        consider making something similar to cc_eval, cc_cli but for blocknotify/txnotify, cc_notify

change entropy mechanism from blocks % 10 to notarization txids 
    use notarization db(NOT MEMPOOL) as we can assume it's unchanging

need some mechanism other than earlytxid to force miners to pay blocks to arbitary conditions
    maybe it could just be a single UTXO that dwiddles over time, so it can be funded once and forgotten about

long term, newly syncing nodes should get latest notarization hash via nspv from all peers
    once it's confident it has latest notarization hash
    turn off validation until it reaches unnotarized blocks 
"""

