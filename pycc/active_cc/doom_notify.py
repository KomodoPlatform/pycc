import os
import sys
from stakerlib import def_credentials
from doom import make_wad

# FIXME this should use notarization hashes instead of block hashes as they can be considered "final" as soon as they are confirmed
# use notarization db as it cannot be changed once notarization enters it

blockhash = sys.argv[1]
rpc = def_credentials('PYDOOM')
height = rpc.getblock(blockhash)['height']
print('height, hash', height, blockhash)
if height % 10 == 0:
    seed = int(blockhash,16) >> 225
    wad_path = make_wad(seed)
    if wad_path:
        print('created ' + wad_path + ' at height ' + str(height))
        sys.exit(0)
    else:
        print('did not create ' + str(seed) + '.wad , already exists or error')
        sys.exit(0)
else:
    print('not height % 10, do not need to generate wad')
    sys.exit(0)