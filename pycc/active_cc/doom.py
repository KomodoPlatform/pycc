import oblige
import os
import sys
from pycc import *
from pycctx import *
import json
import traceback
import zlib
import subprocess # RISSSSKKKKKYYYYYYYYYYY should compile prboom directly into daemon and be accesible via chain.prboom()


valid_events = ['newentropy', 'payout']
transitions = ( ('play', ['newentropy'], 'submit'),
                ('submit', ['newentropy'], 'proc'),
                ('proc', ['newentropy'], 'proc'), # do nothing
                ('proc', ['payout'], 'play'),
            )



def rebuild_demo(rawtics):
    static_header = b'm\x02\x01\x01\x00\x00\x00\x00\x00\x01\x00\x00\x00' # maybe this can differ by "plan"
    uncomp = zlib.decompress(rawtics)
    return(static_header + uncomp + b'\x80')


def prboom_val(seed, demo_path):
    print('huh')
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
    results = results.split('\n')
    if results[-4] == 'FINISHED: E1M1' and results[-3].startswith("Timed"): # FIXME make sure this is static, maybe better to search through last few params
        gametics = int(results[-3].split(' ')[1])
        return(gametics)

class CheckDemoHash:
    def __init__(self, input_idx):
        self.input_idx = input_idx

    def __call__(self, tx, spec):
        txid_in = spec['inputs'][0]['previous_output'][self.input_idx]
        tx_in = Tx.decode_bin(tx.app.chain.get_tx_confirmed(txid_in))
        prev_params = decode_params(get_opret(tx_in))
        check_hash = prev_params[2]['hash']

        demo = ast.literal_eval(tx.tx.outputs[-1].script.get_opret_data().decode())[2]['rawtics']
        opret_hash = hashlib.sha256(demo).hexdigest()

        assert check_hash == opret_hash

        return(0)

class DoomDemo:
    def __init__(self, input_idx):
        self.input_idx = input_idx

    def __call__(self, tx, spec):
        txid_in = spec['inputs'][0]['previous_output'][self.input_idx]
        tx_in = Tx.decode_bin(tx.app.chain.get_tx_confirmed(txid_in))
        prev_params = decode_params(get_opret(tx_in))
        curr_params = decode_params(get_opret(tx.tx))

        seed = prev_params[2]['seed']

        proported_tics = curr_params[2]['gametics']
        rawtics = curr_params[2]['rawtics']

        current_path = os.path.dirname(os.path.realpath(__file__))
        if not os.path.exists(current_path + '/temp_demos'):
            os.makedirs(current_path + '/temp_demos')
        full_demo = rebuild_demo(rawtics)
        temp_path = current_path + '/temp_demos/' + str(seed) + '.demo'
        with open(temp_path, "wb") as rebuilt:
            rebuilt.write(full_demo)

        gametics = prboom_val(seed, temp_path)
        os.remove(temp_path)
        if not gametics:
            raise IntendExcept('Submitted bad demo, dirty cheater or broken client')
        if proported_tics != gametics:
            raise IntendExcept('Submitted bad demo, misconfigured prboom!')
        return(0)


