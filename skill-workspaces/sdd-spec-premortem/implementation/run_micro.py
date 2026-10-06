"""Five independent repetitions with the complete assigned skill package."""
import argparse
import concurrent.futures
import os
import subprocess
from pathlib import Path
os.environ['PYTHONDONTWRITEBYTECODE']='1'

p=argparse.ArgumentParser()
p.add_argument('--variant',default='old_skill',choices=['old_skill','with_skill','without_skill'])
p.add_argument('--skill')
p.add_argument('--workers',type=int,default=2)
p.add_argument('--reps',default='1,2,3,4,5')
p.add_argument('--prefix',default='micro')
p.add_argument('--timeout',type=int,default=480)
args=p.parse_args()
if Path(__file__).with_name('hold-new-micro-runs').exists():
    print('New micro runs held by user steering; queued repetitions were not launched.',flush=True)
    raise SystemExit(0)

def run(rep):
    command=['uv','run','--no-project','python',str(Path(__file__).with_name('run_behavior.py')),'--ids','21','--variant',args.variant,'--iteration',f'{args.prefix}-{rep}','--workers','1','--timeout',str(args.timeout)]
    if args.skill:
        command+=['--skill',args.skill]
    return subprocess.run(command).returncode

with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
    codes=list(pool.map(run,[int(x) for x in args.reps.split(',')]))
raise SystemExit(max(codes))
