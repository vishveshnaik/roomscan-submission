import argparse
import json
from pathlib import Path
from .pipeline import run


def main():
    parser=argparse.ArgumentParser(description='Local room capture baseline. Unverified values stay explicit.')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('run',help='Reconstruct a capture')
    p.add_argument('input')
    p.add_argument('--out',required=True)
    p.add_argument('--tier',choices=['auto','lidar','photos','video'],default='auto')
    p.add_argument('--no-drift',action='store_true')
    p.add_argument('--geometry',choices=['baseline','structural'],default='structural')
    p.add_argument('--no-damage',action='store_true')
    p.add_argument('--metric',action='store_true',help='Image-only SfM plus local learned metric depth (optional model dependencies)')
    p.add_argument('--weights',default='models/depth_pro.pt')
    p.add_argument('--keyframes',type=int,default=240)
    p.add_argument('--depth-views',type=int,default=12)
    p.add_argument('--rotate-cw',action='store_true',help='Rotate sideways video frames 90 degrees clockwise')
    p.add_argument('--every',type=int,default=20)
    p.add_argument('--evidence',help='Optional human-reviewed surface evidence JSON')
    p=sub.add_parser('compare',help='Rigidly compare two cached metric scans without asserting accuracy')
    p.add_argument('source_cache');p.add_argument('target_cache')
    p.add_argument('--source-structure',required=True);p.add_argument('--target-structure',required=True);p.add_argument('--out',required=True)
    p=sub.add_parser('evaluate',help='Score output against independently collected ground truth')
    p.add_argument('result')
    p.add_argument('truth')
    p.add_argument('--out',required=True)
    p.add_argument('--repeat')
    p.add_argument('--competitor')
    p=sub.add_parser('validate')
    p.add_argument('result')
    args=parser.parse_args()
    try:
        if args.command=='run':
            if min(args.every,args.keyframes,args.depth_views)<1:
                raise ValueError('--every, --keyframes and --depth-views must be positive')
            result=run(args.input,args.out,args.tier,not args.no_drift,args.every,args.evidence,args.geometry,not args.no_damage,args.metric,args.weights,args.rotate_cw,args.keyframes,args.depth_views)
            print(json.dumps({'status':result['status'],'rooms':len(result['rooms']),
                              'mode':('metric_multiview' if args.metric else 'relative_two_view') if result['tier'] in {'photos','video'} else 'lidar',
                              'seconds':result['timing_seconds'],'review':str(Path(args.out).resolve()/'review.html')}))
        elif args.command=='validate':
            from .pipeline import validate
            validate(json.loads(Path(args.result).read_text()))
            print('Schema valid')
        elif args.command=='compare':
            from .compare import compare_captures
            report=compare_captures(args.source_cache,args.target_cache,args.source_structure,args.target_structure,args.out)
            print(json.dumps({'status':report['status'],'alignment':report['alignment']}))
        else:
            from .evaluate import evaluate
            report=evaluate(json.loads(Path(args.result).read_text()),json.loads(Path(args.truth).read_text()),
                            json.loads(Path(args.repeat).read_text()) if args.repeat else None,
                            json.loads(Path(args.competitor).read_text()) if args.competitor else None)
            out=Path(args.out)
            out.mkdir(parents=True,exist_ok=True)
            (out/'benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
            rows=['# Benchmark report','',f"Overall: **{report['status']}**",'', '| Gate | Status | Detail |','| --- | --- | --- |']
            for k,v in report['gates'].items():
                rows.append(f"| {k} | {v['status']} | {json.dumps(v,sort_keys=True)} |")
            rows+=['','Missing ground truth is not a pass. Uncalibrated ranges are not statistical confidence intervals.']
            (out/'benchmark.md').write_text('\n'.join(rows)+'\n')
            print(report['status'])
    except (ValueError,KeyError,OSError) as error:
        parser.exit(2,f'Error: {error}\n')

if __name__=='__main__':
    main()
