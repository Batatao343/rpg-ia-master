import json,glob
tot=ok=0;fora=[]
for f in sorted(glob.glob('docs/spec373/arena-*.json')):
    d=json.load(open(f,encoding='utf-8'))
    for k,v in d['criaturas'].items():
        tot+=1
        if v.get('ok'): ok+=1
        else: fora.append(k)
print(ok,tot)
print(fora)
base=set();
for f in glob.glob('docs/spec373/base/eval/arena-*.json'):
    d=json.load(open(f,encoding='utf-8'))
    for k,v in d['criaturas'].items():
        if not v.get('ok'): base.add(k)
now=set(fora)
print('NEW FAIL',sorted(now-base)); print('NEW OK',len(base-now))
print('STILL',sorted(now&base))