schema = {
    "doom": {
        "create_funding": {
            "inputs": [
                Input(P2PKH()) # any normal P2PKH input
            ],
            "outputs": [
                Output(SpendBy("doom.payout")), # CC global, reward to be paid out to winner
                Output(P2PKH()) # any normal P2PKH outputs
            ],
            # includes RelativeAmountUserArg in opret for winner amount
        },
        "payout": {
            "inputs": 
                #[Input(SpendBy("doom.payout"))], # CC global, reward amount from create_funding and 0 sat utxos from submit_demos
                #[Inputs(SpendBy("doom.payout"))] # all 0 sat from submit_demos
                [Inputs(SpendBy("doom.payout"))]
            ,
            "outputs": [
                Output(P2PKH()) # FIXME enforce amount, RelativeAmountUserArg(0) - 10000)# full amount - txfee to winner, may have to increase txfee to incentivize miners to include these
                #Output(P2PKH(), RelativeAmountUserArg(0) - 10000) # FIXME check amounts, need ExactAmountAllInputs()

            ]
            # includes 'payout' event in opret
        },  
        "submit_hash": {
            "inputs": [
                Inputs(P2PKH()) # any normal P2PKH inputs, at least 3x txfee
            ],
            "outputs": [
                Output(SpendBy("doom.submit_demo"), ExactAmount(20000)), # CC global, to be spent by submit_demo
                Output(P2PKH()), # change amount output to user

            ]
            # will include a hash of the demo in opret 
            # can only happen while state is 'play'
        },
        "submit_demo": {
            "inputs": [
                Input(SpendBy("doom.submit_demo")) # faucet create or drip utxo from global
            ],
            "outputs": [
                Output(SpendBy("doom.payout"), ExactAmount(0)) # 0 sat output to be spent by payout
            ],
            "validators": [
                # check that hash of input OPRET actually matches submitted demo 
                # can only happen while state is 'submit'
                CheckDemoHash(0),
                DoomDemo(0)
            ]
        }
    }
}


# FIXME set defaults to 'fail' so help message is returned to user if missing args, maybe a more elegant way of doing this
def create_funding(app, create_amount='fail', seed='fail'):
    print('IN')
    try:
        create_amount = int(create_amount)
        seed = int(seed)
        #pdb.set_trace()
    except:
        return(rpc_error(info['help']['create_funding']))

    myaddr = rpc_wrap(app.chain, 'setpubkey')['address']
    global_pair = string_keypair(seed)

    vin, vin_tx, vin_amount = find_input(app.chain, [myaddr], create_amount+10000)
    print(seed)

    create_tx = app.create_tx_extra_data({
        "name": "doom.create_funding",
        "inputs": [vin],
        "outputs": [
            {"amount": create_amount,
             "script": {"pubkey": global_pair['pubkey']}},
            {"amount": vin_amount - create_amount - 10000,
             "script": {"address": myaddr}}
        ]
    }, 
    {"seed": seed})
    mywif = rpc_wrap(app.chain, 'dumpprivkey', myaddr)
    create_tx.sign((mywif,))
    return(rpc_success(create_tx.encode()))

def submit_hash(app, seed=None):
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

    print("opret", opret)

    opret_hash = hashlib.sha256(opret).hexdigest()

    setpubkey = rpc_wrap(app.chain, 'setpubkey')
    myaddr = setpubkey['address']
    mywif = rpc_wrap(app.chain, 'dumpprivkey', myaddr)


    print('opret_hash', opret_hash)
    my_global_pair = string_keypair(mywif + str(seed)) # FIXME research if this will degrade key's security 
    # could probably use pubkey instead with a Validator to check that an input is spent by this pubkey 

    vins, vins_amount = find_inputs(app.chain, [myaddr], 30000)

    wifs = (mywif,)

    submit_tx = app.create_tx_extra_data({
        "name": "doom.submit_hash",
        "inputs": [
            vins
        ],
        "outputs": [
            {"script": {"pubkey": my_global_pair['pubkey']}},
            {"amount": vins_amount - 20000,
             "script": {"address": myaddr}},
        ]
    },
    {"hash": opret_hash, "seed": seed})
    submit_tx.sign(wifs)
    return rpc_success(submit_tx.encode())


# TODO
# vout0 should go to winner least game tics
# submit_demo must store gametic count 
# check that full amount is spent to winner


