#!python

import sys
import json
import requests
import leb128
import zlib
import subprocess
import time

def gpu_temp():
    out = subprocess.run(['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader'],
                         capture_output=True, encoding='utf8')
    return int(out.stdout)

context = []
declen = 0
enclen = 0
ziplen = 0

file = open(sys.argv[1], "r", encoding="UTF-8")
inbuf = ""
exhausted = False
prev_is_ch = False

outf = open(sys.argv[2], "wb")
outz = zlib.compressobj(level=9, wbits=-15)

while True:
    while gpu_temp() > 75:
        time.sleep(1)

    while len(inbuf) < 1024 and not exhausted:
        r = file.read(256)
        if r:
            inbuf += r
        else:
            exhausted = True

    if len(inbuf) == 0 and exhausted:
        break

    if len(context) > 512:
        context = context[len(context) - 512:]

    r = requests.post('http://localhost:8080/completion',
                      headers={'Content-Type': 'application/json'},
                      data=json.dumps({
                          'prompt': "".join(context),
                          'n_predict': 1,
                          'top_k': 128,
                          'n_probs': 128,
                          'seed': 42,
                          'temperature': 0,
                      })
                      )
    try:
        ds = r.json()
        probs = ds['completion_probabilities'][0]['probs']
        if len(probs) > 128:
            probs = probs[:128]

        matches = [(i, len(probs[i]['tok_str']), probs[i]['tok_str'])
                   for i in range(len(probs)) if inbuf.startswith(probs[i]['tok_str'])]
        if matches[0][0] != 0:
            matches.sort(key=lambda m: m[1], reverse=True)
    except Exception as e:
        print(e)
        matches = []

    if len(matches):
        idx, matchlen, token = matches[0]
        print(f"Match: {token} Len: {matchlen} Idx: {idx}")
        context.append(token)
        prev_is_ch = False
        declen += len(token)
        inbuf = inbuf[matchlen:]
    else:
        ch = inbuf[0]
        cp = ord(ch)
        idx = cp + 128

        print(f"No match, char: {ch}, Codepoint: {cp}, Idx: {idx}")
        if prev_is_ch:
            context[-1] += ch
        else:
            context.append(ch)
            prev_is_ch = True

        declen += 1
        inbuf = inbuf[1:]

    enc = leb128.u.encode(idx)
    zipped = outz.compress(enc)
    enclen += len(enc)
    ziplen += len(zipped)
    zip_extra = len(outz.copy().flush())
    zip_total = ziplen + zip_extra

    print(f"{declen} -> {enclen} -> {zip_total} ({declen / zip_total})")

    outf.write(zipped)
    outf.flush()

zipped = outz.flush()
ziplen += len(zipped)
outf.write(zipped)
print(f"flush: {declen} -> {enclen} -> {ziplen} ({declen / ziplen})")
