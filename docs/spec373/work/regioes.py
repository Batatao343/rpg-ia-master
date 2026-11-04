import glob,re,os,sys
ids=sys.argv[1].split(',')
regs=set()
for f in glob.glob('data/bestiario/fichas/*.yaml'):
    t=open(f,encoding='utf-8').read()
    for i in ids:
        if re.search(r'id: '+i+r'\b',t): regs.add(os.path.basename(f)[:-5])
print(','.join(sorted(regs)))