def payout(app, seed=None):
    if not seed:
        return(rpc_error(info['help']['payout']))
    global_pair = string_keypair(seed)
    CC_addr = CCaddr_normal(global_pair['pubkey'], app.eval_code)
    print('MY CC_ADDR', CC_addr)

    # FIXME cannot use find_all_inputs safely until we have CCv2 implemented into pycctx

    # CCv2 validation of submit_demo txes will ensure that users cannot send to global_string(seed) address 
    # unless they submit a demo that finishes that seed's level 
    # also need some way to ensure a bad actor is not resubmitting the same demo over and over to spam, maybe some required burn or payment here
    # possibly validation that ensures a user cannot submit a demo if it has more gametics than an already submitted demo 

    # leaving this for now as I expect to have this implemented 
    vins, vins_amount = find_all_inputs(app.chain, [CC_addr], True)
    for vin in vins:
        vin['script']['pubkey'] = global_pair['pubkey']


    submit_tx = app.create_tx_extra_data({
        "name": "doom.payout",
        "inputs": [
            vins
        ],
        "outputs": [
            #{"amount": vins_amount - 10000,
            {"script": {"address": global_pair['addr']}, # FIXME goes to winner P2PKH
             "amount": vins_amount} # FIMXE enforce amount
        ] 
    },
    {"doom": 'payout', "seed":seed})
    wifs = (global_pair['wif'],)

    submit_tx.sign(wifs)
    return rpc_success(submit_tx.encode())


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


    gametics = prboom_val(seed, demo_path)
    if not gametics:
        raise IntendExcept('demo validation failed, does not finish E1M1. Misconfigured prboom')

    myaddr = rpc_wrap(app.chain, 'setpubkey')['address']
    mywif = rpc_wrap(app.chain, 'dumpprivkey', myaddr)

    global_pair = string_keypair(seed)
    my_global_pair = string_keypair(mywif + str(seed))


    CC_addr = CCaddr_normal(my_global_pair['pubkey'], app.eval_code)
    print(CC_addr)
    hash_vin, hash_tx, hash_amount = find_input(app.chain, [CC_addr], 0, True)
    # FIXME this will need to ensure that we are spending a utxo that we created and not a utxo a bad actor has sent to our seed address
    # bad actor can send a utxo to this address once it's publicly known(after submit_hash), and if this utxo is selected here, it could cause 
    # this function to create an invalid submit_demo transaction 


    vin, vin_tx, vin_amount = find_input(app.chain, [CC_addr], 0, True)
    vin['script']['pubkey'] = my_global_pair['pubkey']
    print('MY_GLOBAL', my_global_pair['pubkey'])
    print("GLOBAL", global_pair['pubkey'])
    # FIXME add a check here to check that seed of vin matches global address
    # could prevent a player from submitting demo if we create a bad create_funding with mismatched seed

    #vin['script']['pubkey'] = global_pair['pubkey'] # FIXME this causes a komodod segfault with create_tx_pow somehow?
    wifs = (my_global_pair['wif'],)

    submit_tx = app.create_tx_extra_data({
        "name": "doom.submit_demo",
        "inputs": [
            vin
        ],
        "outputs": [
            {"script": {"pubkey": global_pair['pubkey']}}
        ]
    },
    {"rawtics": opret, "seed":seed, "gametics": gametics}) #FIXME add gametics val 
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


def my_events(prevblock, events):
    if ( (prevblock['height']+1) % 10 == 0):
        print("SPECIAL EVENT OFF")
        events.append('newentropy')
        return(events)
    return(events)


info = {"name": "doom",
        "functions": {"create_wad": create_wad,
                      "submit_hash": submit_hash,
                      "submit_demo": submit_demo,
                      "create_funding": create_funding,
                      "payout": payout},
        "eval": b'dd',
        "FSM": transitions,
        "special_events": my_events,
        "schema": schema, # FIXME this seems kind of stupid as we can assume schema dict will always exist, leaving it for now
        "help": {"create_wad": "pycli doom create_wad [hash]", # FIXME not used until pycli segfault is fixed, using blocknotify for now
                 "submit_demo": "pycli doom submit_demo seed", # 
                 "create_funding": "pycli doom create_funding amount seed",
                 "payout": "pycli doom payout seed"}}
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

