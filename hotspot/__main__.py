import argparse
import json
import sys
from pathlib import Path
from .common import read, write
from .store import Store
from .service import dispatch, exclusive

def main(argv=None):
    p=argparse.ArgumentParser(description='长灯说史热点中心；手工数据与证据审核，不执行平台发布')
    p.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[1]/'.runtime')
    p.add_argument('--environment',choices=['production','test'],default='production')
    sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('serve');s.add_argument('--port',type=int,default=8776)
    for name in ('status','collect','audit'):sub.add_parser(name)
    for name in ('manual','evidence','candidate','review','invalidate'):
        s=sub.add_parser(name);s.add_argument('file',type=Path)
    for name in ('replay','packet','gate'):
        s=sub.add_parser(name);s.add_argument('id')
    s=sub.add_parser('search');s.add_argument('query')
    s=sub.add_parser('export');s.add_argument('id');s.add_argument('--actor',required=True);s.add_argument('--authorize',action='store_true');s.add_argument('--workflow',default='history_long_video')
    s=sub.add_parser('backup');s.add_argument('destination',type=Path)
    s=sub.add_parser('restore');s.add_argument('backup',type=Path);s.add_argument('destination',type=Path)
    s=sub.add_parser('benchmark');s.add_argument('gold',type=Path);s.add_argument('runs',type=Path);s.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv)
    try:
        if args.command=='restore':result=Store.restore(args.backup,args.destination)
        elif args.command=='benchmark':
            from .benchmark import evaluate_repeats
            result=evaluate_repeats(read(args.gold),read(args.runs));write(args.output,result)
        else:
            store=Store(args.project,args.environment)
            if args.command=='serve':
                from .server import serve
                serve(store,args.port);return 0
            if args.command=='backup':
                with exclusive(store):result=store.backup(args.destination)
            else:
                action={'status':'overview','candidate':'save_candidate','packet':'review_packet'}.get(args.command,args.command)
                data=read(args.file) if hasattr(args,'file') else {}
                if args.command in ('packet','gate'):data={'candidate_id':args.id}
                elif args.command=='replay':data={'snapshot_id':args.id}
                elif args.command=='search':data={'query':args.query}
                elif args.command=='export':data={'candidate_id':args.id,'actor':args.actor,'authorize':args.authorize,'target_workflow':args.workflow}
                result=dispatch(store,action,data)
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (ValueError,KeyError,OSError,TypeError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
